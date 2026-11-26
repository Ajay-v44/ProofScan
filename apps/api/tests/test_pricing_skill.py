from uuid import uuid4

import pytest

from proofscan.agent import chat
from proofscan.agent.market import facts_from_results
from proofscan.agent.pricing_skill import apple_launch_from_results, price_assessment, published_launch
from proofscan.agent.schemas import ChatRequest
from proofscan.agent.telemetry import AgentTrace

DEVICE = "iphone 15 pro"


def retailer(host, amount, *, size=128, condition="refurbished", name="iPhone 15 Pro", suffix=""):
    return {
        "title": f"{name} {size} GB {condition}",
        "url": f"https://{host}/retail/iphone-15-pro{suffix}",
        "snippet": amount,
    }


def range_from(items, *, size=128, condition="refurbished"):
    quotes = facts_from_results({"search_results": items}, DEVICE, "IN", True)
    return price_assessment(DEVICE, "IN", quotes, published_launch(DEVICE, "IN"), size, condition)


def test_assessment_uses_same_capacity_and_condition_with_distinct_merchants():
    result = range_from(
        [
            retailer("cashify.in", "₹ 49,999"),
            retailer("flipkart.com", "INR 52,001"),
            retailer("amazon.in", "₹ 62,000", size=256),
            retailer("croma.com", "₹ 44,000", condition="Used"),
            retailer("reliancedigital.in", "₹ 52,000", name="iPhone 15 Pro Max"),
        ]
    )
    assert result.launch is not None
    assert (result.launch.year, result.launch.price_minor, result.launch.storage_gb) == (
        2023,
        13_490_000,
        128,
    )
    assert result.current is not None
    assert (result.current.low_minor, result.current.high_minor, result.current.median_minor) == (
        4_999_900,
        5_200_100,
        5_100_000,
    )
    assert (result.current.merchant_count, result.current.storage_gb, result.current.condition) == (
        2,
        128,
        "refurbished",
    )


@pytest.mark.parametrize(
    "second", ["₹ 50,000 sold out", "₹ 5,000 EMI", "₹ 49,990 down to ₹ 45,000", "₹ 150,000", "US$ 600"]
)
def test_withholds_range_for_noncomparable_quotes(second):
    result = range_from([retailer("cashify.in", "₹ 49,999"), retailer("flipkart.com", second)])
    assert result.current is None and result.launch is not None


def test_one_merchant_never_counts_as_two_independent_quotes():
    result = range_from(
        [retailer("cashify.in", "₹ 49,999"), retailer("www.cashify.in", "₹ 51,000", suffix="-two")]
    )
    assert result.current is None


def test_us_listing_does_not_confuse_foreign_dollar_price():
    quotes = facts_from_results(
        {"search_results": [retailer("bestbuy.com", "CA$ 500")]}, DEVICE, "US", True
    )
    assert quotes[0].price_minor is None


def test_launch_parser_requires_manufacturer_region_and_explicit_model_price():
    packet = {
        "search_results": [
            {
                "url": "https://www.apple.com/ca/newsroom/2024/09/apple-unveils-iphone-16-pro/",
                "title": "Apple unveils iPhone 16 Pro",
                "snippet": "iPhone 16 Pro starts at $1,449.",
            },
            {
                "url": "https://www.apple.com/newsroom/2024/09/apple-unveils-iphone-16-pro/",
                "title": "Apple unveils iPhone 16 Pro and iPhone 16 Pro Max",
                "snippet": "iPhone 16 Pro starts at $999 or $41.62 per month. iPhone 16 Pro Max starts at $1,199.",
            },
        ]
    }
    launch = apple_launch_from_results(packet, "iphone 16 pro", "US", 2026)
    assert launch and launch.year == 2024 and launch.price_minor == 99_900 and launch.storage_gb is None
    assert apple_launch_from_results(packet, "iphone 16", "US", 2026) is None


async def private_lookup(*_args):
    pytest.fail("Public pricing accessed private records")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "What is the iPhone 15 Pro worth in Canada?",
        "What is the iPhone 15 Pro price in India and the UK?",
        "How much is an iPhone 15 Pro 128GB or 256GB?",
    ],
)
async def test_chat_clarifies_ambiguous_prices_before_calling_search(monkeypatch, question):
    async def unexpected_search(*_args, **_kwargs):
        pytest.fail("Pricing searched before clarifying the requested comparison")

    monkeypatch.setattr(chat, "search_market", unexpected_search)
    result = await chat.build_chat(
        ChatRequest(message=question),
        AgentTrace(uuid4(), "recommendation"),
        private_lookup,
        private_lookup,
    )
    assert result.status == "needs_input"


@pytest.mark.asyncio
async def test_chat_keeps_launch_price_when_market_provider_is_down(monkeypatch):
    async def unavailable(*_args, **_kwargs):
        return None

    monkeypatch.setattr(chat, "search_market", unavailable)
    answer = await chat.build_chat(
        ChatRequest(message="What did the iPhone 15 Pro launch at and what is it worth now?"),
        AgentTrace(uuid4(), "recommendation"),
        private_lookup,
        private_lookup,
    )
    assert answer.status == "answer" and answer.checked_at is None
    assert answer.pricing[0].launch is not None and answer.pricing[0].current is None


@pytest.mark.asyncio
async def test_chat_does_not_price_quotes_removed_by_verifier(monkeypatch):
    async def market_search(device, market, **_kwargs):
        return facts_from_results(
            {
                "search_results": [
                    retailer("croma.com", "INR 50,000"),
                    retailer("cashify.in", "₹ 49,999"),
                ]
            },
            device,
            market,
            True,
        )

    async def review(first_pass, *_args):
        return first_pass[:1]

    monkeypatch.setattr(chat, "search_market", market_search)
    monkeypatch.setattr(chat, "review", review)
    answer = await chat.build_chat(
        ChatRequest(message="How much is an iPhone 15 Pro refurbished 128GB in India?"),
        AgentTrace(uuid4(), "recommendation"),
        private_lookup,
        private_lookup,
    )
    assert len(answer.sources) == 1
    assert answer.pricing[0].current is None
