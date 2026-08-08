"""Config flow for JDECo."""
from __future__ import annotations

from typing import Any
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .api import JDecoAPI, JDecoAPIError
from .const import DOMAIN, CONF_AGREEMENT_NO, CONF_DEVICE_ID

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class JDecoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JDECo."""

    VERSION = 1

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._device_id: str = str(uuid.uuid4())
        self._agreements: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """First step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = JDecoAPI(session, self._username, self._password, self._device_id)
            try:
                await api.authenticate()
                self._agreements = await api.get_agreements()
                if not self._agreements:
                    errors["base"] = "no_agreements"
                else:
                    return await self.async_step_agreement()
            except JDecoAPIError:
                errors["base"] = "auth_failed"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    async def async_step_agreement(self, user_input: dict[str, Any] | None = None):
        """Second step: choose agreement."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=f"JDECo {user_input[CONF_AGREEMENT_NO]}",
                data={
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_AGREEMENT_NO: user_input[CONF_AGREEMENT_NO],
                    CONF_DEVICE_ID: self._device_id,
                },
            )

        options = {
            f"{a.get('agreementNo', a.get('agreementNumber', '?'))} – {a.get('address', '')}": a.get(
                'agreementNo', a.get('agreementNumber')
            )
            for a in self._agreements
        }
        schema = vol.Schema({vol.Required(CONF_AGREEMENT_NO): vol.In(options)})
        return self.async_show_form(step_id="agreement", data_schema=schema, errors=errors)
