"""DI provider + lifespan tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_unirate import UniRateDep, unirate_lifespan

BASE = "https://api.unirateapi.com"


def _build_app() -> FastAPI:
    app = FastAPI(lifespan=unirate_lifespan(api_key="test-key"))

    @app.get("/rate")
    async def _rate(client: UniRateDep) -> dict[str, float]:
        rate = await client.get_rate("USD", "EUR")
        assert isinstance(rate, float)
        return {"rate": rate}

    return app


@respx.mock
def test_dependency_injects_client() -> None:
    respx.get(f"{BASE}/api/rates").mock(
        return_value=httpx.Response(200, json={"rate": "0.91"})
    )
    app = _build_app()
    with TestClient(app) as test_client:
        resp = test_client.get("/rate")
    assert resp.status_code == 200
    assert resp.json() == {"rate": 0.91}


def test_lifespan_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIRATE_API_KEY", raising=False)
    app = FastAPI(lifespan=unirate_lifespan())
    with pytest.raises(RuntimeError, match="UniRate API key not set"):
        with TestClient(app):
            pass


def test_lifespan_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIRATE_API_KEY", "from-env")
    app = FastAPI(lifespan=unirate_lifespan())

    @app.get("/check")
    async def _check(client: UniRateDep) -> dict[str, str]:
        return {"key": client.api_key}

    with TestClient(app) as test_client:
        resp = test_client.get("/check")
    assert resp.status_code == 200
    assert resp.json() == {"key": "from-env"}


def test_dependency_errors_when_no_lifespan() -> None:
    app = FastAPI()

    @app.get("/r")
    async def _r(client: UniRateDep) -> dict[str, str]:
        return {"key": client.api_key}

    with TestClient(app, raise_server_exceptions=False) as test_client:
        resp = test_client.get("/r")
    assert resp.status_code == 500
