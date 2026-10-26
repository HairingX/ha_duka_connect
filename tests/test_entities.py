"""The unit's entities: what they show, and what they write."""

from __future__ import annotations

from duka_connect import Speed, VentilationMode
from duka_connect.testing import SimulatedDuka
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from datetime import datetime

import pytest
from homeassistant.util import dt as dt_util
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.duka_connect.const import DOMAIN
from custom_components.duka_connect.data import DukaData

from .conftest import FakeClock

NAME = "Duka One"


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{NAME}_{key}")
    assert found is not None, key
    return found


def state(hass: HomeAssistant, platform: str, key: str) -> str:
    current = hass.states.get(entity_id(hass, platform, key))
    assert current is not None, key
    return current.state


async def test_the_unit_has_every_entity(hass: HomeAssistant, loaded: DukaData) -> None:
    unique_ids = sorted(entry.unique_id for entry in er.async_get(hass).entities.values())
    assert unique_ids == sorted(
        f"{NAME}_{key}"
        for key in (
            "fan", "humidity", "fan_rpm", "rtc_battery_voltage", "filter_timer", "timer_countdown",
            "operating_time", "alarm", "firmware_version", "firmware_date", "unit_type",
            "filter_replace", "boost", "reset_filter_timer", "reset_alarms",
            "humidity_sensor_enabled", "humidity_threshold", "boost_off_delay",
            "ventilation_mode", "timer_mode", "rtc_battery_low",
            "fan2_rpm", "analog_sensor_level", "ip_address",
            "humidity_over_threshold", "relay_sensor_active", "analog_sensor_over_threshold",
            "weekly_schedule", "cloud_enabled", "relay_sensor_enabled", "analog_sensor_enabled",
            "night_timer", "party_timer", "filter_interval", "analog_sensor_threshold",
            "supply_speed_1", "exhaust_speed_1", "supply_speed_2", "exhaust_speed_2",
            "supply_speed_3", "exhaust_speed_3", "restore_fan_speeds", "set_clock",
            "speed", "manual_speed", "clock", "clock_offset",
        )
    )


async def test_sensors_show_the_units_values(hass: HomeAssistant, loaded: DukaData) -> None:
    assert state(hass, "sensor", "humidity") == "45"
    assert state(hass, "sensor", "rtc_battery_voltage") == "3.01"
    assert state(hass, "sensor", "alarm") == "none"
    assert state(hass, "binary_sensor", "filter_replace") == STATE_OFF
    assert state(hass, "select", "ventilation_mode") == "heat_recovery"
    assert state(hass, "fan", "fan") == STATE_ON


async def test_an_alarm_level_is_shown_by_its_name(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka, clock: FakeClock
) -> None:
    unit.values[0x83] = b"\x02"
    clock.advance(60)
    await loaded.client.poll()
    await hass.async_block_till_done()
    assert state(hass, "sensor", "alarm") == "warning"


async def test_entities_are_unavailable_while_the_unit_does_not_answer(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka, clock: FakeClock
) -> None:
    unit.answering = False
    clock.advance(30)
    await loaded.client.poll()
    await hass.async_block_till_done()
    assert state(hass, "sensor", "humidity") == STATE_UNAVAILABLE


async def test_a_percentage_runs_the_fan_at_the_manual_speed(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "fan", "set_percentage",
        {"entity_id": entity_id(hass, "fan", "fan"), "percentage": 50}, blocking=True,
    )
    assert unit.values[0x02] == bytes([Speed.MANUAL])
    assert unit.values[0x44] == bytes([128])


async def test_a_preset_mode_runs_the_fan_at_a_preset_speed(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "fan", "set_preset_mode",
        {"entity_id": entity_id(hass, "fan", "fan"), "preset_mode": "high"}, blocking=True,
    )
    assert unit.values[0x02] == bytes([Speed.HIGH])
    current = hass.states.get(entity_id(hass, "fan", "fan"))
    assert current is not None and current.attributes["preset_mode"] == "high"


