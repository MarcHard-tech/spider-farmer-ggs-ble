"""Select entities for Spider Farmer GGS Controller (device mode dropdowns)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Coroutine, Optional

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    FAN_MODES, FAN_MODES_REV,
    HUMIDIFIER_MODES, HUMIDIFIER_MODES_REV,
    LIGHT_MODES, LIGHT_MODES_REV,
)
from .coordinator import GGSData, SpiderFarmerGGSCoordinator


@dataclass
class GGSSelectDescription(SelectEntityDescription):
    """Extends SelectEntityDescription with accessors and a setter."""
    current_fn: Callable[[GGSData], Optional[str]] = lambda d: None
    select_fn: Callable[..., Coroutine] = None
    options_list: list[str] = None


def _light_mode_label(mode_type: Optional[int]) -> Optional[str]:
    return LIGHT_MODES_REV.get(mode_type) if mode_type is not None else None


def _fan_mode_label(mode_type: Optional[int]) -> Optional[str]:
    return FAN_MODES_REV.get(mode_type) if mode_type is not None else None


def _humidifier_mode_label(mode_type: Optional[int]) -> Optional[str]:
    return HUMIDIFIER_MODES_REV.get(mode_type) if mode_type is not None else None


async def _set_light_mode(coordinator: SpiderFarmerGGSCoordinator, module: str, mode_label: str) -> None:
    mode_type = LIGHT_MODES.get(mode_label)
    if mode_type is None:
        return
    block = coordinator._build_config_block(module, {"modeType": mode_type, "lastAutoModeType": mode_type})
    await coordinator.async_send_config_field(module, block)


async def _set_fan_mode(coordinator: SpiderFarmerGGSCoordinator, module: str, mode_label: str) -> None:
    mode_type = FAN_MODES.get(mode_label)
    if mode_type is None:
        return
    block = coordinator._build_config_block(module, {"modeType": mode_type})
    await coordinator.async_send_config_field(module, block)


async def _set_humidifier_mode(coordinator: SpiderFarmerGGSCoordinator, mode_label: str) -> None:
    mode_type = HUMIDIFIER_MODES.get(mode_label)
    if mode_type is None:
        return
    block = coordinator._build_config_block("humidifier", {"modeType": mode_type})
    await coordinator.async_send_config_field("humidifier", block)


SELECT_DESCRIPTIONS: tuple[GGSSelectDescription, ...] = (
    GGSSelectDescription(
        key="light_mode",
        name="Light 1 Mode",
        icon="mdi:lightbulb-cog",
        current_fn=lambda d: _light_mode_label(d.light_mode),
        select_fn=lambda c, v: _set_light_mode(c, "light", v),
        options_list=list(LIGHT_MODES.keys()),
    ),
    GGSSelectDescription(
        key="light2_mode",
        name="Light 2 Mode",
        icon="mdi:lightbulb-cog-outline",
        current_fn=lambda d: _light_mode_label(d.light2_mode),
        select_fn=lambda c, v: _set_light_mode(c, "light2", v),
        options_list=list(LIGHT_MODES.keys()),
    ),
    GGSSelectDescription(
        key="fan_mode",
        name="Fan Mode",
        icon="mdi:fan-auto",
        current_fn=lambda d: _fan_mode_label(d.fan_mode),
        select_fn=lambda c, v: _set_fan_mode(c, "fan", v),
        options_list=list(FAN_MODES.keys()),
    ),
    GGSSelectDescription(
        key="blower_mode",
        name="Blower Mode",
        icon="mdi:fan-auto",
        current_fn=lambda d: _fan_mode_label(d.blower_mode),
        select_fn=lambda c, v: _set_fan_mode(c, "blower", v),
        options_list=list(FAN_MODES.keys()),
    ),
    GGSSelectDescription(
        key="humidifier_mode",
        name="Humidifier Mode",
        icon="mdi:air-humidifier",
        current_fn=lambda d: _humidifier_mode_label(d.humidifier_mode),
        select_fn=lambda c, v: _set_humidifier_mode(c, v),
        options_list=list(HUMIDIFIER_MODES.keys()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerGGSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GGSSelectEntity(coordinator, entry, desc) for desc in SELECT_DESCRIPTIONS
    )


class GGSSelectEntity(CoordinatorEntity[SpiderFarmerGGSCoordinator], SelectEntity):
    """A select entity for choosing device modes."""

    entity_description: GGSSelectDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SpiderFarmerGGSCoordinator,
        entry: ConfigEntry,
        description: GGSSelectDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_options = description.options_list
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Spider Farmer GGS Controller",
            "manufacturer": "Spider Farmer",
            "model": "GGS Controller",
        }

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.entity_description.current_fn(self.coordinator.data) is not None
        )

    @property
    def current_option(self) -> Optional[str]:
        return self.entity_description.current_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        await self.entity_description.select_fn(self.coordinator, option)
