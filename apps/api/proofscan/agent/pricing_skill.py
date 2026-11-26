import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from statistics import median
from urllib.parse import urlsplit

from .guardrails import device_models, device_title
from .market import (
    MARKETS,
    PRICE_AMOUNT,
    SearchFact,
    clean_text,
    money_minor,
    safe_result,
    search_results,
)
from .schemas import LaunchPrice, Market, MarketRange, PriceAssessment, QuoteCondition

APPLE_15_PRO_RELEASE = "newsroom/2023/09/apple-unveils-iphone-15-pro-and-iphone-15-pro-max/"
APPLE_MARKET_PATH = {"IN": "/in/", "GB": "/uk/", "US": "/"}
APPLE_15_PRO_PRICES = {"IN": (134_900, 159_900), "GB": (999, 1199), "US": (999, 1199)}
SAMSUNG_S24_RELEASE = "https://news.samsung.com/us/enter-new-era-of-mobile-ai-samsung-galaxy-s24-series/"
SAMSUNG_S24_PRICES = {
    "galaxy s24": (79_999, 128),
    "galaxy s24 plus": (99_999, 256),
    "galaxy s24 ultra": (129_999, 256),
}


def published_launch(device: str, market: Market) -> LaunchPrice | None:
    if device in {"iphone 15 pro", "iphone 15 pro max"}:
        index = int(device.endswith(" max"))
        return LaunchPrice(
            year=2023,
            price_minor=APPLE_15_PRO_PRICES[market][index] * 100,
            storage_gb=(128, 256)[index],
            href="https://www.apple.com" + APPLE_MARKET_PATH[market] + APPLE_15_PRO_RELEASE,
        )
    if market == "US" and (samsung := SAMSUNG_S24_PRICES.get(device)):
        amount, storage = samsung
        return LaunchPrice(year=2024, price_minor=amount, storage_gb=storage, href=SAMSUNG_S24_RELEASE)
    return None


def apple_launch_from_results(
    payload: object, device: str, market: Market, year: int
) -> LaunchPrice | None:
    items = payload.get("search_results") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    _, currency, symbol, _ = MARKETS[market]
    press_path = re.compile(
        APPLE_MARKET_PATH[market]
        + r"newsroom/(20\d{2})/\d{2}/apple-(?:unveils|introduces|debuts|announces|launches)-[\w-]+/?"
    )
    starting_price = re.compile(
        rf"\b{re.escape(device)} (?:starts? at|will start at|starting at|is priced at|remains at the same starting price of) "
        rf"((?:{symbol})\s*{PRICE_AMOUNT})(?!\d|[.,]\d)"
    )
    matches: dict[tuple[int, int], LaunchPrice] = {}
    for item in items[:12]:
        if not isinstance(item, dict):
            continue
        url, title, snippet = (item.get(field) for field in ("url", "title", "snippet"))
        if not isinstance(url, str) or not isinstance(title, str) or not isinstance(snippet, str):
            continue
        link = safe_result(url, ("apple.com",))
        if link is None or device not in device_models(clean_text(title, 400)):
            continue
        release = press_path.fullmatch(urlsplit(link[1]).path)
        if not release or not 2007 <= int(release[1]) <= year:
            continue
        text = clean_text(snippet, 1500)
        for claim in starting_price.finditer(text):
            if amount := money_minor(claim[1], symbol, currency):
                announced_year = int(release[1])
                matches[(announced_year, amount)] = LaunchPrice(
                    year=announced_year, price_minor=amount, href=link[1]
                )
    return next(iter(matches.values())) if len(matches) == 1 else None


async def lookup_launch(device: str, market: Market) -> LaunchPrice | None:
    known = published_launch(device, market)
    if (
        known
        or device_models(device) != [device]
        or not device.startswith("iphone ")
        or device == "iphone se"
    ):
        return known
    country, currency, _, _ = MARKETS[market]
    payload = await search_results(
        f"site:apple.com/newsroom {device} {country} {currency} original starting price Apple announcement"
    )
    return apple_launch_from_results(payload, device, market, date.today().year)


def price_assessment(
    device: str,
    market: Market,
    quotes: Iterable[SearchFact],
    launch: LaunchPrice | None,
    storage_gb: int | None,
    condition: QuoteCondition | None,
) -> PriceAssessment:
    _, currency, _, merchants = MARKETS[market]
    assessment = PriceAssessment(
        device=device_title(device), market=market, currency=currency, launch=launch
    )
    if device.startswith(("macbook ", "thinkpad ")) or device == "iphone se":
        return assessment

    groups: dict[tuple[int, QuoteCondition], dict[str, int]] = defaultdict(dict)
    for quote in quotes:
        size, quality, amount = quote.storage_gb, quote.condition, quote.price_minor
        if (
            quote.device != device
            or quote.merchant not in merchants
            or size is None
            or quality is None
            or amount is None
        ):
            continue
        if (storage_gb is not None and size != storage_gb) or (
            condition is not None and quality != condition
        ):
            continue
        groups[size, quality].setdefault(quote.merchant, amount)

    eligible = [
        group
        for group in groups.items()
        if len(group[1]) >= 2 and max(group[1].values()) <= 2 * min(group[1].values())
    ]
    if not eligible:
        return assessment
    (size, quality), sources = max(eligible, key=lambda group: len(group[1]))
    prices = list(sources.values())
    assessment.current = MarketRange(
        low_minor=min(prices),
        high_minor=max(prices),
        median_minor=round(median(prices)),
        storage_gb=size,
        condition=quality,
        merchant_count=len(prices),
    )
    return assessment
