"""Measurements of the unit, its alarm, timers and firmware."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from duka_connect import AlarmLevel, Key, PointKey
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import DukaConfigEntry, DukaData
from .entity import DukaEntityDescription, DukaPointEntity, describe

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaSensorDescription(DukaEntityDescription, SensorEntityDescription):
    """A sensor of one point."""


def _sensor(point: Key[Any], **kwargs: Any) -> DukaSensorDescription:
    return DukaSensorDescription(key=str(point), translation_key=str(point), point=point, **kwargs)


SENSORS: tuple[DukaSensorDescription, ...] = (
    _sensor(
        PointKey.HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    _sensor(
        PointKey.FAN_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    ),
    _sensor(
        PointKey.RTC_BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _sensor(
        PointKey.FILTER_TIMER,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
    ),
    _sensor(
        PointKey.TIMER_COUNTDOWN,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
    ),
    _sensor(
        PointKey.OPERATING_TIME,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _sensor(
        PointKey.ALARM,
        device_class=SensorDeviceClass.ENUM,
        options=[level.name.lower() for level in AlarmLevel],
    ),
    _sensor(PointKey.FIRMWARE_VERSION, entity_category=EntityCategory.DIAGNOSTIC),
    _sensor(
        PointKey.FIRMWARE_DATE,
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _sensor(
        PointKey.UNIT_TYPE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _sensor(
        PointKey.FAN2_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    ),
    _sensor(
        PointKey.ANALOG_SENSOR_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    _sensor(
        PointKey.IP_ADDRESS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a sensor for every described point the unit has."""
    data = entry.runtime_data
    async_add_entities(DukaSensor(data, d) for d in describe(data, SENSORS))


class DukaSensor(DukaPointEntity, SensorEntity):
    """A point's value; a state by its name."""

    def __init__(self, data: DukaData, description: DukaSensorDescription) -> None:
        super().__init__(data, description)

    def _show(self) -> None:
        current = self._current(self._key)
        self._attr_native_value = (
            current.name.lower() if isinstance(current, IntEnum) else current
        )
