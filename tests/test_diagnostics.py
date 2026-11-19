"""Diagnostics leave out the password and what locates the unit."""

from __future__ import annotations

from duka_connect.testing import SimulatedDuka
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry

from custom_components.duka_connect.data import DukaData
from custom_components.duka_connect.diagnostics import (
    REDACTED,
    async_get_config_entry_diagnostics,
)

from .conftest import DEVICE_ID, HOST, PASSWORD

UNIT_ADDRESS = bytes([192, 0, 2, 77])


async def test_diagnostics_hold_every_value_and_no_credential(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    text = repr(report)
    for secret in (DEVICE_ID, HOST, PASSWORD):
        assert secret not in text
    assert report["entry"]["data"]["password"] == REDACTED
    assert report["values"]["rtc_battery_voltage"]["raw"] == "c20b"
    assert (report["model"], report["identity"]) == ("Duka One", {"unit_type": 3})
    assert report["values"]["rtc_battery_voltage"]["consecutive_failures"] == 0


async def test_diagnostics_say_how_the_unit_answers(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    link = report["link"]
    assert link["requests"] > 0
    assert (link["open"], link["open_for"], link["openings"], link["gave_up"]) == (False, 0.0, 0, False)


async def test_diagnostics_leave_out_the_address_the_unit_reports(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.values[0xA3] = UNIT_ADDRESS
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    text = repr(report)
    assert "192.0.2.77" not in text
    assert UNIT_ADDRESS.hex() not in text
    assert report["values"]["ip_address"] == {
        "value": REDACTED,
        "quality": "GOOD",
        "raw": REDACTED,
        "certainty": "REPORTED",
        "consecutive_failures": 0,
    }
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