async def test_turning_the_fan_off_writes_power_off(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": entity_id(hass, "fan", "fan")}, blocking=True
    )
    assert unit.values[0x01] == b"\x00"
    assert state(hass, "fan", "fan") == STATE_OFF


async def test_selecting_a_ventilation_mode_writes_it(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": entity_id(hass, "select", "ventilation_mode"), "option": "supply"},
        blocking=True,
    )
    assert unit.values[0xB7] == bytes([VentilationMode.SUPPLY])
    assert state(hass, "select", "ventilation_mode") == "supply"


async def test_the_filter_button_resets_the_filter(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka, clock: FakeClock
) -> None:
    unit.values[0x88] = b"\x01"
    await loaded.client.refresh()
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "filter_replace") == STATE_ON
    await hass.services.async_call(
        "button", "press",
        {"entity_id": entity_id(hass, "button", "reset_filter_timer")}, blocking=True,
    )
    clock.advance(1)
    await loaded.client.poll()
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "filter_replace") == STATE_OFF


async def test_a_number_outside_its_limits_is_refused(
    hass: HomeAssistant, loaded: DukaData
) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": entity_id(hass, "number", "humidity_threshold"), "value": 30},
            blocking=True,
        )


async def test_turning_the_fan_on_writes_power_on(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    unit.values[0x01] = b"\x00"
    await loaded.client.refresh()
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": entity_id(hass, "fan", "fan")}, blocking=True
    )
    assert unit.values[0x01] == b"\x01"
    assert unit.values[0x02] == bytes([Speed.MEDIUM])


async def test_turning_the_fan_on_at_a_percentage_runs_the_manual_speed(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "fan", "turn_on",
        {"entity_id": entity_id(hass, "fan", "fan"), "percentage": 100}, blocking=True,
    )
    assert unit.values[0x02] == bytes([Speed.MANUAL])
    assert unit.values[0x44] == bytes([255])
    current = hass.states.get(entity_id(hass, "fan", "fan"))
    assert current is not None and current.attributes["percentage"] == 100


async def test_a_percentage_of_0_turns_the_fan_off(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "fan", "set_percentage",
        {"entity_id": entity_id(hass, "fan", "fan"), "percentage": 0}, blocking=True,
    )
    assert unit.values[0x01] == b"\x00"


