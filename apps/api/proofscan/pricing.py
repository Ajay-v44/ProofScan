from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Protocol

from pydantic import BaseModel, StringConstraints, TypeAdapter

from .config import settings
from .db import now
from .schemas import Hardware, Platform, Positive, PriceView


class Comparable(BaseModel):
    device: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=180)]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    amount: Positive
    sold_on: date
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=250)]


class PricingProvider(Protocol):
    def estimate(self, hardware: Hardware, platform: Platform) -> PriceView | None: ...


@dataclass
class RuleBasedPricing:
    comparables: list[Comparable]

    def estimate(self, hardware: Hardware, platform: Platform) -> PriceView | None:
        if platform == "simulator":
            low, high = (15_000, 19_000) if hardware.memory_gib == 16 else (8_000, 11_000)
            return PriceView(currency="INR", low=low, high=high, source="SIMULATED", sample_size=0)
        if not hardware.manufacturer or not hardware.model:
            return None
        label = " ".join([hardware.manufacturer, hardware.model]).casefold()
        today = now().date()
        # Use one record per sold listing and require prices in one currency.
        matched = {
            item.reference: item
            for item in self.comparables
            if item.device.casefold() == label and today - timedelta(days=90) <= item.sold_on <= today
        }
        currencies = {item.currency for item in matched.values()}
        if len(matched) < 3 or len(currencies) != 1:
            return None
        amounts = sorted(item.amount for item in matched.values())
        last = len(amounts) - 1
        return PriceView(
            currency=currencies.pop(),
            low=amounts[last // 4],
            high=amounts[(last * 3 + 3) // 4],
            source="LOCAL_COMPARABLES",
            sample_size=len(amounts),
        )


def read_comparables(path: Path) -> list[Comparable]:
    try:
        with path.open("rb") as file:
            data = file.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("The comparables file exceeds 2 MB")
        return TypeAdapter(list[Comparable]).validate_json(data)
    except (OSError, ValueError) as exc:
        raise ValueError("PRICING_COMPARABLES_FILE must contain valid sold comparable records") from exc


@lru_cache
def pricing_provider() -> PricingProvider:
    path = settings().pricing_comparables_file
    return RuleBasedPricing(read_comparables(path) if path else [])
