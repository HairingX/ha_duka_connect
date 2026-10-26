"""Actions on the unit: reset its alarms, its filter timer and its fan speeds, and set its clock."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from duka_connect import Key, PointKey
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import SET_CLOCK_KEY
from .data import DukaConfigEntry, DukaData
from .entity import DukaEntity, DukaEntityDescription, shown

# The client sends writes in order, so actions are passed to it as they come.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaButtonDescription(DukaEntityDescription, ButtonEntityDescription):
    """A button that sends one command; shown where the unit has `requires`, if given.

    A command has no value to read, so whether the unit has it is told by a point it acts on.
    """

    point: Key[bool]
    requires: Key[Any] | None = None


BUTTONS: tuple[DukaButtonDescription, ...] = (
    DukaButtonDescription(
        key=str(PointKey.RESET_FILTER_TIMER),
        translation_key=str(PointKey.RESET_FILTER_TIMER),
        point=PointKey.RESET_FILTER_TIMER,
        entity_category=EntityCategory.CONFIG,
    ),
    DukaButtonDescription(
        key=str(PointKey.RESET_ALARMS),
        translation_key=str(PointKey.RESET_ALARMS),
        point=PointKey.RESET_ALARMS,
        entity_category=EntityCategory.CONFIG,
    ),
    DukaButtonDescription(
        key=str(PointKey.RESTORE_FAN_SPEEDS),
        translation_key=str(PointKey.RESTORE_FAN_SPEEDS),
        point=PointKey.RESTORE_FAN_SPEEDS,
        requires=PointKey.SUPPLY_SPEED_1,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a button for every command the unit has, and one to set its clock."""
    data = entry.runtime_data
    entities: list[ButtonEntity] = [
        DukaButton(data, d)
        for d in BUTTONS
        if d.requires is None or shown(data, d.requires)
    ]
    if shown(data, PointKey.CLOCK_TIME) and shown(data, PointKey.CLOCK_DATE):
        entities.append(DukaSetClock(data))
    async_add_entities(entities)


class DukaButton(DukaEntity, ButtonEntity):
    """A command, usable while the unit answers."""

    def __init__(self, data: DukaData, description: DukaButtonDescription) -> None:
        self.entity_description = description
        self._command = description.point
        super().__init__(data, str(description.point))

    async def async_press(self) -> None:
        """Send the command; what it changes is read back."""
        await self._write([(self._command, True)])


class DukaSetClock(DukaEntity, ButtonEntity):
    """Set the unit's clock and calendar to Home Assistant's local time.

    The unit's weekly schedule runs by its own clock, which has no time zone and drifts.
    """

    _attr_translation_key = SET_CLOCK_KEY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: DukaData) -> None:
        super().__init__(data, SET_CLOCK_KEY)

    async def async_press(self) -> None:
        """Write the local date and time, to the second, in one request."""
        now = dt_util.now().replace(microsecond=0)
        await self._write([(PointKey.CLOCK_TIME, now.time()), (PointKey.CLOCK_DATE, now.date())])
