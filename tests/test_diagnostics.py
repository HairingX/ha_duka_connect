"""Diagnostics leave out the password and what locates the unit."""

from __future__ import annotations

import json
from importlib import metadata

import pytest
from duka_connect.testing import FakeClock, SimulatedDuka
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry

from custom_components.duka_connect.data import DukaData
from custom_components.duka_connect.diagnostics import (
    REDACTED,
    async_get_config_entry_diagnostics,
)

from .conftest import DEVICE_ID, HOST, PASSWORD
from .test_entities import entity_id

UNIT_ADDRESS = bytes([192, 0, 2, 77])


def _secrets(text: str) -> list[str]:
    """What locates or identifies the unit, or is its password, found in `text`.

    The password is looked for as a value, quoted, and as the bytes it is sent as: its digits
    alone can be part of a time.
    """
    return [
        secret
        for secret in (DEVICE_ID, HOST, f'"{PASSWORD}"', f"'{PASSWORD}'", PASSWORD.encode().hex(),
                       "192.0.2.77", UNIT_ADDRESS.hex(), "192, 0, 2, 77")
        if secret in text
    ]


async def test_diagnostics_hold_every_value_and_no_credential(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    assert _secrets(repr(report)) == []
    assert report["entry"]["data"]["password"] == REDACTED
    battery = report["values"]["rtc_battery_voltage"]
    assert (battery["value"], battery["raw"], battery["quality"]) == (3010, "c20b", "GOOD")
    assert (battery["certainty"], battery["consecutive_failures"]) == ("verified", 0)
    assert battery["at"]
    assert report["values"]["speed"]["value"] == "MEDIUM"
    assert report["values"]["firmware_date"]["value"] == "2023-05-17"
    assert (report["model"], report["identity"]) == ("Duka One", {"unit_type": 3})
    assert (report["status"], report["unavailable"]) == ({"CONNECTED": True, "WRITE_PENDING": False}, {})


async def test_diagnostics_say_how_the_unit_answers_and_the_versions(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    assert report["integration_version"] == "0.0.0"
    assert report["libraries"] == {
        "duka_connect": metadata.version("duka_connect"),
        "event_connect": metadata.version("event_connect"),
    }
    assert (report["silent"], report["silent_for"]) == (False, 0.0)
    assert report["seconds_until_next_poll"] is not None
    link = report["link"]
    assert link["requests"] > 0
    assert (link["open"], link["open_for"], link["openings"], link["gave_up"]) == (False, 0.0, 0, False)
    assert "writes" not in link


async def test_a_library_not_installed_has_no_version(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    loaded: DukaData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", missing)
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    assert report["libraries"] == {"duka_connect": None, "event_connect": None}


async def test_a_write_shows_that_the_unit_took_it_and_what_it_answered(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": entity_id(hass, "number", "humidity_threshold"), "value": 70},
        blocking=True,
    )
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    (record,) = report["writes"]["humidity_threshold"]
    assert (record["value"], record["raw"], record["attempts"]) == (70, "46", 1)
    assert (record["outcome"], record["detail"]) == ("taken", "")
    assert record["sent_at"] and record["ended_at"]
    read_back = record["read_back"]
    assert (read_back["value"], read_back["quality"], read_back["raw"]) == (70, "GOOD", "46")
    assert read_back["at"]


async def test_diagnostics_leave_out_the_address_the_unit_reports(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.values[0xA3] = UNIT_ADDRESS
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    assert _secrets(repr(report)) == []
    address = report["values"]["ip_address"]
    assert (address["value"], address["raw"], address["quality"]) == (REDACTED, REDACTED, "GOOD")
    assert (address["certainty"], address["consecutive_failures"]) == ("verified", 0)
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostics_of_every_point_and_a_write_hold_nothing_that_locates_or_identifies(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka, clock: FakeClock
) -> None:
    """The unit reports a recognisable address; a setting is written, and then every point read."""
    unit.values[0xA3] = UNIT_ADDRESS
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    client = config_entry.runtime_data.client
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": entity_id(hass, "number", "humidity_threshold"), "value": 70},
        blocking=True,
    )
    clock.advance(60)
    await client.refresh()
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    text = json.dumps(report)  # raises for anything JSON cannot hold
    assert set(report["values"]) == {str(key) for key, point in client.points.items() if point.readable}
    assert report["writes"]["humidity_threshold"][0]["outcome"] == "taken"
    assert _secrets(text) == []
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
