"""FastAPI integration for the UniRate currency-exchange API."""

from fastapi_unirate.client import UniRateAPIError, UniRateClient
from fastapi_unirate.dependencies import (
    UniRateDep,
    get_unirate_client,
    unirate_lifespan,
)
from fastapi_unirate.middleware import CurrencyConversionMiddleware
from fastapi_unirate.models import Money

__all__ = [
    "CurrencyConversionMiddleware",
    "Money",
    "UniRateAPIError",
    "UniRateClient",
    "UniRateDep",
    "get_unirate_client",
    "unirate_lifespan",
]

__version__ = "0.1.0"
