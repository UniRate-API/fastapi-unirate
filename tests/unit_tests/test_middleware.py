"""Conversion middleware tests against a real FastAPI app via TestClient."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_unirate import (
    CurrencyConversionMiddleware,
    Money,
    UniRateClient,
    unirate_lifespan,
)

BASE = "https://api.unirateapi.com"


def _build_app() -> FastAPI:
    app = FastAPI(lifespan=unirate_lifespan(api_key="test-key"))
    app.add_middleware(CurrencyConversionMiddleware)

    @app.get("/widget")
    async def _widget() -> dict[str, Money]:
        return {"price": Money(amount=100.0, currency="USD")}

    @app.get("/cart")
    async def _cart() -> dict[str, Any]:
        return {
            "items": [
                {"name": "a", "price": {"amount": 10.0, "currency": "USD"}},
                {"name": "b", "price": {"amount": 20.0, "currency": "USD"}},
            ],
            "total": {"amount": 30.0, "currency": "USD"},
        }

    @app.get("/no-money")
    async def _no_money() -> dict[str, str]:
        return {"hello": "world"}

    @app.get("/mixed")
    async def _mixed() -> dict[str, Any]:
        return {
            "label": "amount field but no currency",
            "amount": 7.0,
            "nested": {"amount": 5.0, "currency": "USD"},
        }

    return app


@respx.mock
def test_middleware_passes_through_when_no_query_param() -> None:
    app = _build_app()
    with TestClient(app) as c:
        resp = c.get("/widget")
    assert resp.status_code == 200
    assert resp.json() == {"price": {"amount": 100.0, "currency": "USD"}}


@respx.mock
def test_middleware_rewrites_top_level_money() -> None:
    convert = respx.get(f"{BASE}/api/convert").mock(
        return_value=httpx.Response(200, json={"result": "92.0"})
    )
    app = _build_app()
    with TestClient(app) as c:
        resp = c.get("/widget?currency=EUR")
    assert resp.status_code == 200
    assert resp.json() == {"price": {"amount": 92.0, "currency": "EUR"}}
    assert convert.called
    assert convert.calls.last.request.url.params["from"] == "USD"
    assert convert.calls.last.request.url.params["to"] == "EUR"
    assert convert.calls.last.request.url.params["amount"] == "100.0"


@respx.mock
def test_middleware_rewrites_nested_and_lists() -> None:
    # Two distinct (currency, amount) pairs → 2 calls expected, not 3
    # (the cart has two items + one total, but {USD,30} and the items
    # are all different amounts).
    respx.get(f"{BASE}/api/convert").mock(
        side_effect=[
            httpx.Response(200, json={"result": "9.2"}),
            httpx.Response(200, json={"result": "18.4"}),
            httpx.Response(200, json={"result": "27.6"}),
        ]
    )
    app = _build_app()
    with TestClient(app) as c:
        resp = c.get("/cart?currency=EUR")
    assert resp.status_code == 200
    body = resp.json()
    assert {n["price"]["currency"] for n in body["items"]} == {"EUR"}
    assert body["total"]["currency"] == "EUR"
    amounts = sorted(
        [n["price"]["amount"] for n in body["items"]] + [body["total"]["amount"]]
    )
    assert amounts == pytest.approx(sorted([9.2, 18.4, 27.6]))


@respx.mock
def test_middleware_skips_dicts_missing_keys() -> None:
    convert = respx.get(f"{BASE}/api/convert").mock(
        return_value=httpx.Response(200, json={"result": "4.6"})
    )
    app = _build_app()
    with TestClient(app) as c:
        resp = c.get("/mixed?currency=EUR")
    assert resp.status_code == 200
    body = resp.json()
    # Only the nested Money is rewritten; the loose ``amount`` field stays.
    assert body["amount"] == 7.0
    assert body["nested"] == {"amount": 4.6, "currency": "EUR"}
    assert convert.call_count == 1


@respx.mock
def test_middleware_passthrough_on_api_error() -> None:
    respx.get(f"{BASE}/api/convert").mock(return_value=httpx.Response(429))
    app = _build_app()
    with TestClient(app) as c:
        resp = c.get("/widget?currency=EUR")
    assert resp.status_code == 200
    # Original body returned unchanged.
    assert resp.json() == {"price": {"amount": 100.0, "currency": "USD"}}


@respx.mock
def test_middleware_skips_non_json_responses() -> None:
    from fastapi.responses import PlainTextResponse

    app = _build_app()

    @app.get("/text", response_class=PlainTextResponse)
    async def _text() -> str:
        return "plain"

    with TestClient(app) as c:
        resp = c.get("/text?currency=EUR")
    assert resp.status_code == 200
    assert resp.text == "plain"


@respx.mock
def test_middleware_same_currency_no_call() -> None:
    convert = respx.get(f"{BASE}/api/convert")
    app = _build_app()
    with TestClient(app) as c:
        resp = c.get("/widget?currency=USD")
    assert resp.status_code == 200
    assert resp.json() == {"price": {"amount": 100.0, "currency": "USD"}}
    assert not convert.called


@respx.mock
def test_middleware_custom_query_param() -> None:
    respx.get(f"{BASE}/api/convert").mock(
        return_value=httpx.Response(200, json={"result": "78.0"})
    )
    app = FastAPI(lifespan=unirate_lifespan(api_key="test-key"))
    app.add_middleware(CurrencyConversionMiddleware, query_param="display_currency")

    @app.get("/p")
    async def _p() -> Money:
        return Money(amount=100.0, currency="USD")

    with TestClient(app) as c:
        # `currency` should now be ignored; only `display_currency` triggers.
        unchanged = c.get("/p?currency=EUR")
        rewritten = c.get("/p?display_currency=GBP")
    assert unchanged.json() == {"amount": 100.0, "currency": "USD"}
    assert rewritten.json() == {"amount": 78.0, "currency": "GBP"}


@respx.mock
def test_middleware_explicit_client_override() -> None:
    respx.get(f"{BASE}/api/convert").mock(
        return_value=httpx.Response(200, json={"result": "55.5"})
    )
    override_client = UniRateClient(api_key="override-key")

    app = FastAPI()  # Note: no lifespan — middleware uses override.
    app.add_middleware(CurrencyConversionMiddleware, client=override_client)

    @app.get("/p")
    async def _p() -> Money:
        return Money(amount=100.0, currency="USD")

    with TestClient(app) as c:
        resp = c.get("/p?currency=EUR")
    assert resp.json() == {"amount": 55.5, "currency": "EUR"}
