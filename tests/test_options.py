"""The entry's options: the voltage under which the clock battery counts as low."""

from __future__ import annotations

from typing import Any

from duka_connect.testing import SimulatedDuka
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.duka_connect.const import BATTERY_LOW_DEFAULT, CONF_BATTERY_LOW
from custom_components.duka_connect.data import DukaData

from .test_entities import state


async def test_the_clock_battery_counts_as_low_under_2500_mv_by_default(loaded: DukaData) -> None:
    assert loaded.battery_low == BATTERY_LOW_DEFAULT == 2500


async def test_a_changed_limit_reloads_the_entry_with_it(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData, unit: SimulatedDuka
) -> None:
    assert state(hass, "binary_sensor", "rtc_battery_low") == STATE_OFF
    flow: Any = hass.config_entries.options
    result = dict(await flow.async_init(config_entry.entry_id))
    assert result["type"] is FlowResultType.FORM
    result = dict(await flow.async_configure(result["flow_id"], {CONF_BATTERY_LOW: 3100}))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options == {CONF_BATTERY_LOW: 3100}
    data: DukaData = config_entry.runtime_data
    assert data.battery_low == 3100
    assert state(hass, "binary_sensor", "rtc_battery_low") == STATE_ON
