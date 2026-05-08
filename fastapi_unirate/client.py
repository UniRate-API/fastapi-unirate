"""Async UniRate API client used by the FastAPI dependency."""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.unirateapi.com"
DEFAULT_TIMEOUT = 30.0


class UniRateAPIError(Exception):
    """Raised when the UniRate API returns a non-success response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UniRateClient:
    """Thin async client over the UniRate REST API.

    Wraps an ``httpx.AsyncClient`` so it slots cleanly into FastAPI's async
    request lifecycle. Use :func:`fastapi_unirate.unirate_lifespan` to manage
    a single client per app, or instantiate directly inside tests.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            msg = "api_key is required"
            raise ValueError(msg)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this instance owns it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> UniRateClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _request(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        full_params: dict[str, Any] = {"api_key": self.api_key}
        if params:
            full_params.update(params)
        try:
            response = await self._client.get(
                f"{self.base_url}{path}",
                params=full_params,
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            raise UniRateAPIError(f"UniRate request failed: {exc}") from exc

        if response.status_code == 401:
            raise UniRateAPIError("Missing or invalid UniRate API key", status_code=401)
        if response.status_code == 403:
            raise UniRateAPIError(
                "Endpoint requires a UniRate Pro subscription", status_code=403
            )
        if response.status_code == 404:
            raise UniRateAPIError(
                "Currency not found or no data available", status_code=404
            )
        if response.status_code == 429:
            raise UniRateAPIError("UniRate API rate limit exceeded", status_code=429)
        if response.status_code >= 400:
            raise UniRateAPIError(
                f"UniRate API error: HTTP {response.status_code}",
                status_code=response.status_code,
            )
        return response.json()

    async def get_rate(
        self, from_currency: str = "USD", to_currency: str | None = None
    ) -> float | dict[str, float]:
        """Return the latest rate, or a mapping of every target rate.

        Args:
            from_currency: ISO 4217 base currency code.
            to_currency: ISO 4217 target currency. If omitted, every supported
                target is returned.
        """
        params: dict[str, Any] = {"from": from_currency.upper()}
        if to_currency is not None:
            params["to"] = to_currency.upper()
        data = await self._request("/api/rates", params)
        if to_currency is not None:
            return float(data["rate"])
        return {code: float(rate) for code, rate in data["rates"].items()}

    async def convert(
        self,
        from_currency: str,
        to_currency: str,
        amount: float = 1.0,
    ) -> float:
        """Convert ``amount`` from one currency to another at the latest rate."""
        data = await self._request(
            "/api/convert",
            {
                "from": from_currency.upper(),
                "to": to_currency.upper(),
                "amount": amount,
            },
        )
        return float(data["result"])

    async def get_supported_currencies(self) -> list[str]:
        """Return every supported ISO/ticker code the API can convert between."""
        data = await self._request("/api/currencies")
        return list(data["currencies"])

    async def convert_historical(
        self,
        from_currency: str,
        to_currency: str,
        date: str,
        amount: float = 1.0,
    ) -> float:
        """Convert at the rate observed on ``date`` (YYYY-MM-DD). Pro-gated."""
        data = await self._request(
            "/api/historical/rates",
            {
                "from": from_currency.upper(),
                "to": to_currency.upper(),
                "amount": amount,
                "date": date,
            },
        )
        if "result" in data:
            return float(data["result"])
        return float(data["rate"])
