"""Settings that are on or off: whether humidity may start boost."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from duka_connect import Key, PointKey
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import DukaConfigEntry, DukaData
from .entity import DukaEntityDescription, DukaPointEntity, describe

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaSwitchDescription(DukaEntityDescription, SwitchEntityDescription):
    """A switch of one flag that can be written."""

    point: Key[bool]


SWITCHES: tuple[DukaSwitchDescription, ...] = (
    DukaSwitchDescription(
        key=str(PointKey.HUMIDITY_SENSOR_ENABLED),
        translation_key=str(PointKey.HUMIDITY_SENSOR_ENABLED),
        point=PointKey.HUMIDITY_SENSOR_ENABLED,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a switch for every described flag the unit has."""
    data = entry.runtime_data
    async_add_entities(DukaSwitch(data, d) for d in describe(data, SWITCHES))


class DukaSwitch(DukaPointEntity, SwitchEntity):
    """A setting that is on or off."""

    def __init__(self, data: DukaData, description: DukaSwitchDescription) -> None:
        self._flag = description.point
        super().__init__(data, description)

    def _show(self) -> None:
        self._attr_is_on = self._current(self._flag)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the setting on."""
        await self._write([(self._flag, True)])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the setting off."""
        await self._write([(self._flag, False)])
