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


def _seconds_to_minutes(seconds: Optional[int]) -> Optional[float]:
    """Convert seconds to minutes for display."""
    return seconds / 60 if seconds is not None else None


def _light_schedule_setter(module: str, field: str):
    """Create a setter for light schedule fields."""
    async def setter(coordinator, value):
        cached = coordinator._build_config_block(module, {})
        tp = cached.get("timePeriod", [{"enabled": 1, "weekmask": 127}])
        if not tp:
            tp = [{"enabled": 1, "weekmask": 127}]
        tp[0][field] = int(value)
        cached["timePeriod"] = tp
        await coordinator.async_send_config_field(module, cached)
    return setter


def _light_ppfd_setter(module: str, field: str):
    """Create a setter for light PPFD fields."""
    async def setter(coordinator, value):
        cached = coordinator._build_config_block(module, {})
        pp = cached.get("ppfdPeriod", [{"enabled": 1, "weekmask": 127}])
        if not pp:
            pp = [{"enabled": 1, "weekmask": 127}]
        pp[0][field] = int(value)
        cached["ppfdPeriod"] = pp
        await coordinator.async_send_config_field(module, cached)
    return setter


def _light_field_setter(module: str, field: str, cast=int):
    """Create a setter for a top-level light field."""
    async def setter(coordinator, value):
        block = coordinator._build_config_block(module, {field: cast(value)})
        await coordinator.async_send_config_field(module, block)
    return setter


def _fan_schedule_setter(module: str, field: str):
    async def setter(coordinator, value):
        cached = coordinator._build_config_block(module, {})
        tp = cached.get("timePeriod", [{"enabled": 1, "weekmask": 127}])
        if not tp:
            tp = [{"enabled": 1, "weekmask": 127}]
        tp[0][field] = int(value)
        tp[0].setdefault("enabled", 1)
        tp[0].setdefault("weekmask", 127)
        cached["timePeriod"] = tp
        await coordinator.async_send_config_field(module, cached)
    return setter


def _fan_cycle_setter(module: str, field: str):
    async def setter(coordinator, value):
        cached = coordinator._build_config_block(module, {})
        ct = cached.get("cycleTime", {"weekmask": 127})
        ct[field] = int(value)
        cached["cycleTime"] = ct
        await coordinator.async_send_config_field(module, cached)
    return setter


def _fan_field_setter(module: str, field: str):
    async def setter(coordinator, value):
        block = coordinator._build_config_block(module, {field: int(value)})
        await coordinator.async_send_config_field(module, block)
    return setter


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
        set_fn=lambda c, v: c.async_set_module_manual("fan", v > 0, int(v)),
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
        set_fn=lambda c, v: c.async_set_module_manual("light", v > 0, int(v)),
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
        set_fn=lambda c, v: c.async_set_module_manual("blower", v > 0, int(v)),
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
        set_fn=lambda c, v: c.async_set_module_manual("light2", v > 0, int(v)),
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
        set_fn=lambda c, v: c.async_set_module_manual("humidifier", v > 0, int(v)),
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


# ── Light 1 settings ────────────────────────────────────────────────────────
LIGHT_SETTING_DESCRIPTIONS: tuple[GGSNumberDescription, ...] = (
    GGSNumberDescription(
        key="light_schedule_brightness",
        name="Light 1 Schedule Brightness",
        icon="mdi:brightness-percent",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light_schedule_brightness,
        set_fn=_light_schedule_setter("light", "brightness"),
    ),
    GGSNumberDescription(
        key="light_fade_time",
        name="Light 1 Fade Time",
        icon="mdi:weather-sunset",
        native_min_value=0,
        native_max_value=240,
        native_step=1,
        native_unit_of_measurement="min",
        value_fn=lambda d: _seconds_to_minutes(d.light_fade_time),
        set_fn=lambda c, v: _light_schedule_setter("light", "fadeTime")(c, v * 60),
    ),
    GGSNumberDescription(
        key="light_ppfd_target",
        name="Light 1 PPFD Target",
        icon="mdi:white-balance-sunny",
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        native_unit_of_measurement="µmol/m²/s",
        value_fn=lambda d: d.light_ppfd_target,
        set_fn=_light_ppfd_setter("light", "brightness"),
    ),
    GGSNumberDescription(
        key="light_dimming_min",
        name="Light 1 Dimming Min",
        icon="mdi:brightness-4",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light_dimming_min,
        set_fn=_light_field_setter("light", "ppfdMinBrightness"),
    ),
    GGSNumberDescription(
        key="light_dimming_max",
        name="Light 1 Dimming Max",
        icon="mdi:brightness-7",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light_dimming_max,
        set_fn=_light_field_setter("light", "ppfdMaxBrightness"),
    ),
    GGSNumberDescription(
        key="light_dim_threshold",
        name="Light 1 Dim Threshold",
        icon="mdi:thermometer-alert",
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement="°C",
        value_fn=lambda d: d.light_dim_threshold,
        set_fn=_light_field_setter("light", "darkTemp", float),
    ),
    GGSNumberDescription(
        key="light_off_threshold",
        name="Light 1 Off Threshold",
        icon="mdi:thermometer-off",
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement="°C",
        value_fn=lambda d: d.light_off_threshold,
        set_fn=_light_field_setter("light", "offTemp", float),
    ),
)

