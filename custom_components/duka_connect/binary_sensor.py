"""Whether the filter needs replacing, whether boost runs, and whether the clock battery is low."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from duka_connect import Key, PointKey
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BATTERY_LOW_KEY
from .data import DukaConfigEntry, DukaData
from .entity import DukaEntity, DukaEntityDescription, DukaPointEntity, describe, shown

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaBinarySensorDescription(DukaEntityDescription, BinarySensorEntityDescription):
    """A binary sensor of one flag."""

    point: Key[bool]


BINARY_SENSORS: tuple[DukaBinarySensorDescription, ...] = (
    DukaBinarySensorDescription(
        key=str(PointKey.FILTER_REPLACE),
        translation_key=str(PointKey.FILTER_REPLACE),
        point=PointKey.FILTER_REPLACE,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    DukaBinarySensorDescription(
        key=str(PointKey.BOOST),
        translation_key=str(PointKey.BOOST),
        point=PointKey.BOOST,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a binary sensor for every described flag the unit has."""
    data = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        DukaBinarySensor(data, d) for d in describe(data, BINARY_SENSORS)
    ]
    if shown(data, PointKey.RTC_BATTERY_VOLTAGE):
        entities.append(DukaBatteryLow(data))
    async_add_entities(entities)


class DukaBinarySensor(DukaPointEntity, BinarySensorEntity):
    """A flag of the unit."""

    def __init__(self, data: DukaData, description: DukaBinarySensorDescription) -> None:
        self._flag = description.point
        super().__init__(data, description)

    def _show(self) -> None:
        self._attr_is_on = self._current(self._flag)


class DukaBatteryLow(DukaEntity, BinarySensorEntity):
    """On while the clock battery's voltage is under the limit the user sets."""

    _attr_translation_key = BATTERY_LOW_KEY
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, data: DukaData) -> None:
        self._data = data
        super().__init__(data, BATTERY_LOW_KEY)

    def _watched(self) -> tuple[Key[Any], ...]:
        return (PointKey.RTC_BATTERY_VOLTAGE,)

    def _show(self) -> None:
        voltage = self._current(PointKey.RTC_BATTERY_VOLTAGE)
        self._attr_is_on = None if voltage is None else voltage < self._data.battery_low

    async def async_added_to_hass(self) -> None:
        """Follow the voltage, whether the unit answers, and the limit."""
        self._data.battery_low_listeners.append(self._limit_changed)
        self.async_on_remove(lambda: self._data.battery_low_listeners.remove(self._limit_changed))
        await super().async_added_to_hass()

    @callback
    def _limit_changed(self) -> None:
        self._changed()
