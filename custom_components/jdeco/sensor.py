"""Sensor platform for JDECo."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JDecoDataUpdateCoordinator


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
    def native_value(self) -> float | None:
        kw_qty = self.coordinator.data.get("kw_qty", {})
        val = kw_qty.get("qty") or kw_qty.get("kwQty") or kw_qty.get("remainingQuantity")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        return None

    @property
    def extra_state_attributes(self):
        return {
            "agreement_no": self.coordinator.data.get("agreement_no"),
            "last_voucher_amount": self.coordinator.data.get("last_voucher", {}).get("amount"),
            "debt_amount": self.coordinator.data.get("debt", {}).get("amount"),
        }
