"""FastAPI dependency wiring for :class:`UniRateClient`."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request

from fastapi_unirate.client import UniRateClient

_STATE_KEY = "unirate_client"


def unirate_lifespan(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
) -> Callable[[FastAPI], Any]:
    """Return a FastAPI ``lifespan`` callable that owns a single shared client.

    Reads ``UNIRATE_API_KEY`` from the environment when ``api_key`` is not
    passed.

    Example:
        .. code-block:: python

            from fastapi import FastAPI
            from fastapi_unirate import unirate_lifespan

            app = FastAPI(lifespan=unirate_lifespan())
    """

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        key = api_key or os.environ.get("UNIRATE_API_KEY")
        if not key:
            msg = (
                "UniRate API key not set — pass api_key= to unirate_lifespan() "
                "or set UNIRATE_API_KEY in the environment"
            )
            raise RuntimeError(msg)
        kwargs: dict[str, Any] = {}
        if base_url is not None:
            kwargs["base_url"] = base_url
        if timeout is not None:
            kwargs["timeout"] = timeout
        client = UniRateClient(api_key=key, **kwargs)
        setattr(app.state, _STATE_KEY, client)
        try:
            yield
        finally:
            await client.aclose()

    return _lifespan


def get_unirate_client(request: Request) -> UniRateClient:
    """``Depends`` provider that returns the lifespan-managed client.

    Raises:
        RuntimeError: If the app was started without ``unirate_lifespan``
            (or another wiring that puts a ``UniRateClient`` on
            ``app.state.unirate_client``).
    """
    client = getattr(request.app.state, _STATE_KEY, None)
    if client is None:
        msg = (
            "UniRateClient is not configured. Wire up the app with "
            "fastapi_unirate.unirate_lifespan() or assign a client to "
            "app.state.unirate_client manually."
        )
        raise RuntimeError(msg)
    return client


# Convenience alias for path-operation signatures.
UniRateDep = Annotated[UniRateClient, Depends(get_unirate_client)]


__all__ = [
    "UniRateDep",
    "get_unirate_client",
    "unirate_lifespan",
]
