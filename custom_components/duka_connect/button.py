"""Actions on the unit: reset its alarms, and its filter timer."""

from __future__ import annotations

from dataclasses import dataclass

from duka_connect import Key, PointKey
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import DukaConfigEntry, DukaData
from .entity import DukaEntity, DukaEntityDescription

# The client sends writes in order, so actions are passed to it as they come.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DukaButtonDescription(DukaEntityDescription, ButtonEntityDescription):
    """A button that sends one command."""

    point: Key[None]


BUTTONS: tuple[DukaButtonDescription, ...] = tuple(
    DukaButtonDescription(
        key=str(point), translation_key=str(point), point=point, entity_category=EntityCategory.CONFIG
    )
    for point in (PointKey.RESET_FILTER_TIMER, PointKey.RESET_ALARMS)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a button for every command."""
    data = entry.runtime_data
    async_add_entities(DukaButton(data, description) for description in BUTTONS)


class DukaButton(DukaEntity, ButtonEntity):
    """A command, usable while the unit answers."""

    def __init__(self, data: DukaData, description: DukaButtonDescription) -> None:
        self.entity_description = description
        self._command = description.point
        super().__init__(data, str(description.point))

    async def async_press(self) -> None:
        """Send the command; what it changes is read back."""
        await self._write([(self._command, None)])