# ── Light 2 settings ────────────────────────────────────────────────────────
LIGHT2_SETTING_DESCRIPTIONS: tuple[GGSNumberDescription, ...] = (
    GGSNumberDescription(
        key="light2_schedule_brightness",
        name="Light 2 Schedule Brightness",
        icon="mdi:brightness-percent",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light2_schedule_brightness,
        set_fn=_light_schedule_setter("light2", "brightness"),
    ),
    GGSNumberDescription(
        key="light2_fade_time",
        name="Light 2 Fade Time",
        icon="mdi:weather-sunset",
        native_min_value=0,
        native_max_value=240,
        native_step=1,
        native_unit_of_measurement="min",
        value_fn=lambda d: _seconds_to_minutes(d.light2_fade_time),
        set_fn=lambda c, v: _light_schedule_setter("light2", "fadeTime")(c, v * 60),
    ),
    GGSNumberDescription(
        key="light2_ppfd_target",
        name="Light 2 PPFD Target",
        icon="mdi:white-balance-sunny",
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        native_unit_of_measurement="µmol/m²/s",
        value_fn=lambda d: d.light2_ppfd_target,
        set_fn=_light_ppfd_setter("light2", "brightness"),
    ),
    GGSNumberDescription(
        key="light2_dimming_min",
        name="Light 2 Dimming Min",
        icon="mdi:brightness-4",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light2_dimming_min,
        set_fn=_light_field_setter("light2", "ppfdMinBrightness"),
    ),
    GGSNumberDescription(
        key="light2_dimming_max",
        name="Light 2 Dimming Max",
        icon="mdi:brightness-7",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.light2_dimming_max,
        set_fn=_light_field_setter("light2", "ppfdMaxBrightness"),
    ),
    GGSNumberDescription(
        key="light2_dim_threshold",
        name="Light 2 Dim Threshold",
        icon="mdi:thermometer-alert",
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement="°C",
        value_fn=lambda d: d.light2_dim_threshold,
        set_fn=_light_field_setter("light2", "darkTemp", float),
    ),
    GGSNumberDescription(
        key="light2_off_threshold",
        name="Light 2 Off Threshold",
        icon="mdi:thermometer-off",
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement="°C",
        value_fn=lambda d: d.light2_off_threshold,
        set_fn=_light_field_setter("light2", "offTemp", float),
    ),
)

