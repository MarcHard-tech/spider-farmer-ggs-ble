"""Number (slider) entities for Spider Farmer GGS Controller."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Coroutine, Optional

from homeassistant.components.number import (
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GGSData, SpiderFarmerGGSCoordinator


@dataclass
class GGSNumberDescription(NumberEntityDescription):
    """Extends NumberEntityDescription with accessors and a set-value action."""
    value_fn: Callable[[GGSData], Optional[float]] = lambda d: None
    set_fn: Callable[..., Coroutine] = lambda coord, v: coord.async_set_fan(True, v)


NUMBER_DESCRIPTIONS: tuple[GGSNumberDescription, ...] = (
    # ── Confirmed devices ─────────────────────────────────────────────────────
    GGSNumberDescription(
        key="fan_speed",
        name="Fan Speed",
        icon="mdi:fan",
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        value_fn=lambda d: d.fan_level,
        # Speed 0 = off, 1–10 = on at that speed
        set_fn=lambda c, v: c.async_set_fan(v > 0, int(v)),
    ),
    GGSNumberDescription(
        key="light_level",
        name="Grow Light Level",
        icon="mdi:lightbulb-on",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light_level,
        set_fn=lambda c, v: c.async_set_light(v > 0, int(v)),
    ),
    GGSNumberDescription(
        key="blower_level",
        name="Blower Level",
        icon="mdi:fan-chevron-up",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.blower_level,
        set_fn=lambda c, v: c.async_set_blower(v > 0, int(v)),
    ),
    GGSNumberDescription(
        key="light2_level",
        name="Grow Light 2 Level",
        icon="mdi:lightbulb-on-outline",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light2_level,
        set_fn=lambda c, v: c.async_set_light2(v > 0, int(v)),
    ),
    # ── Optional devices (unavailable if device doesn't report them) ──────────
    GGSNumberDescription(
        key="humidifier_level",
        name="Humidifier Level",
        icon="mdi:air-humidifier",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.humidifier_level,
        set_fn=lambda c, v: c.async_set_humidifier(v > 0, int(v)),
    ),
    GGSNumberDescription(
        key="heater_level",
        name="Heater Level",
        icon="mdi:radiator",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.heater_level,
        set_fn=lambda c, v: c.async_set_heater(v > 0, int(v)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerGGSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GGSNumberEntity(coordinator, entry, desc) for desc in NUMBER_DESCRIPTIONS
    )


class GGSNumberEntity(
    CoordinatorEntity[SpiderFarmerGGSCoordinator], RestoreNumber
):
    """A slider entity for controlling the level of a GGS-managed device."""

    entity_description: GGSNumberDescription
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: SpiderFarmerGGSCoordinator,
        entry: ConfigEntry,
        description: GGSNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
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
            and self.entity_description.value_fn(self.coordinator.data) is not None
        )

    @property
    def native_value(self) -> Optional[float]:
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_fn(self.coordinator, value)
