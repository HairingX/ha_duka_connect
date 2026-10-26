"""Choices of the unit: the fan speed, which way the air moves, and which timed mode runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from duka_connect import Key, PointKey, Speed, TimerMode, VentilationMode
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import DukaConfigEntry, DukaData
from .entity import DukaEntityDescription, DukaPointEntity, describe

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaSelectDescription(DukaEntityDescription, SelectEntityDescription):
    """A select of one state that can be written; its options are the state's names."""

    states: type[IntEnum]


def _select(point: Key[Any], states: type[IntEnum]) -> DukaSelectDescription:
    return DukaSelectDescription(
        key=str(point),
        translation_key=str(point),
        point=point,
        states=states,
        options=[state.name.lower() for state in states],
    )


SELECTS: tuple[DukaSelectDescription, ...] = (
    _select(PointKey.SPEED, Speed),
    _select(PointKey.VENTILATION_MODE, VentilationMode),
    _select(PointKey.TIMER_MODE, TimerMode),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a select for every described state the unit has."""
    data = entry.runtime_data
    async_add_entities(DukaSelect(data, d) for d in describe(data, SELECTS))


class DukaSelect(DukaPointEntity, SelectEntity):
    """A state the unit is set to."""

    def __init__(self, data: DukaData, description: DukaSelectDescription) -> None:
        self._states = description.states
        super().__init__(data, description)

    def _show(self) -> None:
        current = self._current(self._key)
        self._attr_current_option = (
            current.name.lower() if isinstance(current, IntEnum) else None
        )

    async def async_select_option(self, option: str) -> None:
        """Set the unit to the chosen state."""
        await self._write([(self._key, self._states[option.upper()])])
