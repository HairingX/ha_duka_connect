"""Set up a Duka One, found on the network or by its address, and change where it is reached or
its password."""

from __future__ import annotations

import logging
from typing import Any

import probatio
from duka_connect import (
    DEFAULT_PASSWORD,
    CannotConnectError,
    DiscoveredDevice,
    UnsupportedDeviceError,
    discover,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD

from . import const
from .const import CONF_DEVICE_ID, DEFAULT_NAME, DOMAIN
from .data import new_client

_LOGGER = logging.getLogger(__name__)


class DeviceIdNotFoundError(Exception):
    """No unit, or more than one, answered discovery at the address."""


async def find_device_id(host: str) -> str:
    """Ask the unit at `host` for its device id.

    Raises:
        DeviceIdNotFoundError: no unit, or more than one, answered.
    """
    found = await discover(host, timeout=const.DISCOVERY_TIMEOUT)
    if len(found) != 1:
        raise DeviceIdNotFoundError(host)
    return found[0].device_id


async def search_units() -> list[DiscoveredDevice]:
    """Ask every unit on the local network, by broadcast, for its address and device id."""
    return await discover(timeout=const.DISCOVERY_TIMEOUT)


async def connect_once(host: str, device_id: str, password: str) -> None:
    """Connect to the unit once, and let it go.

    Raises:
        CannotConnectError: the unit did not answer.
        UnsupportedDeviceError: the unit is not a Duka One.
    """
    client = new_client(host, device_id, password)
    try:
        await client.connect()
    finally:
        await client.disconnect()


async def _check(host: str, device_id: str, password: str) -> str | None:
    """The error to show for these settings, or None when the unit answers."""
    try:
        await connect_once(host, device_id, password)
    except CannotConnectError:
        return "cannot_connect"
    except UnsupportedDeviceError:
        return "unsupported_device"
    except Exception:
        _LOGGER.exception("Connecting to the unit failed unexpectedly")
        return "unknown"
    return None


def _schema(defaults: dict[str, Any], *, with_name: bool) -> probatio.Schema:
    fields: dict[Any, Any] = {}
    host = defaults.get(CONF_HOST, "")
    if with_name:
        fields[probatio.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME))] = str
        # Setting up, an empty address searches the network for the unit.
        fields[probatio.Optional(CONF_HOST, default=host)] = str
    else:
        fields[probatio.Required(CONF_HOST, default=host)] = str
    fields[probatio.Optional(CONF_DEVICE_ID, default=defaults.get(CONF_DEVICE_ID, ""))] = str
    fields[probatio.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, DEFAULT_PASSWORD))] = str
    return probatio.Schema(fields)


class DukaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a unit found on the network, or by its address.

    Without an address, the network is searched: one unit found is set up, and of several the
    user picks one. Without a device id, the unit at the address is asked for it.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Start with nothing entered and nothing found."""
        self._entered: dict[str, Any] = {}
        self._found: dict[str, DiscoveredDevice] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the unit's name, address, device id and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if str(user_input.get(CONF_HOST) or "").strip():
                return await self._finish(user_input)
            found = await self._search(str(user_input.get(CONF_DEVICE_ID) or "").strip().upper())
            if len(found) == 1:
                return await self._finish(_with_unit(user_input, found[0]))
            if found:
                self._entered = user_input
                self._found = {unit.device_id: unit for unit in found}
                return await self.async_step_pick()
            errors["base"] = "no_units_found"
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}, with_name=True), errors=errors
        )

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user pick one of the units the search found."""
        if user_input is not None:
            unit = self._found[user_input[CONF_DEVICE_ID]]
            return await self._finish(_with_unit(self._entered, unit))
        options = {unit.device_id: f"{unit.device_id} ({unit.host})" for unit in self._found.values()}
        return self.async_show_form(
            step_id="pick",
            data_schema=probatio.Schema({probatio.Required(CONF_DEVICE_ID): probatio.In(options)}),
        )

    async def _search(self, device_id: str) -> list[DiscoveredDevice]:
        """The units on the network not set up yet; only the one with `device_id`, if given."""
        configured = self._async_current_ids(include_ignore=False)
        return [
            unit
            for unit in await search_units()
            if unit.device_id.upper() not in configured
            and (not device_id or unit.device_id.upper() == device_id)
        ]

    async def _finish(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry for what was entered, or show it again with its error.

        A unit found by the search is shown with its address and device id filled in, so that
        a wrong password can be corrected.
        """
        settings, error = await self._settings(user_input)
        if error is None:
            await self.async_set_unique_id(settings[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=settings[CONF_NAME], data=settings)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input, with_name=True),
            errors={"base": error},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the unit's address, or its password; the device id must stay the same."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            settings, error = await self._settings(
                {**user_input, CONF_NAME: entry.data[CONF_NAME]}
            )
            if error is None:
                await self.async_set_unique_id(settings[CONF_DEVICE_ID])
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data=settings)
            errors["base"] = error
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(dict(user_input or entry.data), with_name=False),
            errors=errors,
        )

    async def _settings(self, user_input: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        """The entry's data from what was entered, and the error to show, if any."""
        host = str(user_input[CONF_HOST]).strip()
        device_id = str(user_input.get(CONF_DEVICE_ID) or "").strip().upper()
        password = str(user_input[CONF_PASSWORD])
        if not device_id:
            try:
                device_id = await find_device_id(host)
            except DeviceIdNotFoundError:
                return {}, "device_id_not_found"
        settings = {
            CONF_NAME: str(user_input[CONF_NAME]).strip() or DEFAULT_NAME,
            CONF_HOST: host,
            CONF_DEVICE_ID: device_id,
            CONF_PASSWORD: password,
        }
        return settings, await _check(host, device_id, password)


def _with_unit(user_input: dict[str, Any], unit: DiscoveredDevice) -> dict[str, Any]:
    """What was entered, with the address and device id of a unit the search found."""
    return {**user_input, CONF_HOST: unit.host, CONF_DEVICE_ID: unit.device_id}
