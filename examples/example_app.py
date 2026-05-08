"""End-to-end FastAPI demo for fastapi-unirate.

Run:

    UNIRATE_API_KEY=... uvicorn examples.example_app:app

Then:

    curl http://127.0.0.1:8000/products/widget
    curl 'http://127.0.0.1:8000/products/widget?currency=EUR'
    curl http://127.0.0.1:8000/rate/USD/JPY
    curl http://127.0.0.1:8000/convert/USD/EUR/100
"""

from __future__ import annotations

from fastapi import FastAPI

from fastapi_unirate import (
    CurrencyConversionMiddleware,
    Money,
    UniRateDep,
    unirate_lifespan,
)

app = FastAPI(
    title="fastapi-unirate example",
    lifespan=unirate_lifespan(),
)
app.add_middleware(CurrencyConversionMiddleware)


@app.get("/products/widget")
async def get_widget() -> dict[str, Money]:
    """Demonstrates the conversion middleware: hit ?currency=EUR to rewrite."""
    return {"price": Money(amount=19.99, currency="USD")}


@app.get("/rate/{base}/{quote}")
async def get_rate(base: str, quote: str, client: UniRateDep) -> dict[str, float]:
    """Demonstrates the dependency: directly call the client."""
    return {"rate": await client.get_rate(base, quote)}


@app.get("/convert/{base}/{quote}/{amount}")
async def convert(
    base: str, quote: str, amount: float, client: UniRateDep
) -> dict[str, float]:
    return {"result": await client.convert(base, quote, amount)}
