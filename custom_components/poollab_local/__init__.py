"""The PoolLab Local integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PoolLabCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type PoolLabConfigEntry = ConfigEntry[PoolLabCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PoolLabConfigEntry) -> bool:
    """Set up PoolLab Local from a config entry."""
    address = entry.data[CONF_ADDRESS]
    coordinator = PoolLabCoordinator(hass, address)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PoolLabConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