# ── Fan/Blower settings generator ───────────────────────────────────────────
def _fan_settings(module: str, prefix: str, name: str, speed_max: int, has_oscillation: bool):
    """Generate number descriptions for one fan/blower device."""
    descs = [
        GGSNumberDescription(
            key=f"{prefix}_max_speed",
            name=f"{name} Speed",
            icon="mdi:speedometer",
            native_min_value=1,
            native_max_value=speed_max,
            native_step=1,
            value_fn=lambda d, p=prefix: getattr(d, f"{p}_max_speed"),
            set_fn=_fan_field_setter(module, "maxSpeed"),
        ),
        GGSNumberDescription(
            key=f"{prefix}_min_speed",
            name=f"{name} Standby Speed",
            icon="mdi:speedometer-slow",
            native_min_value=0,
            native_max_value=speed_max,
            native_step=1,
            value_fn=lambda d, p=prefix: getattr(d, f"{p}_min_speed"),
            set_fn=_fan_field_setter(module, "minSpeed"),
        ),
        GGSNumberDescription(
            key=f"{prefix}_cycle_run",
            name=f"{name} Cycle Run Time",
            icon="mdi:timer-play",
            native_min_value=0,
            native_max_value=1440,
            native_step=1,
            native_unit_of_measurement="min",
            value_fn=lambda d, p=prefix: _seconds_to_minutes(getattr(d, f"{p}_cycle_run")),
            set_fn=lambda c, v, m=module: _fan_cycle_setter(m, "openDur")(c, v * 60),
        ),
        GGSNumberDescription(
            key=f"{prefix}_cycle_off",
            name=f"{name} Cycle Off Time",
            icon="mdi:timer-pause",
            native_min_value=0,
            native_max_value=1440,
            native_step=1,
            native_unit_of_measurement="min",
            value_fn=lambda d, p=prefix: _seconds_to_minutes(getattr(d, f"{p}_cycle_off")),
            set_fn=lambda c, v, m=module: _fan_cycle_setter(m, "closeDur")(c, v * 60),
        ),
        GGSNumberDescription(
            key=f"{prefix}_cycle_times",
            name=f"{name} Cycle Count",
            icon="mdi:repeat",
            native_min_value=1,
            native_max_value=100,
            native_step=1,
            value_fn=lambda d, p=prefix: getattr(d, f"{p}_cycle_times"),
            set_fn=_fan_cycle_setter(module, "times"),
        ),
    ]
    if has_oscillation:
        descs.append(GGSNumberDescription(
            key=f"{prefix}_shake_level",
            name=f"{name} Oscillation Level",
            icon="mdi:rotate-3d-variant",
            native_min_value=0,
            native_max_value=10,
            native_step=1,
            value_fn=lambda d: d.fan_shake_level,
            set_fn=_fan_field_setter(module, "shakeLevel"),
        ))
    return tuple(descs)


FAN_SETTING_DESCRIPTIONS = _fan_settings("fan", "fan", "Fan", 10, True)
BLOWER_SETTING_DESCRIPTIONS = _fan_settings("blower", "blower", "Blower", 100, False)

# ── Humidifier cycle settings ───────────────────────────────────────────────
HUMIDIFIER_SETTING_DESCRIPTIONS: tuple[GGSNumberDescription, ...] = (
    GGSNumberDescription(
        key="humidifier_cycle_run",
        name="Humidifier Cycle Run Time",
        icon="mdi:timer-play",
        native_min_value=0,
        native_max_value=1440,
        native_step=1,
        native_unit_of_measurement="min",
        value_fn=lambda d: _seconds_to_minutes(d.humidifier_cycle_run),
        set_fn=lambda c, v: _fan_cycle_setter("humidifier", "openDur")(c, v * 60),
    ),
    GGSNumberDescription(
        key="humidifier_cycle_off",
        name="Humidifier Cycle Off Time",
        icon="mdi:timer-pause",
        native_min_value=0,
        native_max_value=1440,
        native_step=1,
        native_unit_of_measurement="min",
        value_fn=lambda d: _seconds_to_minutes(d.humidifier_cycle_off),
        set_fn=lambda c, v: _fan_cycle_setter("humidifier", "closeDur")(c, v * 60),
    ),
    GGSNumberDescription(
        key="humidifier_cycle_times",
        name="Humidifier Cycle Count",
        icon="mdi:repeat",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        value_fn=lambda d: d.humidifier_cycle_times,
        set_fn=_fan_cycle_setter("humidifier", "times"),
    ),
)

# ── Combined descriptions ───────────────────────────────────────────────────
NUMBER_DESCRIPTIONS_ALL: tuple[GGSNumberDescription, ...] = (
    *NUMBER_DESCRIPTIONS,
    *LIGHT_SETTING_DESCRIPTIONS,
    *LIGHT2_SETTING_DESCRIPTIONS,
    *FAN_SETTING_DESCRIPTIONS,
    *BLOWER_SETTING_DESCRIPTIONS,
    *HUMIDIFIER_SETTING_DESCRIPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerGGSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GGSNumberEntity(coordinator, entry, desc) for desc in NUMBER_DESCRIPTIONS_ALL
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
