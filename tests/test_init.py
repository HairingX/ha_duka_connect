"""Loading and unloading a unit's config entry."""

from __future__ import annotations

from duka_connect.testing import SimulatedDuka
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.duka_connect.const import DOMAIN
from custom_components.duka_connect.data import DukaData

from .conftest import DEVICE_ID, entry_data


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
