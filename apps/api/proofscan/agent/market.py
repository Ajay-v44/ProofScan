import asyncio
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from html import unescape
from urllib.parse import urlsplit, urlunsplit

import httpx

from ..config import settings
from .guardrails import device_models, normalized
from .schemas import Market, QuoteCondition

WEB_TIMEOUT = 7
MAX_RESPONSE_BYTES = 192_000
MARKETS = {
    "IN": (
        "India",
        "INR",
        r"₹|\binr\b|\brs\.?",
        (
            "amazon.in",
            "flipkart.com",
            "croma.com",
            "reliancedigital.in",
            "cashify.in",
            "controlz.world",
            "refitglobal.com",
            "sahivalue.com",
        ),
    ),
    "US": (
        "United States",
        "USD",
        r"\bus\$|(?<!\w)\$|\busd\b\s*\$?",
        ("amazon.com", "bestbuy.com", "swappa.com", "walmart.com", "backmarket.com"),
    ),
    "GB": (
        "United Kingdom",
        "GBP",
        r"£|\bgbp\b",
        ("amazon.co.uk", "argos.co.uk", "johnlewis.com", "backmarket.co.uk", "currys.co.uk"),
    ),
}
MANUFACTURERS = ("apple.com", "samsung.com", "store.google.com", "oneplus.com", "mi.com", "lenovo.com")
FINANCING = re.compile(
    r"\b(?:per month|monthly|emi|installments?|per week|trade[ -]in|launch price|msrp|was priced|starting at|up to|save|sold out|out of stock|currently unavailable|parts only|prepaid price|card offer)\b|/\s*(?:mo|month)\b"
)
PRICE_AMOUNT = r"(\d{1,6}(?:[ ,]\d{2,3}){0,3}(?:\.\d{2})?)"
STORAGE = re.compile(r"\b(?:(64|128|256|512|1024|2048)\s*gb|([12])\s*tb)\b")
ACCESSORIES = re.compile(
    r"\b(?:phone case|protective case|screen protector|replacement screen|replacement battery|parts only|repair kit|sim tray)\b"
)
CONDITIONS: tuple[tuple[QuoteCondition, re.Pattern[str]], ...] = (
    ("refurbished", re.compile(r"\b(?:refurbished|renewed|reconditioned)\b")),
    ("used", re.compile(r"\b(?:used|pre[ -]owned|second[ -]hand)\b")),
    ("new", re.compile(r"\b(?:brand[ -]new|factory sealed|new in box)\b")),
)
UNWANTED_LINK = re.compile(
    r"/(?:redirect|outbound|login|account|signin|cart|checkout|gp/slredirect)(?:/|$)", re.IGNORECASE
)
SPECS = (
    (
        "display size",
        re.compile(
            r"\b(\d{1,2}(?:\.\d{1,2})?)\s*[- ]?inch(?:es)?\s+(?:[a-z]+\s+){0,3}(?:display|screen)\b"
        ),
        " in",
    ),
    ("memory", re.compile(r"\b(\d{1,3})\s*g(?:i)?b\s+(?:of\s+)?ram\b"), " GB RAM"),
    ("refresh rate", re.compile(r"\b(\d{2,3})\s*hz\b"), " Hz"),
    ("battery capacity", re.compile(r"\b(\d{4,5})\s*mah\b"), " mAh"),
    ("camera resolution", re.compile(r"\b(\d{1,3})\s*mp\s+(?:main |rear |front )?camera\b"), " MP"),
)


@dataclass(frozen=True)
class SearchFact:
    device: str
    merchant: str
    href: str
    detail: str
    price_minor: int | None = None
    condition: QuoteCondition | None = None
    storage_gb: int | None = None


def safe_result(raw: str, domains: tuple[str, ...]) -> tuple[str, str] | None:
    try:
        url = urlsplit(raw)
        host = (url.hostname or "").removeprefix("www.")
        if (
            url.scheme != "https"
            or host not in domains
            or url.username is not None
            or url.password is not None
            or url.port not in {None, 443}
        ):
            return None
    except ValueError:
        return None
    if not re.fullmatch(r"/[A-Za-z0-9._/%+~-]{3,420}", url.path) or UNWANTED_LINK.search(url.path):
        return None
    if "%" in url.path or ".." in url.path or "//" in url.path:
        return None
    return host, urlunsplit(("https", url.hostname or host, url.path, "", ""))


def money_minor(text: str, symbol: str, currency: str) -> int | None:
    amounts = re.findall(rf"(?:{symbol})\s*{PRICE_AMOUNT}(?!\d|[.,]\d)", text)
    unique = {int(Decimal(amount.replace(",", "").replace(" ", "")) * 100) for amount in amounts}
    if len(unique) != 1:
        return None
    value = unique.pop()
    if not 2_000 <= value <= 500_000_000 or (currency == "INR" and value < 100_000):
        return None
    return value


