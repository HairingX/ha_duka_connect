"""Diagnostics leave out the password and what locates the unit."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.duka_connect.data import DukaData
from custom_components.duka_connect.diagnostics import (
    REDACTED,
    async_get_config_entry_diagnostics,
)

from .conftest import DEVICE_ID, HOST, PASSWORD


async def test_diagnostics_hold_every_value_and_no_credential(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    report = await async_get_config_entry_diagnostics(hass, config_entry)
    text = repr(report)
    for secret in (DEVICE_ID, HOST, PASSWORD):
        assert secret not in text
    assert report["entry"]["data"]["password"] == REDACTED
    assert report["values"]["rtc_battery_voltage"]["raw"] == "c20b"
    assert report["unit_type"] == 3
