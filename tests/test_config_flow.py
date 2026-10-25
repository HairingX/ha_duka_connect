"""Setting a unit up, found by a search or entered by hand, and changing where it is reached."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from duka_connect.testing import SimulatedDuka
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.duka_connect.const import CONF_DEVICE_ID, DOMAIN

from .conftest import DEVICE_ID, HOST, NAME, PASSWORD, entry_data

SECOND_ID = "DUKA0000TEST0002"
MANUAL = {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_ID: DEVICE_ID, CONF_PASSWORD: PASSWORD}


async def configure(hass: HomeAssistant, flow_id: str, user_input: dict[str, str]) -> dict[str, Any]:
    # HA declares the flow manager's user input as a bare `dict`.
    flow: Any = hass.config_entries.flow
    result: ConfigFlowResult = await flow.async_configure(flow_id, user_input)
    return dict(result)


async def choose(hass: HomeAssistant, step: str) -> dict[str, Any]:
    """A user's flow, past the first menu to `step`."""
    flow: dict[str, Any] = dict(
        await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    )
    assert flow["type"] is FlowResultType.MENU
    return await configure(hass, flow["flow_id"], {"next_step_id": step})


async def manual(hass: HomeAssistant, user_input: dict[str, str]) -> dict[str, Any]:
    result = await choose(hass, "manual")
    return await configure(hass, result["flow_id"], user_input)


@pytest.fixture
async def second_unit(network: list[SimulatedDuka]) -> AsyncIterator[SimulatedDuka]:
    """A second unit on the network, with the same password."""
    simulated = SimulatedDuka(device_id=SECOND_ID, password=PASSWORD)
    await simulated.start(HOST)
    network.append(simulated)
    yield simulated
    simulated.close()


async def test_the_flow_starts_with_a_choice_of_search_or_manual(hass: HomeAssistant) -> None:
    flow = dict(await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER}))
    assert flow["type"] is FlowResultType.MENU
    assert flow["menu_options"] == ["search", "manual"]


async def test_a_search_shows_the_unit_it_finds(hass: HomeAssistant) -> None:
    result = await choose(hass, "search")
    assert result["step_id"] == "pick"
    result = await configure(
        hass, result["flow_id"], {CONF_DEVICE_ID: DEVICE_ID, CONF_NAME: NAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data()


async def test_of_several_units_found_the_user_picks_one(
    hass: HomeAssistant, second_unit: SimulatedDuka
) -> None:
    result = await choose(hass, "search")
    result = await configure(
        hass, result["flow_id"], {CONF_DEVICE_ID: SECOND_ID, CONF_NAME: NAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data(device_id=SECOND_ID)


async def test_a_unit_set_up_already_is_left_out_of_the_search(
    hass: HomeAssistant, second_unit: SimulatedDuka
) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data()).add_to_hass(hass)
    result = await choose(hass, "search")
    with pytest.raises(InvalidData):
        await configure(
            hass, result["flow_id"], {CONF_DEVICE_ID: DEVICE_ID, CONF_NAME: NAME, CONF_PASSWORD: PASSWORD}
        )
    result = await configure(
        hass, result["flow_id"], {CONF_DEVICE_ID: SECOND_ID, CONF_NAME: NAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["data"] == entry_data(device_id=SECOND_ID)


async def test_a_search_that_finds_nothing_offers_to_search_again_or_enter_by_hand(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.answering = False
    result = await choose(hass, "search")
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "not_found"
    assert result["menu_options"] == ["search", "manual"]
    unit.answering = True
    result = await configure(hass, result["flow_id"], {"next_step_id": "search"})
    assert result["step_id"] == "pick"


async def test_after_finding_nothing_the_unit_can_be_entered_by_hand(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.answering = False
    result = await choose(hass, "search")
    result = await configure(hass, result["flow_id"], {"next_step_id": "manual"})
    assert result["step_id"] == "manual"


async def test_a_found_unit_with_a_wrong_password_asks_again(hass: HomeAssistant) -> None:
    result = await choose(hass, "search")
    result = await configure(
        hass, result["flow_id"], {CONF_DEVICE_ID: DEVICE_ID, CONF_NAME: NAME, CONF_PASSWORD: "9999"}
    )
    assert result["step_id"] == "pick"
    assert result["errors"] == {"base": "cannot_connect"}
    result = await configure(
        hass, result["flow_id"], {CONF_DEVICE_ID: DEVICE_ID, CONF_NAME: NAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_a_unit_is_set_up_by_hand_by_its_address_device_id_and_password(
    hass: HomeAssistant,
) -> None:
    result = await manual(hass, {**MANUAL, CONF_DEVICE_ID: DEVICE_ID.lower()})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data()
    assert [entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN)] == [DEVICE_ID]


async def test_an_empty_device_id_is_asked_of_the_unit(hass: HomeAssistant) -> None:
    result = await manual(hass, {**MANUAL, CONF_DEVICE_ID: ""})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data()


async def test_a_unit_that_does_not_answer_shows_an_error(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.answering = False
    result = await manual(hass, MANUAL)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_unit_answering_at_the_address_asks_for_the_device_id(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.answering = False
    result = await manual(hass, {**MANUAL, CONF_DEVICE_ID: ""})
    assert result["errors"] == {"base": "device_id_not_found"}


async def test_a_wrong_password_shows_an_error(hass: HomeAssistant) -> None:
    result = await manual(hass, {**MANUAL, CONF_PASSWORD: "9999"})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_a_unit_set_up_already_is_not_set_up_again(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data()).add_to_hass(hass)
    result = await manual(hass, MANUAL)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_unit_that_is_not_a_duka_one_shows_an_error(
    hass: HomeAssistant, unit: SimulatedDuka
) -> None:
    unit.unsupported.add(0xB9)
    result = await manual(hass, MANUAL)
    assert result["errors"] == {"base": "unsupported_device"}


async def test_an_unexpected_error_shows_an_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(host: str, device_id: str, password: str) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr("custom_components.duka_connect.config_flow.connect_once", failing)
    result = await manual(hass, MANUAL)
    assert result["errors"] == {"base": "unknown"}


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
