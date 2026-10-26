"""Measurements of the unit, its alarm, timers and firmware."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
from homeassistant.util import dt as dt_util

from .const import CLOCK_KEY, CLOCK_OFFSET_KEY
from .data import DukaConfigEntry, DukaData
from .entity import DukaEntity, DukaEntityDescription, DukaPointEntity, describe, shown

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
    """Add a sensor for every described point the unit has, and its clock where it has one."""
    data = entry.runtime_data
    entities: list[SensorEntity] = [DukaSensor(data, d) for d in describe(data, SENSORS)]
    if shown(data, PointKey.CLOCK_TIME) and shown(data, PointKey.CLOCK_DATE):
        entities += [DukaClock(data), DukaClockOffset(data)]
    async_add_entities(entities)


class DukaSensor(DukaPointEntity, SensorEntity):
    """A point's value; a state by its name."""

    def __init__(self, data: DukaData, description: DukaSensorDescription) -> None:
        super().__init__(data, description)

    def _show(self) -> None:
        current = self._current(self._key)
        self._attr_native_value = (
            current.name.lower() if isinstance(current, IntEnum) else current
        )


class _UnitClock(DukaEntity, SensorEntity):
    """The unit's clock and calendar, read as Home Assistant's local time.

    The unit's clock has no time zone; *Set clock* writes Home Assistant's local time to it.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def _watched(self) -> tuple[Key[Any], ...]:
        return (PointKey.CLOCK_TIME, PointKey.CLOCK_DATE)

    def _unit_time(self) -> datetime | None:
        clock = self._current(PointKey.CLOCK_TIME)
        calendar = self._current(PointKey.CLOCK_DATE)
        if clock is None or calendar is None:
            return None
        return datetime.combine(calendar, clock, tzinfo=dt_util.get_default_time_zone())


class DukaClock(_UnitClock):
    """The date and time the unit's clock shows, as it was when last read."""

    _attr_translation_key = CLOCK_KEY
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, data: DukaData) -> None:
        super().__init__(data, CLOCK_KEY)

    def _show(self) -> None:
        self._attr_native_value = self._unit_time()


class DukaClockOffset(_UnitClock):
    """How many seconds the unit's clock is ahead of Home Assistant's, when it was last read."""

    _attr_translation_key = CLOCK_OFFSET_KEY
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, data: DukaData) -> None:
        super().__init__(data, CLOCK_OFFSET_KEY)

    def _show(self) -> None:
        unit_time = self._unit_time()
        read = self._client.value(PointKey.CLOCK_TIME)
        if unit_time is None or read is None or read.timestamp is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = round(unit_time.timestamp() - read.timestamp)
