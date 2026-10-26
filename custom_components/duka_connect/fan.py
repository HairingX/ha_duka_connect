"""The fan: on or off, its speed, and its three preset speeds."""

from __future__ import annotations

from typing import Any

from duka_connect import Key, PointKey, Speed
from homeassistant.components.fan import FanEntity
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import DukaConfigEntry, DukaData
from .entity import DukaEntity
from .speed import manual_to_percentage, percentage_to_manual

PARALLEL_UPDATES = 0

PRESETS: dict[str, Speed] = {"low": Speed.LOW, "medium": Speed.MEDIUM, "high": Speed.HIGH}
"""The unit's preset speeds, by preset mode; any other speed is the manual one."""

_PRESET_PERCENTAGE: dict[Speed, int] = {Speed.LOW: 33, Speed.MEDIUM: 67, Speed.HIGH: 100}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the unit's fan."""
    async_add_entities([DukaFan(entry.runtime_data)])


class DukaFan(DukaEntity, FanEntity):
    """The unit's fan.

    A percentage is the manual speed, 1 to 255; a preset mode is one of the three preset speeds,
    whose percentage is shown as a third of the range each.
    """

    _attr_name = None
    _attr_translation_key = "fan"
    _attr_preset_modes = list(PRESETS)
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
    )

    def __init__(self, data: DukaData) -> None:
        super().__init__(data, "fan")

    def _watched(self) -> tuple[Key[Any], ...]:
        return (PointKey.POWER, PointKey.SPEED, PointKey.MANUAL_SPEED)

    def _required(self) -> tuple[Key[Any], ...]:
        return (PointKey.POWER, PointKey.SPEED)

    def _show(self) -> None:
        on = self._current(PointKey.POWER)
        speed = self._current(PointKey.SPEED)
        manual = self._current(PointKey.MANUAL_SPEED)
        self._attr_is_on = on
        # Home Assistant counts a fan with a preset mode as on, so an off fan shows none.
        self._attr_preset_mode = (
            next((name for name, preset in PRESETS.items() if preset is speed), None)
            if on else None
        )
        if not on:
            self._attr_percentage = 0
        elif speed is Speed.MANUAL:
            self._attr_percentage = (
                None if manual is None
                else manual_to_percentage(max(manual, 1))
            )
        else:
            self._attr_percentage = None if speed is None else _PRESET_PERCENTAGE[speed]

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on, at a speed when one is given."""
        writes: list[tuple[Key[Any], Any]] = [(PointKey.POWER, True)]
        writes += self._speed_writes(percentage, preset_mode)
        await self._write(writes)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._write([(PointKey.POWER, False)])

    async def async_set_percentage(self, percentage: int) -> None:
        """Run the fan at the manual speed; 0 turns it off."""
        if percentage == 0:
            await self.async_turn_off()
            return
        await self._write([(PointKey.POWER, True), *self._speed_writes(percentage, None)])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Run the fan at a preset speed."""
        await self._write([(PointKey.POWER, True), *self._speed_writes(None, preset_mode)])

    @staticmethod
    def _speed_writes(
        percentage: int | None, preset_mode: str | None
    ) -> list[tuple[Key[Any], Any]]:
        if preset_mode is not None:
            return [(PointKey.SPEED, PRESETS[preset_mode])]
        if percentage is not None and percentage > 0:
            manual = percentage_to_manual(percentage)
            return [(PointKey.SPEED, Speed.MANUAL), (PointKey.MANUAL_SPEED, manual)]
        return []
