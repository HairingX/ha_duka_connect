"""Settings that are numbers: the humidity that starts boost, how long boost runs on, and the
voltage under which the clock battery counts as low."""

from __future__ import annotations

from dataclasses import dataclass

from duka_connect import Key, PointKey
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BATTERY_LOW_KEY
from .data import DukaConfigEntry, DukaData
from .entity import DukaEntityDescription, DukaPointEntity, describe, device_info, shown

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaNumberDescription(DukaEntityDescription, NumberEntityDescription):
    """A number of one setting; its limits are the point's."""

    point: Key[int]


NUMBERS: tuple[DukaNumberDescription, ...] = (
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a number for every described setting the unit has."""
    data = entry.runtime_data
    entities: list[NumberEntity] = [DukaNumber(data, d) for d in describe(data, NUMBERS)]
    if shown(data, PointKey.RTC_BATTERY_VOLTAGE):
        entities.append(DukaBatteryLowThreshold(data))
    async_add_entities(entities)


class DukaNumber(DukaPointEntity, NumberEntity):
    """A setting that is a whole number within the point's limits."""

    def __init__(self, data: DukaData, description: DukaNumberDescription) -> None:
        self._setting = description.point
        point = data.client.points[str(description.point)]
        self._attr_native_min_value = float(point.minimum or 0)
        self._attr_native_max_value = float(point.maximum or 255)
        self._attr_native_step = 1
        super().__init__(data, description)

    def _show(self) -> None:
        current = self._current(self._setting)
        self._attr_native_value = None if current is None else float(current)

    async def async_set_native_value(self, value: float) -> None:
        """Write the setting."""
        await self._write([(self._setting, round(value))])


class DukaBatteryLowThreshold(RestoreNumber):
    """The voltage under which the clock battery counts as low; kept by Home Assistant.

    The unit has no such setting, so the value lives in Home Assistant and survives a restart.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = f"{BATTERY_LOW_KEY}_threshold"
    _attr_device_class = NumberDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_native_min_value = 2000
    _attr_native_max_value = 3300
    _attr_native_step = 50
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: DukaData) -> None:
        self._data = data
        self._attr_unique_id = f"{data.name}_{BATTERY_LOW_KEY}_threshold"
        self._attr_device_info = device_info(data)
        self._attr_native_value = float(data.battery_low)
        data.unique_ids.add(self._attr_unique_id)

    async def async_added_to_hass(self) -> None:
        """Take the limit Home Assistant kept, if there is one."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            await self.async_set_native_value(last.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the limit."""
        self._attr_native_value = value
        self._data.set_battery_low(round(value))
        self.async_write_ha_state()
