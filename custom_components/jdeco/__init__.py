"""JDECo integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .api import JDecoAPI, JDecoAuthError, JDecoAPIError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_AGREEMENT_NO, CONF_DEVICE_ID
from .coordinator import JDecoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up JDECo from a config entry."""
    try:
        _LOGGER.debug("Setting up JDECo integration for agreement %s", entry.data.get(CONF_AGREEMENT_NO))
        
        session = aiohttp_client.async_get_clientsession(hass)
        api = JDecoAPI(
            session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_DEVICE_ID),
        )
        
        # Authenticate with improved error messages
        _LOGGER.debug("Authenticating with JDECo API...")
        try:
            await api.authenticate()
        except JDecoAuthError as err:
            _LOGGER.error("Authentication failed - check your username/password: %s", err)
            return False
        except JDecoAPIError as err:
            _LOGGER.error("Failed to connect to JDECo API: %s", err)
            return False
        
        _LOGGER.debug("Authentication successful, creating coordinator...")
        coordinator = JDecoDataUpdateCoordinator(hass, api, entry.data[CONF_AGREEMENT_NO])
        
        # Perform initial data refresh
        await coordinator.async_config_entry_first_refresh()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        _LOGGER.debug("JDECo integration setup completed successfully")
        return True
    
    except Exception as err:
        _LOGGER.exception("Unexpected error during JDECo setup: %s", err)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading JDECo integration for entry %s", entry.entry_id)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.debug("JDECo integration unloaded successfully")
    return unload_ok
