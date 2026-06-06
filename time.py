"""Time entities for Spider Farmer GGS Controller (schedule start/end times)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Callable, Coroutine, Optional

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GGSData, SpiderFarmerGGSCoordinator


def _seconds_to_time(seconds: Optional[int]) -> Optional[time]:
    """Convert seconds since midnight to a time object."""
    if seconds is None:
        return None
    seconds = seconds % 86400
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return time(h, m)


def _time_to_seconds(t: time) -> int:
    """Convert a time object to seconds since midnight."""
    return t.hour * 3600 + t.minute * 60


@dataclass
class GGSTimeDescription(TimeEntityDescription):
    """Extends TimeEntityDescription with accessors and a setter."""
    value_fn: Callable[[GGSData], Optional[int]] = lambda d: None  # returns seconds
    set_fn: Callable[..., Coroutine] = None


def _light_time_setter(module: str, period_key: str, field: str):
    """Create a setter for a light timePeriod/ppfdPeriod time field."""
    async def setter(coordinator, seconds):
        cached = coordinator._build_config_block(module, {})
        periods = cached.get(period_key, [{"enabled": 1, "weekmask": 127}])
        if not periods:
            periods = [{"enabled": 1, "weekmask": 127}]
        periods[0][field] = seconds
        cached[period_key] = periods
        await coordinator.async_send_config_field(module, cached)
    return setter


def _fan_time_setter(module: str, period_type: str, field: str):
    """Create a setter for fan/blower/humidifier time fields."""
    async def setter(coordinator, seconds):
        cached = coordinator._build_config_block(module, {})
        if period_type == "timePeriod":
            tp = cached.get("timePeriod", [{"enabled": 1, "weekmask": 127}])
            if not tp:
                tp = [{"enabled": 1, "weekmask": 127}]
            tp[0][field] = seconds
            tp[0].setdefault("enabled", 1)
            tp[0].setdefault("weekmask", 127)
            cached["timePeriod"] = tp
        elif period_type == "cycleTime":
            ct = cached.get("cycleTime", {"weekmask": 127})
            ct[field] = seconds
            cached["cycleTime"] = ct
        await coordinator.async_send_config_field(module, cached)
    return setter


TIME_DESCRIPTIONS: tuple[GGSTimeDescription, ...] = (
    # ── Light 1 ──────────────────────────────────────────────────────────────
    GGSTimeDescription(
        key="light_schedule_start",
        name="Light 1 Schedule Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.light_schedule_start,
        set_fn=_light_time_setter("light", "timePeriod", "startTime"),
    ),
    GGSTimeDescription(
        key="light_schedule_end",
        name="Light 1 Schedule End",
        icon="mdi:clock-end",
        value_fn=lambda d: d.light_schedule_end,
        set_fn=_light_time_setter("light", "timePeriod", "endTime"),
    ),
    GGSTimeDescription(
        key="light_ppfd_start",
        name="Light 1 PPFD Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.light_ppfd_start,
        set_fn=_light_time_setter("light", "ppfdPeriod", "startTime"),
    ),
    GGSTimeDescription(
        key="light_ppfd_end",
        name="Light 1 PPFD End",
        icon="mdi:clock-end",
        value_fn=lambda d: d.light_ppfd_end,
        set_fn=_light_time_setter("light", "ppfdPeriod", "endTime"),
    ),
    # ── Light 2 ──────────────────────────────────────────────────────────────
    GGSTimeDescription(
        key="light2_schedule_start",
        name="Light 2 Schedule Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.light2_schedule_start,
        set_fn=_light_time_setter("light2", "timePeriod", "startTime"),
    ),
    GGSTimeDescription(
        key="light2_schedule_end",
        name="Light 2 Schedule End",
        icon="mdi:clock-end",
        value_fn=lambda d: d.light2_schedule_end,
        set_fn=_light_time_setter("light2", "timePeriod", "endTime"),
    ),
    GGSTimeDescription(
        key="light2_ppfd_start",
        name="Light 2 PPFD Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.light2_ppfd_start,
        set_fn=_light_time_setter("light2", "ppfdPeriod", "startTime"),
    ),
    GGSTimeDescription(
        key="light2_ppfd_end",
        name="Light 2 PPFD End",
        icon="mdi:clock-end",
        value_fn=lambda d: d.light2_ppfd_end,
        set_fn=_light_time_setter("light2", "ppfdPeriod", "endTime"),
    ),
    # ── Fan ───────────────────────────────────────────────────────────────────
    GGSTimeDescription(
        key="fan_schedule_start",
        name="Fan Schedule Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.fan_schedule_start,
        set_fn=_fan_time_setter("fan", "timePeriod", "startTime"),
    ),
    GGSTimeDescription(
        key="fan_schedule_end",
        name="Fan Schedule End",
        icon="mdi:clock-end",
        value_fn=lambda d: d.fan_schedule_end,
        set_fn=_fan_time_setter("fan", "timePeriod", "endTime"),
    ),
    GGSTimeDescription(
        key="fan_cycle_start",
        name="Fan Cycle Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.fan_cycle_start,
        set_fn=_fan_time_setter("fan", "cycleTime", "startTime"),
    ),
    # ── Blower ────────────────────────────────────────────────────────────────
    GGSTimeDescription(
        key="blower_schedule_start",
        name="Blower Schedule Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.blower_schedule_start,
        set_fn=_fan_time_setter("blower", "timePeriod", "startTime"),
    ),
    GGSTimeDescription(
        key="blower_schedule_end",
        name="Blower Schedule End",
        icon="mdi:clock-end",
        value_fn=lambda d: d.blower_schedule_end,
        set_fn=_fan_time_setter("blower", "timePeriod", "endTime"),
    ),
    GGSTimeDescription(
        key="blower_cycle_start",
        name="Blower Cycle Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.blower_cycle_start,
        set_fn=_fan_time_setter("blower", "cycleTime", "startTime"),
    ),
    # ── Humidifier ────────────────────────────────────────────────────────────
    GGSTimeDescription(
        key="humidifier_timeslot_start",
        name="Humidifier Time Slot Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.humidifier_schedule_start,
        set_fn=_fan_time_setter("humidifier", "timePeriod", "startTime"),
    ),
    GGSTimeDescription(
        key="humidifier_timeslot_end",
        name="Humidifier Time Slot End",
        icon="mdi:clock-end",
        value_fn=lambda d: d.humidifier_schedule_end,
        set_fn=_fan_time_setter("humidifier", "timePeriod", "endTime"),
    ),
    GGSTimeDescription(
        key="humidifier_cycle_start",
        name="Humidifier Cycle Start",
        icon="mdi:clock-start",
        value_fn=lambda d: d.humidifier_cycle_start,
        set_fn=_fan_time_setter("humidifier", "cycleTime", "startTime"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerGGSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GGSTimeEntity(coordinator, entry, desc) for desc in TIME_DESCRIPTIONS
    )


class GGSTimeEntity(CoordinatorEntity[SpiderFarmerGGSCoordinator], TimeEntity):
    """A time entity for schedule start/end times."""

    entity_description: GGSTimeDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SpiderFarmerGGSCoordinator,
        entry: ConfigEntry,
        description: GGSTimeDescription,
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
        return (
            self.coordinator.last_update_success
            and self.entity_description.value_fn(self.coordinator.data) is not None
        )

    @property
    def native_value(self) -> Optional[time]:
        seconds = self.entity_description.value_fn(self.coordinator.data)
        return _seconds_to_time(seconds)

    async def async_set_value(self, value: time) -> None:
        seconds = _time_to_seconds(value)
        await self.entity_description.set_fn(self.coordinator, seconds)
