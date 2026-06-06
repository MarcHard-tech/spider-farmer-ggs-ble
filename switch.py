"""Switch entities for Spider Farmer GGS Controller (on/off controls)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GGSData, SpiderFarmerGGSCoordinator


@dataclass
class GGSSwitchDescription(SwitchEntityDescription):
    """Extends SwitchEntityDescription with accessors and a turn-on/off action."""
    is_on_fn: Callable[[GGSData], Optional[bool]] = lambda d: None
    turn_on_fn: Callable[..., Coroutine] = lambda coord: coord.async_set_fan(True)
    turn_off_fn: Callable[..., Coroutine] = lambda coord: coord.async_set_fan(False)


SWITCH_DESCRIPTIONS: tuple[GGSSwitchDescription, ...] = (
    # ── Confirmed devices ─────────────────────────────────────────────────────
    GGSSwitchDescription(
        key="fan",
        name="Fan",
        icon="mdi:fan",
        is_on_fn=lambda d: d.fan_on,
        turn_on_fn=lambda c: c.async_set_fan(True),
        turn_off_fn=lambda c: c.async_set_fan(False),
    ),
    GGSSwitchDescription(
        key="light",
        name="Grow Light",
        icon="mdi:lightbulb-on",
        is_on_fn=lambda d: d.light_on,
        turn_on_fn=lambda c: c.async_set_light(True),
        turn_off_fn=lambda c: c.async_set_light(False),
    ),
    GGSSwitchDescription(
        key="blower",
        name="Blower",
        icon="mdi:fan-chevron-up",
        is_on_fn=lambda d: d.blower_on,
        turn_on_fn=lambda c: c.async_set_blower(True),
        turn_off_fn=lambda c: c.async_set_blower(False),
    ),
    # ── Optional devices (unavailable if device doesn't report them) ──────────
    GGSSwitchDescription(
        key="humidifier",
        name="Humidifier",
        icon="mdi:air-humidifier",
        is_on_fn=lambda d: d.humidifier_on,
        turn_on_fn=lambda c: c.async_set_humidifier(True),
        turn_off_fn=lambda c: c.async_set_humidifier(False),
    ),
    GGSSwitchDescription(
        key="light2",
        name="Grow Light 2",
        icon="mdi:lightbulb-on-outline",
        is_on_fn=lambda d: d.light2_on,
        turn_on_fn=lambda c: c.async_set_light2(True),
        turn_off_fn=lambda c: c.async_set_light2(False),
    ),
    GGSSwitchDescription(
        key="heater",
        name="Heater",
        icon="mdi:radiator",
        is_on_fn=lambda d: d.heater_on,
        turn_on_fn=lambda c: c.async_set_heater(True),
        turn_off_fn=lambda c: c.async_set_heater(False),
    ),
    GGSSwitchDescription(
        key="fan_natural_wind",
        name="Fan Natural Wind",
        icon="mdi:weather-windy",
        is_on_fn=lambda d: d.fan_natural,
        turn_on_fn=lambda c: c.async_send_config_field(
            "fan", c._build_config_block("fan", {"natural": 1})
        ),
        turn_off_fn=lambda c: c.async_send_config_field(
            "fan", c._build_config_block("fan", {"natural": 0})
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerGGSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GGSSwitchEntity(coordinator, entry, desc) for desc in SWITCH_DESCRIPTIONS
    )


class GGSSwitchEntity(CoordinatorEntity[SpiderFarmerGGSCoordinator], SwitchEntity):
    """An on/off switch entity for a GGS-controlled device."""

    entity_description: GGSSwitchDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SpiderFarmerGGSCoordinator,
        entry: ConfigEntry,
        description: GGSSwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Spider Farmer GGS Controller",
            "manufacturer": "Spider Farmer",
            "model": "GGS Controller",
        }

    @property
    def available(self) -> bool:
        """Entity is only available once the device has reported its state."""
        return (
            self.coordinator.last_update_success
            and self.entity_description.is_on_fn(self.coordinator.data) is not None
        )

    @property
    def is_on(self) -> Optional[bool]:
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.turn_on_fn(self.coordinator)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.turn_off_fn(self.coordinator)
