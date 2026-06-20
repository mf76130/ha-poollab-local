"""Sensor platform for PoolLab Local."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    IDEAL_RANGES,
    MANUFACTURER,
    MEASUREMENT_TYPES,
    MEASURE_STATUS_NAMES,
    MODEL,
)
from .coordinator import PoolLabCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PoolLab sensors from a config entry."""
    coordinator: PoolLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]

    known_types: set[int] = set()
    entities: list[SensorEntity] = [PoolLabBatterySensor(coordinator, address)]

    # Recreate a sensor for every measurement type ever seen on this device
    # (from the entity registry), not just types present in the live
    # coordinator data right now. Otherwise, after a restart where the
    # device hasn't been read yet this session, these sensors would never
    # be instantiated at all - and RestoreEntity can't restore a value for
    # an entity object that doesn't exist.
    prefix = f"{address}_measure_"
    registry = async_get_entity_registry(hass)
    for entity_entry in async_entries_for_config_entry(registry, entry.entry_id):
        if not entity_entry.unique_id.startswith(prefix):
            continue
        try:
            type_id = int(entity_entry.unique_id[len(prefix) :])
        except ValueError:
            continue
        if type_id not in known_types:
            known_types.add(type_id)
            entities.append(PoolLabMeasurementSensor(coordinator, address, type_id))

    async_add_entities(entities)

    @callback
    def _add_new_measurement_sensors() -> None:
        if not coordinator.data:
            return
        new_entities = [
            PoolLabMeasurementSensor(coordinator, address, type_id)
            for type_id in coordinator.data.get("measurements", {})
            if type_id not in known_types
        ]
        for entity in new_entities:
            known_types.add(entity.type_id)
        if new_entities:
            async_add_entities(new_entities)

    _add_new_measurement_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_measurement_sensors))


class PoolLabBaseEntity(CoordinatorEntity[PoolLabCoordinator], RestoreEntity):
    """Common device info for all PoolLab entities.

    Combines CoordinatorEntity (live BLE data) with RestoreEntity, so the
    last known value survives a Home Assistant restart and isn't lost just
    because the device happens to be unreachable for the first poll after
    startup (e.g. out of range, or busy with the LabCom app).
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator)
        self._address = address

    @property
    def device_info(self) -> DeviceInfo:
        info = (self.coordinator.data or {}).get("device_info", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={("bluetooth", self._address)},
            name="PoolLab",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=str(info.get("fw_version", "")) or None,
        )

    @property
    def available(self) -> bool:
        # Always available: show the last known value (live or restored)
        # rather than flipping to "unavailable" just because the most
        # recent poll attempt failed or hasn't happened yet this session.
        return True


class PoolLabBatterySensor(PoolLabBaseEntity, SensorEntity):
    """Battery level of the PoolLab device."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Battery"

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator, address)
        self._attr_unique_id = f"{address}_battery"
        self._restored_value: int | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = int(float(last_state.state))
            except ValueError:
                self._restored_value = None

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            value = self.coordinator.data.get("device_info", {}).get("battery_level")
            if value is not None:
                return value
        return self._restored_value


class PoolLabMeasurementSensor(PoolLabBaseEntity, SensorEntity):
    """One sensor per measurement scenario seen on the device (e.g. pH, Free Chlorine)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: PoolLabCoordinator, address: str, type_id: int
    ) -> None:
        super().__init__(coordinator, address)
        self.type_id = type_id

        name, unit, _decimals = MEASUREMENT_TYPES.get(
            type_id, (f"Unknown scenario {type_id}", "ppm", 2)
        )
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{address}_measure_{type_id}"
        if unit == "pH":
            self._attr_device_class = SensorDeviceClass.PH

        self._restored_value: float | None = None
        self._restored_attrs: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = float(last_state.state)
            except ValueError:
                self._restored_value = None
            self._restored_attrs = {
                key: last_state.attributes[key]
                for key in (
                    "status",
                    "measure_id",
                    "ideal_low",
                    "ideal_high",
                    "ideal_range_status",
                )
                if key in last_state.attributes
            }

    @property
    def _record(self) -> dict[str, Any] | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("measurements", {}).get(self.type_id)

    @property
    def native_value(self) -> float | None:
        record = self._record
        if record:
            return record["value"]
        return self._restored_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        record = self._record
        if not record:
            return self._restored_attrs

        attrs: dict[str, Any] = {
            "status": MEASURE_STATUS_NAMES.get(record["status"], "unknown"),
            "measure_id": record["measure_id"],
        }

        ideal_range = IDEAL_RANGES.get(self.type_id)
        if ideal_range is not None:
            ideal_low, ideal_high = ideal_range
            attrs["ideal_low"] = ideal_low
            attrs["ideal_high"] = ideal_high
            value = record["value"]
            if value < ideal_low:
                attrs["ideal_range_status"] = "zu niedrig"
            elif value > ideal_high:
                attrs["ideal_range_status"] = "zu hoch"
            else:
                attrs["ideal_range_status"] = "ok"

        return attrs
