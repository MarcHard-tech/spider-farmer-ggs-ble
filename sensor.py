"""Sensor entities for Spider Farmer GGS Controller."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GGSData, SpiderFarmerGGSCoordinator


@dataclass
class GGSSensorDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a value accessor."""
    value_fn: Callable[[GGSData], Optional[float | int | str | bool]] = lambda d: None


# ── Environment sensors ──────────────────────────────────────────────────────

ENVIRONMENT_SENSORS: tuple[GGSSensorDescription, ...] = (
    GGSSensorDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.temperature,
    ),
    GGSSensorDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.humidity,
    ),
    GGSSensorDescription(
        key="vpd",
        name="VPD",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kPa",
        icon="mdi:water-thermometer",
        value_fn=lambda d: d.vpd,
    ),
    GGSSensorDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ppm",
        value_fn=lambda d: d.co2,
    ),
    GGSSensorDescription(
        key="ppfd",
        name="PPFD",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="µmol/m²/s",
        icon="mdi:white-balance-sunny",
        value_fn=lambda d: d.ppfd,
    ),
    GGSSensorDescription(
        key="is_day_env_target",
        name="Environment On Target",
        icon="mdi:target",
        value_fn=lambda d: "Yes" if d.is_day_env_target else "No" if d.is_day_env_target is not None else None,
    ),
)

# ── Soil probe sensors ───────────────────────────────────────────────────────

def _soil_probe_sensors(probe_num: int) -> tuple[GGSSensorDescription, ...]:
    """Generate sensor descriptions for a single soil probe."""
    attr = f"soil_probe_{probe_num}"
    return (
        GGSSensorDescription(
            key=f"soil{probe_num}_temp",
            name=f"Soil Probe {probe_num} Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            icon="mdi:thermometer",
            value_fn=lambda d, a=attr: getattr(d, a).temperature,
        ),
        GGSSensorDescription(
            key=f"soil{probe_num}_wc",
            name=f"Soil Probe {probe_num} Water Content",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            icon="mdi:water-percent",
            value_fn=lambda d, a=attr: getattr(d, a).water_content,
        ),
        GGSSensorDescription(
            key=f"soil{probe_num}_ec",
            name=f"Soil Probe {probe_num} EC",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="mS/cm",
            icon="mdi:flash",
            value_fn=lambda d, a=attr: getattr(d, a).ec,
        ),
    )


SOIL_PROBE_SENSORS: tuple[GGSSensorDescription, ...] = (
    *_soil_probe_sensors(1),
    *_soil_probe_sensors(2),
    *_soil_probe_sensors(3),
)

# ── Soil average sensors ─────────────────────────────────────────────────────

SOIL_AVG_SENSORS: tuple[GGSSensorDescription, ...] = (
    GGSSensorDescription(
        key="soil_avg_temp",
        name="Soil Average Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        value_fn=lambda d: d.soil_avg_temp,
    ),
    GGSSensorDescription(
        key="soil_avg_wc",
        name="Soil Average Water Content",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        value_fn=lambda d: d.soil_avg_wc,
    ),
    GGSSensorDescription(
        key="soil_avg_ec",
        name="Soil Average EC",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mS/cm",
        icon="mdi:flash",
        value_fn=lambda d: d.soil_avg_ec,
    ),
)

# ── Grow plan sensors ────────────────────────────────────────────────────────

PLAN_SENSORS: tuple[GGSSensorDescription, ...] = (
    GGSSensorDescription(
        key="plan_active",
        name="Grow Plan Active",
        icon="mdi:calendar-check",
        value_fn=lambda d: "Running" if d.plan_active else "Stopped" if d.plan_active is not None else None,
    ),
    GGSSensorDescription(
        key="plan_days_remaining",
        name="Grow Plan Days Remaining",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="days",
        icon="mdi:calendar-clock",
        value_fn=lambda d: d.plan_days_remaining,
    ),
    GGSSensorDescription(
        key="plan_days_elapsed",
        name="Grow Plan Days Elapsed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="days",
        icon="mdi:calendar-range",
        value_fn=lambda d: d.plan_days_elapsed,
    ),
    GGSSensorDescription(
        key="plan_total_days",
        name="Grow Plan Total Days",
        native_unit_of_measurement="days",
        icon="mdi:calendar-text",
        value_fn=lambda d: d.plan_total_days,
    ),
    GGSSensorDescription(
        key="plan_progress",
        name="Grow Plan Progress",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:progress-check",
        value_fn=lambda d: d.plan_progress,
    ),
)

# ── Alarm and operation log sensors ──────────────────────────────────────────

EVENT_SENSORS: tuple[GGSSensorDescription, ...] = (
    GGSSensorDescription(
        key="last_alarm",
        name="Last Alarm",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:alarm-light",
        value_fn=lambda d: d.alarm_time,
    ),
    GGSSensorDescription(
        key="last_alarm_type",
        name="Last Alarm Type",
        icon="mdi:alert-circle",
        value_fn=lambda d: d.alarm_type,
    ),
    GGSSensorDescription(
        key="last_operation",
        name="Last Operation",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:history",
        value_fn=lambda d: d.oplog_time,
    ),
    GGSSensorDescription(
        key="last_operation_mode",
        name="Last Operation Mode",
        icon="mdi:cog",
        value_fn=lambda d: d.oplog_mode_type,
    ),
)

# ── All sensor descriptions combined ─────────────────────────────────────────

SENSOR_DESCRIPTIONS: tuple[GGSSensorDescription, ...] = (
    *ENVIRONMENT_SENSORS,
    *SOIL_PROBE_SENSORS,
    *SOIL_AVG_SENSORS,
    *PLAN_SENSORS,
    *EVENT_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpiderFarmerGGSCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GGSSensorEntity(coordinator, entry, desc) for desc in SENSOR_DESCRIPTIONS
    )


class GGSSensorEntity(CoordinatorEntity[SpiderFarmerGGSCoordinator], SensorEntity):
    """A sensor entity for the GGS controller."""

    entity_description: GGSSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SpiderFarmerGGSCoordinator,
        entry: ConfigEntry,
        description: GGSSensorDescription,
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
    def native_value(self) -> Optional[float | int | str]:
        return self.entity_description.value_fn(self.coordinator.data)
