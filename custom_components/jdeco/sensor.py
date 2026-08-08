"""Sensor platform for JDECo."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JDecoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors."""
    coordinator: JDecoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JDecoRemainingKwhSensor(coordinator)])


class JDecoRemainingKwhSensor(CoordinatorEntity, SensorEntity):
    """Remaining kWh sensor."""

    _attr_name = "JDECo Remaining kWh"
    _attr_native_unit_of_measurement = "kWh"

    def __init__(self, coordinator: JDecoDataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.agreement_no}_kwh"

    @property
    def available(self) -> bool:
        """Check if sensor data is available."""
        if not self.coordinator.last_update_success:
            return False
        
        # Sensor is available if we have kw_qty data or other key data
        data = self.coordinator.data or {}
        kw_qty = data.get("kw_qty", {})
        return bool(kw_qty and (kw_qty.get("qty") or kw_qty.get("kwQty") or kw_qty.get("remainingQuantity")))

    @property
    def native_value(self) -> float | None:
        """Return the remaining kWh value."""
        try:
            data = self.coordinator.data or {}
            kw_qty = data.get("kw_qty", {})
            
            # Try multiple field names that the API might return
            val = (
                kw_qty.get("qty")
                or kw_qty.get("kwQty")
                or kw_qty.get("remainingQuantity")
            )
            
            if val is not None:
                return float(val)
            
            _LOGGER.debug("No remaining quantity found in kw_qty response: %s", kw_qty)
            return None
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Failed to parse remaining kWh value: %s", err)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error getting native_value: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        try:
            data = self.coordinator.data or {}
            
            # Safely extract values with fallbacks
            agreement_no = data.get("agreement_no")
            last_voucher = data.get("last_voucher", {})
            debt = data.get("debt", {})
            details = data.get("details", {})
            
            attributes = {
                "agreement_no": agreement_no,
                "last_voucher_amount": last_voucher.get("amount") if last_voucher else None,
                "debt_amount": debt.get("amount") if debt else None,
            }
            
            # Add meter type info if available
            if details:
                if details.get("isPrepaidMeter"):
                    attributes["meter_type"] = "Prepaid"
                elif details.get("isSmartMeter"):
                    attributes["meter_type"] = "Smart"
                
                # Add address if available
                if details.get("address"):
                    attributes["address"] = details["address"]
            
            return attributes
        except Exception as err:
            _LOGGER.error("Error building extra_state_attributes: %s", err)
            return {"agreement_no": self.coordinator.agreement_no}
