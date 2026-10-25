"""Whether the filter needs replacing, and whether boost runs."""

from __future__ import annotations

from dataclasses import dataclass

from duka_connect import Key, PointKey
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import DukaConfigEntry, DukaData
from .entity import DukaEntityDescription, DukaPointEntity, describe

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
    async_add_entities(DukaBinarySensor(data, d) for d in describe(data, BINARY_SENSORS))


class DukaBinarySensor(DukaPointEntity, BinarySensorEntity):
    """A flag of the unit."""

    def __init__(self, data: DukaData, description: DukaBinarySensorDescription) -> None:
        self._flag = description.point
        super().__init__(data, description)

    def _show(self) -> None:
        self._attr_is_on = self._current(self._flag)
