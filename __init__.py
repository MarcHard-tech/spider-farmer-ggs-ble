"""Spider Farmer GGS Controller integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MAC_ADDRESS, DOMAIN, PLAN_STORAGE_PATH
from .coordinator import SpiderFarmerGGSCoordinator
from . import plan_storage

PLATFORMS = ["sensor", "switch", "number", "select", "time"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Spider Farmer GGS from a config entry."""
    coordinator = SpiderFarmerGGSCoordinator(hass, entry.data[CONF_MAC_ADDRESS])

    # Attempt first data fetch. If the device is not reachable right now,
    # HA will raise ConfigEntryNotReady and automatically retry every 30 s.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await hass.async_add_executor_job(plan_storage.seed_defaults, PLAN_STORAGE_PATH)

    from .services import async_register_services
    async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: SpiderFarmerGGSCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