async def test_the_humidity_boost_switch_writes_the_setting(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    switch = entity_id(hass, "switch", "humidity_sensor_enabled")
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert unit.values[0x0F] == b"\x01"
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    assert unit.values[0x0F] == b"\x00"


async def test_a_number_within_its_limits_is_written(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": entity_id(hass, "number", "humidity_threshold"), "value": 70},
        blocking=True,
    )
    assert unit.values[0x19] == bytes([70])


async def test_the_clock_battery_is_low_under_the_limit(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    assert state(hass, "binary_sensor", "rtc_battery_low") == STATE_OFF
    unit.values[0x24] = (2400).to_bytes(2, "little")
    await loaded.client.refresh()
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "rtc_battery_low") == STATE_ON


async def test_a_unit_without_a_clock_battery_voltage_has_no_battery_low_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.unsupported.add(0x24)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{NAME}_rtc_battery_low") is None
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_the_clock_is_set_to_home_assistants_local_time(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/Copenhagen")
    freezer.move_to("2027-03-01 06:07:08+00:00")
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", "set_clock")}, blocking=True
    )
    assert unit.values[0x6F] == bytes([8, 7, 7])
    assert unit.values[0x70] == bytes([1, 1, 3, 27])


async def test_a_unit_without_separate_fan_speeds_has_no_restore_button(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.unsupported.update(range(0x3A, 0x40))
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("button", DOMAIN, f"{NAME}_restore_fan_speeds") is None
    assert registry.async_get_entity_id("number", DOMAIN, f"{NAME}_supply_speed_1") is None
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_a_unit_without_a_clock_has_no_set_clock_button(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.unsupported.add(0x6F)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{NAME}_set_clock") is None
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_the_weekly_schedule_switch_writes_the_setting(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id(hass, "switch", "weekly_schedule")}, blocking=True
    )
    assert unit.values[0x72] == b"\x01"


async def test_a_timer_duration_is_written_in_minutes(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": entity_id(hass, "number", "night_timer"), "value": 90},
        blocking=True,
    )
    assert unit.values[0x0302] == bytes([30, 1])


async def test_the_speed_has_its_own_entity_with_its_history(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    assert state(hass, "select", "speed") == "medium"
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": entity_id(hass, "select", "speed"), "option": "high"},
        blocking=True,
    )
    assert unit.values[0x02] == bytes([Speed.HIGH])
    assert state(hass, "fan", "fan") == STATE_ON
    current = hass.states.get(entity_id(hass, "fan", "fan"))
    assert current is not None and current.attributes["preset_mode"] == "high"


async def test_the_manual_speed_is_shown_in_percent_as_the_fan_shows_it(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    await hass.services.async_call(
        "fan", "set_percentage",
        {"entity_id": entity_id(hass, "fan", "fan"), "percentage": 40},
        blocking=True,
    )
    fan = hass.states.get(entity_id(hass, "fan", "fan"))
    manual = hass.states.get(entity_id(hass, "number", "manual_speed"))
    assert fan is not None and manual is not None
    assert manual.state == f"{float(fan.attributes['percentage'])}"
    assert (manual.attributes["min"], manual.attributes["max"]) == (0, 100)


async def test_a_manual_speed_in_percent_is_written_on_the_units_scale(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    for percentage, manual in ((100, 255), (50, 128), (0, 0)):
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": entity_id(hass, "number", "manual_speed"), "value": percentage},
            blocking=True,
        )
        assert unit.values[0x44] == bytes([manual])


async def test_the_device_carries_the_firmware_and_unit_type(
    hass: HomeAssistant, config_entry: MockConfigEntry, loaded: DukaData
) -> None:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, NAME), config_entry.entry_id)
    assert device is not None
    assert (device.manufacturer, device.model, device.sw_version, device.model_id) == (
        "Duka", "Duka One", "1.5", "3"
    )


async def test_high_humidity_is_a_moisture_sensor(hass: HomeAssistant, loaded: DukaData) -> None:
    """Humid air is moisture; the flag shows Wet and Dry, as a Nilan unit's does."""
    current = hass.states.get(entity_id(hass, "binary_sensor", "humidity_over_threshold"))
    assert current is not None
    assert current.attributes["device_class"] == "moisture"
    assert current.attributes["friendly_name"] == "Duka One High humidity"


async def test_the_clock_shows_what_the_unit_thinks_the_time_is(
    hass: HomeAssistant, loaded: DukaData
) -> None:
    shown = dt_util.parse_datetime(state(hass, "sensor", "clock"))
    expected = datetime(2026, 10, 26, 12, 30, 15, tzinfo=dt_util.get_default_time_zone())
    assert shown == expected


async def test_after_setting_the_clock_it_is_no_more_than_a_second_off(
    hass: HomeAssistant, loaded: DukaData
) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", "set_clock")}, blocking=True
    )
    await hass.async_block_till_done()
    assert abs(float(state(hass, "sensor", "clock_offset"))) <= 1


async def test_a_unit_without_a_clock_has_no_clock_sensors(
    hass: HomeAssistant, config_entry: MockConfigEntry, unit: SimulatedDuka
) -> None:
    unit.unsupported.add(0x70)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    for key in ("clock", "clock_offset"):
        assert registry.async_get_entity_id("sensor", DOMAIN, f"{NAME}_{key}") is None
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_a_clock_the_unit_holds_no_valid_date_for_is_unknown(
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    unit.values[0x70] = bytes([31, 1, 13, 26])
    await loaded.client.refresh()
    await hass.async_block_till_done()
    assert state(hass, "sensor", "clock") == STATE_UNKNOWN
    assert state(hass, "sensor", "clock_offset") == STATE_UNKNOWN