def format_money(value: int, currency: str) -> str:
    whole, cents = divmod(value, 100)
    return f"{currency} {whole:,}" + (f".{cents:02d}" if cents else "")


def storage_values(text: str) -> set[int]:
    return {int(gb) if gb else int(tb) * 1024 for gb, tb in STORAGE.findall(text)}


def quote_condition(text: str) -> QuoteCondition | None:
    matches = [condition for condition, pattern in CONDITIONS if pattern.search(text)]
    return matches[0] if len(matches) == 1 else None


def clean_text(value: str, size: int) -> str:
    return normalized(re.sub(r"<[^>]{0,60}>", " ", unescape(value[:size])))


def facts_from_results(
    payload: object,
    device: str,
    market: Market,
    pricing: bool,
    *,
    storage_gb: int | None = None,
    preferred_condition: QuoteCondition | None = None,
) -> list[SearchFact]:
    _, currency, symbol, merchants = MARKETS[market]
    domains = (*merchants, *MANUFACTURERS)
    items = payload.get("search_results") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    facts: list[SearchFact] = []
    seen: set[str] = set()
    for item in items[:12]:
        if not isinstance(item, dict):
            continue
        url, title, snippet = (item.get(field) for field in ("url", "title", "snippet"))
        if not isinstance(url, str) or not isinstance(title, str) or not isinstance(snippet, str):
            continue
        link = safe_result(url, domains)
        title = clean_text(title, 400)
        if link is None or link[1] in seen or device_models(title) != [device]:
            continue
        text = title + " " + clean_text(snippet, 1500)
        amount, condition, storage = None, None, None
        if pricing:
            if not FINANCING.search(text) and not ACCESSORIES.search(title):
                amount = money_minor(text, symbol, currency)
                condition = quote_condition(text)
                sizes = storage_values(text)
                storage = sizes.pop() if len(sizes) == 1 else None
            detail = "Open listing for price and availability"
            if amount is not None:
                size_detail = f" · {storage} GB" if storage else ""
                detail = f"{format_money(amount, currency)} · {condition or 'condition unconfirmed'}{size_detail}"
        else:
            details = [
                f"{label.capitalize()} {match[1]}{unit}"
                for label, pattern, unit in SPECS
                if (match := pattern.search(text))
            ]
            detail = " · ".join(details[:3]) or "Open the product page for specifications"
        seen.add(link[1])
        facts.append(SearchFact(device, link[0], link[1], detail, amount, condition, storage))
    if not pricing:
        return sorted(facts, key=lambda item: item.detail.startswith("Open"))[:3]
    ranked = sorted(
        facts,
        key=lambda item: (
            item.price_minor is None,
            storage_gb is not None and item.storage_gb != storage_gb,
            preferred_condition is not None and item.condition != preferred_condition,
            item.storage_gb is None or item.condition is None,
        ),
    )
    first_per_merchant: dict[str, SearchFact] = {}
    for item in ranked:
        first_per_merchant.setdefault(item.merchant, item)
    selected = list(first_per_merchant.values())[:3]
    if len(selected) < 3:
        selected.extend(item for item in ranked if item not in selected)
    return selected[:3]


async def search_results(query: str) -> object:
    config = settings()
    if not config.kimi_api_key:
        return None
    try:
        async with (
            asyncio.timeout(WEB_TIMEOUT),
            httpx.AsyncClient(follow_redirects=False, timeout=WEB_TIMEOUT) as client,
        ):
            async with client.stream(
                "POST",
                config.kimi_base_url.rstrip("/") + "/tools/search",
                headers={"Authorization": "Bearer " + config.kimi_api_key.get_secret_value()},
                json={"text_query": query, "limit": 10, "timeout_seconds": 6, "include_content": False},
            ) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        return None
        return json.loads(body)
    except (httpx.HTTPError, TimeoutError, ValueError, UnicodeError):
        return None


async def search_market(
    device: str,
    market: Market,
    *,
    pricing: bool,
    storage_gb: int | None = None,
    condition: QuoteCondition | None = None,
) -> list[SearchFact] | None:
    if device_models(device) != [device]:
        return None
    country, currency, _, _ = MARKETS[market]
    # Only known device models, market labels and validated shopping options are sent.
    if pricing:
        storage = f" {storage_gb}GB" if storage_gb in {64, 128, 256, 512, 1024, 2048} else ""
        condition_hint = condition if condition in {"used", "refurbished", "new"} else "refurbished"
        query = f"{device}{storage} {country} {currency} price retail {condition_hint}"
    else:
        query = f"{device} {country} official specifications"
    payload = await search_results(query)
    if payload is None:
        return None
    return facts_from_results(
        payload, device, market, pricing, storage_gb=storage_gb, preferred_condition=condition
    )
