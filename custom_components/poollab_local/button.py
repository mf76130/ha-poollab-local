"""Button platform for PoolLab Local — manually trigger a BLE refresh."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import PoolLabCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PoolLab refresh button."""
    coordinator: PoolLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    async_add_entities([PoolLabRefreshButton(coordinator, address)])


class PoolLabRefreshButton(CoordinatorEntity[PoolLabCoordinator], ButtonEntity):
    """Connects to the PoolLab right now and pulls the latest measurements.

    Use this right after taking a measurement instead of waiting for the
    (intentionally long) background poll interval - the device only
    accepts one BLE connection at a time, so polling rarely makes more
    sense than polling on demand.
    """

    _attr_has_entity_name = True
    _attr_name = "Jetzt abrufen"
    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: PoolLabCoordinator, address: str) -> None:
        super().__init__(coordinator)
        self._address = address
        self._attr_unique_id = f"{address}_refresh_button"

    @property
    def available(self) -> bool:
        # Critical: never tie this to coordinator.last_update_success.
        # If a refresh attempt fails, the *only* way to retry is this
        # button - making it unavailable after a failed poll would create
        # a permanent deadlock (no auto-polling, no working retry button).
        return True

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

    async def async_press(self) -> None:
        """Trigger an immediate BLE poll of the device."""
        await self.coordinator.async_request_refresh()
