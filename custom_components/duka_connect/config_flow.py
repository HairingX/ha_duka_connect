"""Set up a Duka One, and change where it is reached or its password."""

from __future__ import annotations

import logging
from typing import Any

import probatio
from duka_connect import (
    DEFAULT_PASSWORD,
    CannotConnectError,
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
    if with_name:
        fields[probatio.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME))] = str
    fields[probatio.Required(CONF_HOST, default=defaults.get(CONF_HOST, ""))] = str
    fields[probatio.Optional(CONF_DEVICE_ID, default=defaults.get(CONF_DEVICE_ID, ""))] = str
    fields[probatio.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, DEFAULT_PASSWORD))] = str
    return probatio.Schema(fields)


class DukaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a unit by its address; its device id is asked for when it is left empty."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the unit's name, address, device id and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            settings, error = await self._settings(user_input)
            if error is None:
                await self.async_set_unique_id(settings[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=settings[CONF_NAME], data=settings)
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}, with_name=True), errors=errors
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
