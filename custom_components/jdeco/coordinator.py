"""DataUpdateCoordinator for JDECo."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import JDecoAPI, JDecoAPIError, JDecoAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class JDecoDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from JDECo."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: JDecoAPI,
        agreement_no: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.api = api
        self.agreement_no = agreement_no

    async def _async_update_data(self):
        """Fetch the latest data concurrently."""
        try:
            agree_no = self.agreement_no
            
            # Run all API calls concurrently instead of sequentially
            # This significantly reduces total update time
            (
                details,
                debt,
                last_voucher,
                kw_qty,
            ) = await asyncio.gather(
                self.api.get_agreement_details(agree_no),
                self.api.get_agreement_debt(agree_no),
                self.api.get_last_voucher(agree_no),
                self.api.get_kw_qty(agree_no),
                return_exceptions=True,  # Don't fail entire update if one call fails
            )

            # Handle individual call failures gracefully
            if isinstance(details, Exception):
                _LOGGER.warning("Failed to get agreement details: %s", details)
                details = {}
            if isinstance(debt, Exception):
                _LOGGER.debug("Failed to get agreement debt: %s", debt)
                debt = {}
            if isinstance(last_voucher, Exception):
                _LOGGER.debug("Failed to get last voucher: %s", last_voucher)
                last_voucher = {}
            if isinstance(kw_qty, Exception):
                _LOGGER.debug("Failed to get kW quantity: %s", kw_qty)
                kw_qty = {}

            return {
                "details": details,
                "debt": debt,
                "last_voucher": last_voucher,
                "kw_qty": kw_qty,
                "agreement_no": agree_no,
            }
        except JDecoAuthError as exc:
            _LOGGER.error("Authentication failed: %s", exc)
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except JDecoAPIError as exc:
            _LOGGER.error("API error during update: %s", exc)
            raise UpdateFailed(str(exc)) from exc
        except Exception as exc:
            _LOGGER.error("Unexpected error during update: %s", exc)
            raise UpdateFailed(f"Unexpected error: {exc}") from exc
