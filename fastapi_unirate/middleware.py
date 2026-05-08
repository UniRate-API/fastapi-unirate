"""ASGI middleware that auto-converts Money values in JSON responses.

Reads a target currency from a configurable query parameter (default
``?currency=``) and rewrites every ``Money``-shaped object in the response
JSON to that currency at the latest UniRate rate.

A ``Money``-shaped object is a dict (or list of dicts) with both ``amount``
(numeric) and ``currency`` (string) keys.

Conversions are done concurrently per response and cached for the duration
of the request.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastapi_unirate.client import UniRateAPIError, UniRateClient

_STATE_KEY = "unirate_client"


class CurrencyConversionMiddleware:
    """Rewrite Money-shaped values in JSON responses to a request-scoped currency.

    Args:
        app: The ASGI app to wrap.
        query_param: Name of the query parameter that holds the target
            currency (default ``"currency"``).
        client: Override the lifespan-managed client (mostly for tests).

    Behaviour:
        - Only acts on ``application/json`` responses with a 2xx status.
        - Skips when the query parameter is absent.
        - Leaves the response untouched on any UniRate API error so the
            handler's response still reaches the user.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        query_param: str = "currency",
        client: UniRateClient | None = None,
    ) -> None:
        self.app = app
        self.query_param = query_param
        self._override_client = client

    def _resolve_client(self, scope: Scope) -> UniRateClient | None:
        if self._override_client is not None:
            return self._override_client
        app: FastAPI | None = scope.get("app")
        if app is None:
            return None
        return getattr(app.state, _STATE_KEY, None)

    @staticmethod
    def _target_from_query(scope: Scope, key: str) -> str | None:
        raw_qs = scope.get("query_string") or b""
        if not raw_qs:
            return None
        from urllib.parse import parse_qs

        parsed = parse_qs(raw_qs.decode("latin-1"))
        values = parsed.get(key)
        if not values:
            return None
        target = values[0].strip().upper()
        return target or None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        target = self._target_from_query(scope, self.query_param)
        if target is None:
            await self.app(scope, receive, send)
            return

        client = self._resolve_client(scope)
        if client is None:
            await self.app(scope, receive, send)
            return

        body = bytearray()
        response_start: Message | None = None
        content_type = ""

        async def _send(message: Message) -> None:
            nonlocal response_start, content_type
            if message["type"] == "http.response.start":
                response_start = message
                for name, value in message.get("headers", []):
                    if name.decode("latin-1").lower() == "content-type":
                        content_type = value.decode("latin-1").lower()
                        break
                # Defer sending the start until we know the rewritten body length.
                return
            if message["type"] == "http.response.body":
                body.extend(message.get("body") or b"")
                if message.get("more_body"):
                    return
                # End of body — try to rewrite.
                rewritten = await _maybe_rewrite(
                    bytes(body), content_type, client, target
                )
                if response_start is not None:
                    headers = [
                        (name, value)
                        for name, value in response_start.get("headers", [])
                        if name.decode("latin-1").lower() != "content-length"
                    ]
                    headers.append(
                        (
                            b"content-length",
                            str(len(rewritten)).encode("latin-1"),
                        )
                    )
                    response_start["headers"] = headers
                    await send(response_start)
                await send({"type": "http.response.body", "body": rewritten})
                return
            await send(message)

        await self.app(scope, receive, _send)


async def _maybe_rewrite(
    body: bytes,
    content_type: str,
    client: UniRateClient,
    target: str,
) -> bytes:
    """Rewrite Money values in a JSON body. Pass-through on any failure."""
    if "application/json" not in content_type:
        return body
    if not body:
        return body
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body

    money_nodes = list(_iter_money_nodes(data))
    if not money_nodes:
        return body

    cache: dict[tuple[str, float], float] = {}
    try:
        await asyncio.gather(
            *(_rewrite_node(node, target, client, cache) for node in money_nodes)
        )
    except UniRateAPIError:
        return body

    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def _iter_money_nodes(value: Any) -> Iterator[dict[str, Any]]:
    """Yield every dict that looks like a Money value, depth-first."""
    if isinstance(value, dict):
        if _is_money(value):
            yield value
        for v in value.values():
            yield from _iter_money_nodes(v)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_money_nodes(item)


def _is_money(value: dict[str, Any]) -> bool:
    if "amount" not in value or "currency" not in value:
        return False
    amount = value["amount"]
    currency = value["currency"]
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        return False
    if not isinstance(currency, str) or not currency:
        return False
    return True


async def _rewrite_node(
    node: dict[str, Any],
    target: str,
    client: UniRateClient,
    cache: dict[tuple[str, float], float],
) -> None:
    src_currency = str(node["currency"]).upper()
    if src_currency == target:
        node["currency"] = target
        return
    amount = float(node["amount"])
    cache_key = (src_currency, amount)
    if cache_key in cache:
        node["amount"] = cache[cache_key]
        node["currency"] = target
        return
    converted = await client.convert(
        from_currency=src_currency,
        to_currency=target,
        amount=amount,
    )
    cache[cache_key] = converted
    node["amount"] = converted
    node["currency"] = target


__all__ = ["CurrencyConversionMiddleware"]
