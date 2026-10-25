"""The unit's entities: what they show, and what they write."""

from __future__ import annotations

from duka_connect import Speed, VentilationMode
from duka_connect.testing import SimulatedDuka
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

import pytest

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
            "ventilation_mode", "timer_mode",
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
    hass: HomeAssistant, loaded: DukaData, unit: SimulatedDuka
) -> None:
    unit.values[0x88] = b"\x01"
    await loaded.client.refresh()
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "filter_replace") == STATE_ON
    await hass.services.async_call(
        "button", "press",
        {"entity_id": entity_id(hass, "button", "reset_filter_timer")}, blocking=True,
    )
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
