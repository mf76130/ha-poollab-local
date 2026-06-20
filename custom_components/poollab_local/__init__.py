"""The PoolLab Local integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PoolLabCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PoolLab Local from a config entry."""
    address = entry.data[CONF_ADDRESS]
    coordinator = PoolLabCoordinator(hass, address)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward platforms first, *then* attempt an initial refresh - and
    # don't let a failed refresh block setup. The device is often out of
    # range or asleep between measurements, and the "Jetzt abrufen" button
    # plus restored sensor state cover that gap. Gating setup on a
    # successful BLE connection (as async_config_entry_first_refresh does)
    # would make the whole integration - including the button - unusable
    # whenever the device simply isn't reachable right now.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
