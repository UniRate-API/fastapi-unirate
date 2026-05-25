# fastapi-unirate

[![PyPI](https://img.shields.io/pypi/v/fastapi-unirate.svg)](https://pypi.org/project/fastapi-unirate/)
[![Python](https://img.shields.io/pypi/pyversions/fastapi-unirate.svg)](https://pypi.org/project/fastapi-unirate/)
[![License](https://img.shields.io/pypi/l/fastapi-unirate.svg)](https://github.com/UniRate-API/fastapi-unirate/blob/main/LICENSE)

FastAPI integration for the [UniRate](https://unirateapi.com) currency-exchange API:

- **Async dependency** — `Depends(get_unirate_client)` plus a typed
  `UniRateDep` alias for path-operation signatures.
- **Lifespan helper** — one shared `httpx.AsyncClient`-backed UniRate client
  per app, opened on startup and closed on shutdown.
- **`Money` Pydantic type** — amount + currency pair that round-trips
  through OpenAPI schemas.
- **`CurrencyConversionMiddleware`** — auto-rewrites Money-shaped values in
  JSON responses to a request-scoped target currency
  (`?currency=EUR`).

UniRate covers 593+ fiat, crypto, and commodity codes. Latest rates and
conversion are on the free tier; historical endpoints
(`convert_historical`) require Pro.

## Install

```bash
pip install fastapi-unirate
```

Or with uv / Poetry:

```bash
uv add fastapi-unirate
poetry add fastapi-unirate
```

## Quick start

```python
import os

from fastapi import FastAPI
from fastapi_unirate import (
    CurrencyConversionMiddleware,
    Money,
    UniRateDep,
    unirate_lifespan,
)

app = FastAPI(lifespan=unirate_lifespan())  # reads UNIRATE_API_KEY from env
app.add_middleware(CurrencyConversionMiddleware)


@app.get("/products/widget")
async def get_widget() -> dict[str, Money]:
    return {"price": Money(amount=19.99, currency="USD")}


@app.get("/rate/{base}/{quote}")
async def rate(base: str, quote: str, client: UniRateDep) -> dict[str, float]:
    return {"rate": await client.get_rate(base, quote)}
```

Then:

```
$ curl localhost:8000/products/widget
{"price":{"amount":19.99,"currency":"USD"}}

$ curl localhost:8000/products/widget?currency=EUR
{"price":{"amount":18.42,"currency":"EUR"}}

$ curl localhost:8000/rate/USD/JPY
{"rate":151.83}
```

The middleware finds every `{"amount": <number>, "currency": "<code>"}`
shape — top-level, nested, or inside lists — and rewrites it. Conversions
are de-duplicated per request and run concurrently.

## Configuration

`unirate_lifespan` accepts overrides:

```python
app = FastAPI(
    lifespan=unirate_lifespan(
        api_key="...",                         # default: $UNIRATE_API_KEY
        base_url="https://api.unirateapi.com", # default: production
        timeout=15.0,                          # default: 30s
    )
)
```

`CurrencyConversionMiddleware` accepts the query-parameter name and an
explicit client (mostly for testing):

```python
app.add_middleware(
    CurrencyConversionMiddleware,
    query_param="display_currency",
)
```

## Why a middleware?

The dossier sketched two integration shapes — DI and middleware — and
both pull their weight:

- The DI provider is the right tool when a handler explicitly wants to
  call `convert()` or `get_rate()`.
- The middleware is the right tool when a service has a stable
  `Money`-shaped response and wants to expose
  *one* `?currency=` knob to clients without rewriting every handler.

You can use either, or both together (as in the quick-start example).

## Errors

The client raises `UniRateAPIError` on non-2xx responses (with
`status_code` set). Common cases:

| HTTP | Meaning                                         |
|------|-------------------------------------------------|
| 401  | Missing or invalid API key                      |
| 403  | Pro subscription required (historical, commodities) |
| 404  | Currency not found                              |
| 429  | Rate limit exceeded                             |

The middleware swallows `UniRateAPIError` and passes the original
response through unchanged — so an upstream UniRate outage never becomes
a 500 on your service.

## Compatibility

- Python 3.9 – 3.13
- FastAPI ≥ 0.100
- Pydantic ≥ 2.0

## Related

- [`unirate-api`](https://pypi.org/project/unirate-api/) — sync UniRate
  Python client (this package vendors a small async equivalent so it
  doesn't pull in `requests`).
- [`langchain-unirate`](https://pypi.org/project/langchain-unirate/) —
  LangChain partner package.
- Other UniRate integrations: dbt, Airflow, n8n, Raycast, MCP server.
  Full list at <https://unirateapi.com>.

<!-- unirate-ecosystem-footer:start -->
## Other UniRate clients

UniRate ships official client libraries and framework integrations across the
ecosystem. The repos below are all maintained under the
[UniRate-API](https://github.com/UniRate-API) org.

- **Languages:** [Python](https://github.com/UniRate-API/unirate-api-python) · [Node.js / TypeScript](https://github.com/UniRate-API/unirate-api-nodejs) · [Go](https://github.com/UniRate-API/unirate-api-go) · [Rust](https://github.com/UniRate-API/unirate-api-rust) · [Java](https://github.com/UniRate-API/unirate-api-java) · [Ruby](https://github.com/UniRate-API/unirate-api-ruby) · [PHP](https://github.com/UniRate-API/unirate-api-php) · [.NET](https://github.com/UniRate-API/unirate-api-dotnet) · [Swift](https://github.com/UniRate-API/unirate-api-swift)
- **Web frameworks:** [Django / Wagtail](https://github.com/UniRate-API/wagtail-unirate) · [FastAPI](https://github.com/UniRate-API/fastapi-unirate) · [Flask](https://github.com/UniRate-API/flask-unirate) · [React](https://github.com/UniRate-API/react-unirate) · [tRPC](https://github.com/UniRate-API/trpc-unirate)
- **Static-site generators:** [Astro](https://github.com/UniRate-API/astro-unirate) · [Eleventy](https://github.com/UniRate-API/eleventy-unirate) · [Hugo](https://github.com/UniRate-API/hugo-unirate)
- **Data / orchestration:** [Airflow](https://github.com/UniRate-API/airflow-provider-unirate) · [dbt](https://github.com/UniRate-API/dbt-unirate) · [LangChain](https://github.com/UniRate-API/langchain-unirate)
- **Workflow / no-code:** [n8n](https://github.com/UniRate-API/n8n-nodes-unirate) · [Google Sheets](https://github.com/UniRate-API/unirate-sheets) · [MCP server](https://github.com/UniRate-API/unirate-mcp)
- **Editors / tools:** [VS Code](https://github.com/UniRate-API/vscode-unirate) · [Obsidian](https://github.com/UniRate-API/obsidian-currency)
- **Specialty bridges:** [NodaMoney (.NET)](https://github.com/UniRate-API/UniRateApi.NodaMoney)

Get a free API key at [unirateapi.com](https://unirateapi.com).
<!-- unirate-ecosystem-footer:end -->

## License

MIT
