"""Setting a unit up, and changing where it is reached."""

from __future__ import annotations

import pytest
from duka_connect.testing import SimulatedDuka
from collections.abc import AsyncIterator
from typing import Any

from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.duka_connect.const import CONF_DEVICE_ID, DOMAIN

from .conftest import DEVICE_ID, HOST, NAME, PASSWORD, entry_data


async def configure(
    hass: HomeAssistant, flow_id: str, user_input: dict[str, str]
) -> dict[str, Any]:
    # HA declares the flow manager's user input as a bare `dict`.
    flow: Any = hass.config_entries.flow
    result: ConfigFlowResult = await flow.async_configure(flow_id, user_input)
    return dict(result)


async def start(hass: HomeAssistant, user_input: dict[str, str]) -> dict[str, Any]:
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    return await configure(hass, flow["flow_id"], user_input)


async def test_a_unit_is_set_up_by_its_address_device_id_and_password(hass: HomeAssistant) -> None:
    result = await start(
        hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID.lower(), CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data()
    assert [entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN)] == [DEVICE_ID]


async def test_an_empty_device_id_is_asked_of_the_unit(hass: HomeAssistant) -> None:
    result = await start(hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: "", CONF_PASSWORD: PASSWORD})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data()


async def test_a_unit_that_does_not_answer_shows_an_error(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.answering = False
    result = await start(
        hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_unit_answering_discovery_asks_for_the_device_id(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.answering = False
    result = await start(hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: "", CONF_PASSWORD: PASSWORD})
    assert result["errors"] == {"base": "device_id_not_found"}


async def test_a_wrong_password_shows_an_error(hass: HomeAssistant) -> None:
    result = await start(
        hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: "9999"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_a_unit_set_up_already_is_not_set_up_again(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data()).add_to_hass(hass)
    result = await start(
        hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfiguring_changes_the_password(hass: HomeAssistant, unit: SimulatedDuka) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data())
    entry.add_to_hass(hass)
    unit.password = "2222"
    flow = await entry.start_reconfigure_flow(hass)
    result = await configure(
        hass, flow["flow_id"], {CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: "2222"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PASSWORD] == "2222"


async def test_a_unit_that_is_not_a_duka_one_shows_an_error(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.unsupported.add(0xB9)
    result = await start(
        hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}
    )
    assert result["errors"] == {"base": "unsupported_device"}


async def test_an_unexpected_error_shows_an_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(host: str, device_id: str, password: str) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr("custom_components.duka_connect.config_flow.connect_once", failing)
    result = await start(
        hass, {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}
    )
    assert result["errors"] == {"base": "unknown"}


async def test_reconfiguring_to_a_unit_that_does_not_answer_shows_an_error(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data())
    entry.add_to_hass(hass)
    unit.answering = False
    flow = await entry.start_reconfigure_flow(hass)
    result = await configure(
        hass, flow["flow_id"], {CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}
    )
    assert result["errors"] == {"base": "cannot_connect"}


SECOND_ID = "DUKA0000TEST0002"


@pytest.fixture
async def second_unit(network: list[SimulatedDuka]) -> AsyncIterator[SimulatedDuka]:
    """A second unit on the network, with the same password."""
    simulated = SimulatedDuka(device_id=SECOND_ID, password=PASSWORD)
    await simulated.start(HOST)
    network.append(simulated)
    yield simulated
    simulated.close()


async def test_an_empty_host_sets_up_the_one_unit_the_search_finds(hass: HomeAssistant) -> None:
    result = await start(hass, {CONF_NAME: NAME, CONF_HOST: "", CONF_DEVICE_ID: "", CONF_PASSWORD: PASSWORD})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data()


async def test_of_several_units_found_the_user_picks_one(
    hass: HomeAssistant, second_unit: SimulatedDuka
) -> None:
    result = await start(hass, {CONF_NAME: NAME, CONF_HOST: "", CONF_DEVICE_ID: "", CONF_PASSWORD: PASSWORD})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    result = await configure(hass, result["flow_id"], {CONF_DEVICE_ID: SECOND_ID})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data(device_id=SECOND_ID)


async def test_a_device_id_with_an_empty_host_sets_up_that_unit(
    hass: HomeAssistant, second_unit: SimulatedDuka
) -> None:
    result = await start(
        hass, {CONF_NAME: NAME, CONF_HOST: "", CONF_DEVICE_ID: SECOND_ID.lower(), CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data(device_id=SECOND_ID)


async def test_a_unit_set_up_already_is_left_out_of_the_search(
    hass: HomeAssistant, second_unit: SimulatedDuka
) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data()).add_to_hass(hass)
    result = await start(hass, {CONF_NAME: NAME, CONF_HOST: "", CONF_DEVICE_ID: "", CONF_PASSWORD: PASSWORD})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data(device_id=SECOND_ID)


async def test_a_search_that_finds_nothing_asks_for_the_host(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.answering = False
    result = await start(hass, {CONF_NAME: NAME, CONF_HOST: "", CONF_DEVICE_ID: "", CONF_PASSWORD: PASSWORD})
    assert result["errors"] == {"base": "no_units_found"}


async def test_a_found_unit_with_a_wrong_password_is_shown_with_its_host(
    hass: HomeAssistant,
) -> None:
    result = await start(hass, {CONF_NAME: NAME, CONF_HOST: "", CONF_DEVICE_ID: "", CONF_PASSWORD: "9999"})
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    result = await configure(
        hass, result["flow_id"], {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
