"""Async client tests using respx to mock the UniRate API."""

from __future__ import annotations

import httpx
import pytest
import respx

from fastapi_unirate import UniRateAPIError, UniRateClient

BASE = "https://api.unirateapi.com"


@pytest.fixture
def client() -> UniRateClient:
    return UniRateClient(api_key="test-key")


@respx.mock
async def test_get_rate_pair_returns_float(client: UniRateClient) -> None:
    respx.get(f"{BASE}/api/rates").mock(
        return_value=httpx.Response(200, json={"rate": "0.92"})
    )
    rate = await client.get_rate("USD", "EUR")
    assert rate == pytest.approx(0.92)
    request = respx.calls.last.request
    assert request.url.params["from"] == "USD"
    assert request.url.params["to"] == "EUR"
    assert request.url.params["api_key"] == "test-key"
    assert request.headers["accept"] == "application/json"
    await client.aclose()


@respx.mock
async def test_get_rate_all_returns_dict(client: UniRateClient) -> None:
    respx.get(f"{BASE}/api/rates").mock(
        return_value=httpx.Response(
            200,
            json={"rates": {"EUR": "0.92", "GBP": "0.78"}},
        )
    )
    rates = await client.get_rate("USD")
    assert rates == {"EUR": 0.92, "GBP": 0.78}
    await client.aclose()


@respx.mock
async def test_convert_returns_result(client: UniRateClient) -> None:
    respx.get(f"{BASE}/api/convert").mock(
        return_value=httpx.Response(200, json={"result": "92.0"})
    )
    out = await client.convert("USD", "EUR", 100)
    assert out == pytest.approx(92.0)
    await client.aclose()


@respx.mock
async def test_get_supported_currencies(client: UniRateClient) -> None:
    respx.get(f"{BASE}/api/currencies").mock(
        return_value=httpx.Response(200, json={"currencies": ["USD", "EUR"]})
    )
    out = await client.get_supported_currencies()
    assert out == ["USD", "EUR"]
    await client.aclose()


@respx.mock
async def test_convert_historical_pro_endpoint(client: UniRateClient) -> None:
    respx.get(f"{BASE}/api/historical/rates").mock(
        return_value=httpx.Response(200, json={"result": "91.5"})
    )
    out = await client.convert_historical("USD", "EUR", "2024-01-15", 100)
    assert out == pytest.approx(91.5)
    request = respx.calls.last.request
    assert request.url.params["date"] == "2024-01-15"
    await client.aclose()


@respx.mock
@pytest.mark.parametrize(
    ("status", "expected_message"),
    [
        (401, "Missing or invalid"),
        (403, "Pro subscription"),
        (404, "Currency not found"),
        (429, "rate limit"),
        (500, "HTTP 500"),
    ],
)
async def test_error_mapping(
    client: UniRateClient, status: int, expected_message: str
) -> None:
    respx.get(f"{BASE}/api/rates").mock(return_value=httpx.Response(status))
    with pytest.raises(UniRateAPIError) as excinfo:
        await client.get_rate("USD", "EUR")
    assert excinfo.value.status_code == status
    assert expected_message.lower() in str(excinfo.value).lower()
    await client.aclose()


async def test_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        UniRateClient(api_key="")


async def test_async_context_manager_closes() -> None:
    async with UniRateClient(api_key="k") as c:
        assert isinstance(c, UniRateClient)
    # No assertion on internals — just ensures __aexit__ runs cleanly.
