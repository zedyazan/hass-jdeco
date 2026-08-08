"""DataUpdateCoordinator for JDECo."""
from __future__ import annotations

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
        """Fetch the latest data."""
        try:
            agree_no = self.agreement_no
            details = await self.api.get_agreement_details(agree_no)
            try:
                debt = await self.api.get_agreement_debt(agree_no)
            except JDecoAPIError:
                debt = {}
            try:
                last_voucher = await self.api.get_last_voucher(agree_no)
            except JDecoAPIError:
                last_voucher = {}
            kw_qty: dict = {}
            if details.get("isPrepaidMeter") or details.get("isSmartMeter"):
                try:
                    kw_qty = await self.api.get_kw_qty(agree_no)
                except JDecoAPIError:
                    pass

            return {
                "details": details,
                "debt": debt,
                "last_voucher": last_voucher,
                "kw_qty": kw_qty,
                "agreement_no": agree_no,
            }
        except JDecoAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except JDecoAPIError as exc:
            raise UpdateFailed(str(exc)) from exc
        except Exception as exc:
            raise UpdateFailed(f"Unexpected error: {exc}") from exc
