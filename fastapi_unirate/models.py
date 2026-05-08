"""Pydantic ``Money`` type for response bodies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from fastapi_unirate.client import UniRateClient


class Money(BaseModel):
    """Amount + currency pair that the conversion middleware can rewrite.

    The middleware looks for response objects shaped like ``{"amount": ...,
    "currency": "..."}`` and rewrites them to a request-scoped target
    currency. Use this type in your response models so OpenAPI schemas stay
    accurate, but the middleware will also rewrite plain dicts of the same
    shape.
    """

    model_config = ConfigDict(extra="forbid")

    amount: float
    currency: str = Field(..., min_length=3, max_length=10)

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, v: str) -> str:
        return v.upper()

    async def convert_to(self, client: UniRateClient, currency: str) -> Money:
        """Return a new ``Money`` converted into ``currency`` at the latest rate."""
        if currency.upper() == self.currency:
            return self
        new_amount = await client.convert(
            from_currency=self.currency,
            to_currency=currency,
            amount=self.amount,
        )
        return Money(amount=new_amount, currency=currency.upper())
