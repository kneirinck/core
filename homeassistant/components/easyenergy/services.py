"""Services for easyEnergy integration."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from functools import partial
from typing import Final

from easyenergy import Electricity, Gas, VatOption
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EasyEnergyDataUpdateCoordinator

ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_INCL_VAT: Final = "incl_vat"

GAS_SERVICE_NAME: Final = "get_gas_prices"
ENERGY_USAGE_SERVICE_NAME: Final = "get_energy_usage_prices"
ENERGY_RETURN_SERVICE_NAME: Final = "get_energy_return_prices"
SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(ATTR_START): str,
        vol.Optional(ATTR_END): str,
        vol.Required(ATTR_INCL_VAT, default=True): bool,
    }
)


class PriceType(str, Enum):
    """Type of price."""

    ENERGY_USAGE = "energy_usage"
    ENERGY_RETURN = "energy_return"
    GAS = "gas"


def __get_date(date_input: str | None) -> date | datetime:
    """Get date."""
    if not date_input:
        return dt_util.now().date()

    if value := dt_util.parse_datetime(date_input):
        return value

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_date",
        translation_placeholders={
            "date": date_input,
        },
    )


def __serialize_prices(prices: list[dict[str, float | datetime]]) -> ServiceResponse:
    """Serialize prices to service response."""
    return {
        "prices": [
            {
                key: str(value) if isinstance(value, datetime) else value
                for key, value in timestamp_price.items()
            }
            for timestamp_price in prices
        ]
    }


async def __get_prices(
    call: ServiceCall,
    *,
    coordinator: EasyEnergyDataUpdateCoordinator,
    price_type: PriceType,
) -> ServiceResponse:
    """Get prices from easyEnergy."""
    start = __get_date(call.data.get(ATTR_START))
    end = __get_date(call.data.get(ATTR_END))

    vat = VatOption.INCLUDE
    if call.data.get(ATTR_INCL_VAT) is False:
        vat = VatOption.EXCLUDE

    data: Electricity | Gas

    if price_type == PriceType.GAS:
        data = await coordinator.easyenergy.gas_prices(
            start_date=start,
            end_date=end,
            vat=vat,
        )
        return __serialize_prices(data.timestamp_prices)
    data = await coordinator.easyenergy.energy_prices(
        start_date=start,
        end_date=end,
        vat=vat,
    )

    if price_type == PriceType.ENERGY_USAGE:
        return __serialize_prices(data.timestamp_usage_prices)
    return __serialize_prices(data.timestamp_return_prices)


@callback
def async_setup_services(
    hass: HomeAssistant,
    coordinator: EasyEnergyDataUpdateCoordinator,
) -> None:
    """Set up services for easyEnergy integration."""

    hass.services.async_register(
        DOMAIN,
        GAS_SERVICE_NAME,
        partial(__get_prices, coordinator=coordinator, price_type=PriceType.GAS),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_USAGE_SERVICE_NAME,
        partial(
            __get_prices, coordinator=coordinator, price_type=PriceType.ENERGY_USAGE
        ),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_RETURN_SERVICE_NAME,
        partial(
            __get_prices, coordinator=coordinator, price_type=PriceType.ENERGY_RETURN
        ),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )