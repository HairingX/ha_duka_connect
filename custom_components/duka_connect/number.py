"""Settings of the unit that are numbers."""

from __future__ import annotations

from dataclasses import dataclass

from duka_connect import Key, PointKey
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import DukaConfigEntry, DukaData
from .entity import DukaEntityDescription, DukaPointEntity, describe
from .speed import manual_to_percentage, percentage_to_manual

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaNumberDescription(DukaEntityDescription, NumberEntityDescription):
    """A number of one setting; its limits are the point's, or 0 to 100 % for a manual speed."""

    point: Key[int]
    percentage: bool = False


def _duration(point: Key[int], unit: UnitOfTime) -> DukaNumberDescription:
    return DukaNumberDescription(
        key=str(point),
        translation_key=str(point),
        point=point,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=unit,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    )


def _fan_speed(point: Key[int]) -> DukaNumberDescription:
    return DukaNumberDescription(
        key=str(point),
        translation_key=str(point),
        point=point,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    )


NUMBERS: tuple[DukaNumberDescription, ...] = (
    DukaNumberDescription(
        key=str(PointKey.MANUAL_SPEED),
        translation_key=str(PointKey.MANUAL_SPEED),
        point=PointKey.MANUAL_SPEED,
        percentage=True,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
    DukaNumberDescription(
        key=str(PointKey.HUMIDITY_THRESHOLD),
        translation_key=str(PointKey.HUMIDITY_THRESHOLD),
        point=PointKey.HUMIDITY_THRESHOLD,
        device_class=NumberDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    DukaNumberDescription(
        key=str(PointKey.BOOST_OFF_DELAY),
        translation_key=str(PointKey.BOOST_OFF_DELAY),
        point=PointKey.BOOST_OFF_DELAY,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    _duration(PointKey.NIGHT_TIMER, UnitOfTime.MINUTES),
    _duration(PointKey.PARTY_TIMER, UnitOfTime.MINUTES),
    _duration(PointKey.FILTER_INTERVAL, UnitOfTime.DAYS),
    DukaNumberDescription(
        key=str(PointKey.ANALOG_SENSOR_THRESHOLD),
        translation_key=str(PointKey.ANALOG_SENSOR_THRESHOLD),
        point=PointKey.ANALOG_SENSOR_THRESHOLD,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    *(
        _fan_speed(point)
        for point in (
            PointKey.SUPPLY_SPEED_1, PointKey.EXHAUST_SPEED_1,
            PointKey.SUPPLY_SPEED_2, PointKey.EXHAUST_SPEED_2,
            PointKey.SUPPLY_SPEED_3, PointKey.EXHAUST_SPEED_3,
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a number for every described setting the unit has."""
    data = entry.runtime_data
    async_add_entities(DukaNumber(data, d) for d in describe(data, NUMBERS))


class DukaNumber(DukaPointEntity, NumberEntity):
    """A setting that is a whole number within the point's limits."""

    def __init__(self, data: DukaData, description: DukaNumberDescription) -> None:
        self._setting = description.point
        self._percentage = description.percentage
        point = data.client.points[str(description.point)]
        self._attr_native_min_value = 0.0 if self._percentage else float(point.minimum or 0)
        self._attr_native_max_value = 100.0 if self._percentage else float(point.maximum or 255)
        self._attr_native_step = 1
        super().__init__(data, description)

    def _show(self) -> None:
        current = self._current(self._setting)
        shown = manual_to_percentage(current) if self._percentage and current is not None else current
        self._attr_native_value = None if shown is None else float(shown)

    async def async_set_native_value(self, value: float) -> None:
        """Write the setting."""
        await self._write(
            [(self._setting, percentage_to_manual(value) if self._percentage else round(value))]
        )

