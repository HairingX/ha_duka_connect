"""What the user is told when the unit does not answer or does not take a value."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from duka_connect.testing import SimulatedDuka
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.duka_connect as integration
from custom_components.duka_connect.data import DukaData

from .test_entities import entity_id


async def select_supply(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": entity_id(hass, "select", "ventilation_mode"), "option": "supply"},
        blocking=True,
    )


async def test_a_setting_the_unit_does_not_take_is_an_error(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    unit.unsupported.add(0xB7)
    with pytest.raises(HomeAssistantError) as raised:
        await select_supply(hass)
    assert raised.value.translation_key == "write_refused"


async def test_a_write_the_unit_does_not_answer_is_an_error(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    unit.answering = False
    with pytest.raises(HomeAssistantError) as raised:
        await select_supply(hass)
    assert raised.value.translation_key == "no_answer"


async def test_an_update_the_unit_does_not_answer_makes_the_entity_unavailable(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    assert await async_setup_component(hass, "homeassistant", {})
    unit.answering = False
    await hass.services.async_call(
        "homeassistant", "update_entity",
        {"entity_id": entity_id(hass, "sensor", "humidity")}, blocking=True,
    )
    current = hass.states.get(entity_id(hass, "sensor", "humidity"))
    assert current is not None and current.state == STATE_UNAVAILABLE


async def test_an_update_reads_the_unit_now(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    assert await async_setup_component(hass, "homeassistant", {})
    unit.values[0x25] = bytes([70])
    await hass.services.async_call(
        "homeassistant", "update_entity",
        {"entity_id": entity_id(hass, "sensor", "humidity")}, blocking=True,
    )
    current = hass.states.get(entity_id(hass, "sensor", "humidity"))
    assert current is not None and current.state == "70"


async def test_a_failing_platform_setup_closes_the_connection(
    hass: HomeAssistant, config_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(*args: Any) -> None:
        raise RuntimeError("platforms")

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", failing)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_an_entry_whose_platforms_do_not_unload_stays_loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def refusing(*args: Any) -> bool:
        return False

    with monkeypatch.context() as patched:
        patched.setattr(hass.config_entries, "async_unload_platforms", refusing)
        assert not await integration.async_unload_entry(hass, config_entry)


async def test_a_poll_that_raises_is_logged_and_polling_goes_on(
    loaded: DukaData, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    polls = 0

    async def raising() -> None:
        nonlocal polls
        polls += 1
        raise RuntimeError("poll")

    monkeypatch.setattr(integration, "POLL_TICK", 0.01)
    monkeypatch.setattr(loaded.client, "poll", raising)
    async with asyncio.timeout(5):
        while polls < 2:
            await asyncio.sleep(0.01)
    assert loaded.poller is not None and not loaded.poller.done()
    assert "Reading the unit failed" in caplog.text
