"""Config flow for JDECo."""
from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .api import JDecoAPI, JDecoAPIError, JDecoAuthError
from .const import DOMAIN, CONF_AGREEMENT_NO, CONF_DEVICE_ID

_LOGGER = logging.getLogger(__name__)

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
        self._api: JDecoAPI | None = None  # Cache API instance to avoid re-auth

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """First step: collect credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            session = aiohttp_client.async_get_clientsession(self.hass)
            
            # Create API instance (will be reused in next step)
            self._api = JDecoAPI(session, self._username, self._password, self._device_id)
            
            try:
                _LOGGER.debug("Attempting authentication...")
                await self._api.authenticate()
                _LOGGER.debug("Authentication successful, fetching agreements...")
                
                self._agreements = await self._api.get_agreements()
                if not self._agreements:
                    errors["base"] = "no_agreements"
                    _LOGGER.warning("No agreements found for user %s", self._username)
                else:
                    _LOGGER.debug("Found %d agreement(s), proceeding to selection", len(self._agreements))
                    return await self.async_step_agreement()
            except JDecoAuthError as err:
                errors["base"] = "auth_failed"
                _LOGGER.error("Authentication failed: %s", err)
            except JDecoAPIError as err:
                errors["base"] = "api_error"
                _LOGGER.error("API error during setup: %s", err)
            except Exception as err:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected error during setup")

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

        # Build dropdown options from agreements
        options = {}
        for agreement in self._agreements:
            # Handle different response formats from API
            agreement_no = agreement.get("agreementNo") or agreement.get("agreementNumber")
            address = agreement.get("address", "")
            
            if agreement_no:
                # Create human-readable label
                label = f"{agreement_no}"
                if address:
                    label = f"{agreement_no} – {address}"
                options[label] = agreement_no

        if not options:
            errors["base"] = "no_agreements"
            return self.async_show_form(step_id="agreement", errors=errors)

        schema = vol.Schema({vol.Required(CONF_AGREEMENT_NO): vol.In(options)})
        return self.async_show_form(step_id="agreement", data_schema=schema, errors=errors)
