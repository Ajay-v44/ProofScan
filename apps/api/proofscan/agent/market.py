import asyncio
import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlsplit, urlunsplit

import httpx

from ..config import settings
from .guardrails import device_models, normalized
from .schemas import Market

WEB_TIMEOUT = 7
MAX_RESPONSE_BYTES = 192_000
MARKETS = {
    "IN": (
        "India",
        "INR",
        r"₹|\binr\b|\brs\.?",
        ("amazon.in", "flipkart.com", "croma.com", "reliancedigital.in", "cashify.in"),
    ),
    "US": (
        "United States",
        "USD",
        r"\$|\busd\b|\bus\$",
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
    r"\b(?:per month|monthly|emi|installments?|per week|trade[ -]in|launch price|was priced|starting at|up to|save)\b|/\s*(?:mo|month)\b"
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


def safe_result(raw: str, domains: tuple[str, ...]) -> tuple[str, str] | None:
    try:
        url = urlsplit(raw)
        host = (url.hostname or "").removeprefix("www.")
        if (
            url.scheme != "https"
            or host not in domains
            or url.username
            or url.password
            or url.port not in {None, 443}
        ):
            return None
    except ValueError:
        return None
    if not re.fullmatch(r"/[A-Za-z0-9._/%+~-]{3,420}", url.path) or UNWANTED_LINK.search(url.path):
        return None
    if "%" in url.path or ".." in url.path or "//" in url.path:
        return None
    return host, urlunsplit(("https", url.netloc, url.path, "", ""))


def price_detail(text: str, symbol: str, currency: str) -> str | None:
    if FINANCING.search(text):
        return None
    numeric = r"(\d{1,6}(?:[ ,]\d{2,3}){0,3}(?:\.\d{2})?)"
    amounts = re.findall(rf"(?:{symbol})\s*{numeric}(?!\d|[.,]\d)", text)
    unique = {amount.replace(",", "").replace(" ", "") for amount in amounts}
    if len(unique) != 1:
        return None
    value = unique.pop()
    whole, _, decimal = value.partition(".")
    if not 20 <= int(whole) <= 5_000_000 or (currency == "INR" and int(whole) < 1000):
        return None
    amount = f"{int(whole):,}" + ("." + decimal if decimal and decimal != "00" else "")
    condition = (
        "refurbished"
        if re.search(r"\b(?:refurbished|renewed)\b", text)
        else "used"
        if re.search(r"\b(?:used|pre-owned)\b", text)
        else "condition unconfirmed"
    )
    return f"{currency} {amount} · {condition}"


def facts_from_results(payload: object, device: str, market: Market, pricing: bool) -> list[SearchFact]:
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
        if link is None or link[1] in seen or device_models(unescape(title[:400])) != [device]:
            continue
        text = normalized(unescape(re.sub(r"<[^>]{0,60}>", " ", title[:400] + " " + snippet[:1500])))
        if pricing:
            detail = price_detail(text, symbol, currency) or "Open listing for price and availability"
        else:
            details = [
                f"{label.capitalize()} {match[1]}{unit}"
                for label, pattern, unit in SPECS
                if (match := pattern.search(text))
            ]
            detail = " · ".join(details[:3]) or "Open the product page for specifications"
        seen.add(link[1])
        facts.append(SearchFact(device, link[0], link[1], detail))
    return sorted(facts, key=lambda item: item.detail.startswith("Open"))[:3]


async def search_market(device: str, market: Market, *, pricing: bool) -> list[SearchFact] | None:
    config = settings()
    if not config.kimi_api_key or device_models(device) != [device]:
        return None
    country, currency, _, _ = MARKETS[market]
    # No conversation text, account data, or locally retrieved records cross this boundary.
    query = (
        f"{device} {country} {currency} price retail refurbished"
        if pricing
        else f"{device} {country} official specifications"
    )
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
        return facts_from_results(json.loads(body), device, market, pricing)
    except (httpx.HTTPError, TimeoutError, ValueError, UnicodeError):
        return None
