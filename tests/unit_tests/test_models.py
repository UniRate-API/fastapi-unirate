"""Money model tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from fastapi_unirate import Money, UniRateClient

BASE = "https://api.unirateapi.com"


def test_currency_normalised_to_upper() -> None:
    m = Money(amount=10, currency="usd")
    assert m.currency == "USD"


def test_currency_required_min_length() -> None:
    with pytest.raises(ValidationError):
        Money(amount=10, currency="x")


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": 1, "currency": "USD", "precision": 2})


def test_serialises_round_trip() -> None:
    m = Money(amount=19.99, currency="USD")
    dumped = m.model_dump()
    assert dumped == {"amount": 19.99, "currency": "USD"}
    assert Money(**dumped) == m


@respx.mock
async def test_convert_to_calls_client() -> None:
    respx.get(f"{BASE}/api/convert").mock(
        return_value=httpx.Response(200, json={"result": "9.2"})
    )
    client = UniRateClient(api_key="k")
    money = Money(amount=10, currency="USD")
    out = await money.convert_to(client, "eur")
    assert out == Money(amount=9.2, currency="EUR")
    await client.aclose()


async def test_convert_to_same_currency_skips_call() -> None:
    # No respx mock — the test passes only if no HTTP call is made.
    client = UniRateClient(api_key="k")
    money = Money(amount=10, currency="USD")
    out = await money.convert_to(client, "USD")
    assert out is money
    await client.aclose()
