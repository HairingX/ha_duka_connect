"""Loading and unloading a unit's config entry."""

from __future__ import annotations

import asyncio

import pytest
from duka_connect.testing import SimulatedDuka
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.duka_connect.const import DOMAIN
from custom_components.duka_connect.data import DukaData

from .conftest import DEVICE_ID, FakeClock, entry_data


async def set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_a_unit_that_does_not_answer_is_retried_later(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.answering = False
    await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_wrong_password_is_retried_later(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data(password="9999"))
    await set_up(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_unit_without_a_unit_type_is_not_supported(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.unsupported.add(0xB9)
    await set_up(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unloading_stops_polling_and_disconnects(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    poller = loaded.poller
    assert poller is not None and not poller.done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert poller.done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_the_entities_of_a_point_the_unit_lost_are_removed(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    await set_up(hass, config_entry)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, "Duka One_rtc_battery_voltage")
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    unit.unsupported.add(0x24)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_entity_id("sensor", DOMAIN, "Duka One_rtc_battery_voltage") is None
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize("old,new", [("night_timer", "reduced_duration"), ("party_timer", "boost_duration")])
async def test_an_entity_of_a_renamed_point_keeps_its_entity_id_and_history(
    hass: HomeAssistant, config_entry: MockConfigEntry, old: str, new: str
) -> None:
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    kept = registry.async_get_or_create(
        "number", DOMAIN, f"Duka One_{old}", config_entry=config_entry, suggested_object_id=f"duka_one_{old}"
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_entity_id("number", DOMAIN, f"Duka One_{new}") == kept.entity_id
    assert registry.async_get_entity_id("number", DOMAIN, f"Duka One_{old}") is None
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_a_unit_that_stops_answering_is_logged_once_and_again_when_it_answers(
    hass: HomeAssistant,
    loaded: DukaData,
    unit: SimulatedDuka,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    unit.answering = False
    for _ in range(2):
        clock.advance(30)
        await loaded.client.poll()
    unit.answering = True
    clock.advance(30)
    await loaded.client.poll()
    messages = [r.getMessage() for r in caplog.records if r.name == "custom_components.duka_connect"]
    assert messages == ["Duka One does not answer", "Duka One answers again"]


async def test_with_polling_disabled_nothing_is_read_on_a_schedule(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data(), pref_disable_polling=True
    )
    await set_up(hass, entry)
    data: DukaData = entry.runtime_data
    assert data.client.seconds_until_next_poll() is None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_with_polling_disabled_what_a_command_changes_is_still_read_back(
    hass: HomeAssistant, unit: SimulatedDuka, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("custom_components.duka_connect.POLL_TICK", 0.01)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data(), pref_disable_polling=True
    )
    unit.values[0x88] = b"\x01"
    await set_up(hass, entry)
    registry = er.async_get(hass)
    filter_replace = registry.async_get_entity_id("binary_sensor", DOMAIN, "Duka One_filter_replace")
    reset = registry.async_get_entity_id("button", DOMAIN, "Duka One_reset_filter_timer")
    current = hass.states.get(filter_replace or "")
    assert filter_replace is not None and current is not None and current.state == STATE_ON
    await hass.services.async_call("button", "press", {"entity_id": reset}, blocking=True)
    clock.advance(1)
    for _ in range(100):
        current = hass.states.get(filter_replace)
        if current is not None and current.state == STATE_OFF:
            break
        await asyncio.sleep(0.01)
    current = hass.states.get(filter_replace)
    assert current is not None and current.state == STATE_OFF
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
