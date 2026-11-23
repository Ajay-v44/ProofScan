from datetime import timedelta

from proofscan.db import now
from proofscan.pricing import Comparable, RuleBasedPricing
from proofscan.schemas import Hardware


def test_pricing_requires_recent_distinct_sales_and_keeps_the_demo_separate():
    device = Hardware(manufacturer="Example", model="Model 1", memory_gib=16)
    pricing = RuleBasedPricing([])
    assert pricing.estimate(device, "windows") is None
    demo = pricing.estimate(device, "simulator")
    assert demo and demo.source == "SIMULATED"

    for index, amount in enumerate([500, 600, 700]):
        pricing.comparables.append(
            Comparable(
                device="Example Model 1",
                currency="USD",
                amount=amount,
                sold_on=now().date(),
                reference=f"fixture-{index}",
            )
        )
    result = pricing.estimate(device, "windows")
    assert result and result.source == "LOCAL_COMPARABLES" and result.sample_size == 3
    assert (result.low, result.high) == (500, 700)

    pricing.comparables[0].sold_on -= timedelta(days=91)
    assert pricing.estimate(device, "windows") is None
