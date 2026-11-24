import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from ..config import settings
from ..db import now
from ..schemas import Input
from .catalog import CatalogSearch, requested_measurement
from .guardrails import device_models, device_title, normalized, sensitive_request
from .knowledge import Guide, find_guides
from .market import MARKETS, search_market
from .model import decide
from .schemas import ChatRequest, ChatResponse, ChatSource, Market, Question
from .telemetry import AgentTrace, Event

REFUSAL = "I can help with ProofScan, your shared reports, device buying, and handoffs. Try a question about one of those."
PRIVATE = re.compile(
    r"\b(?:my|our) (?:reports?|devices?|listings?|phones?|tablets?|laptops?|catalog)\b|\b(?:shared with me|verified devices|my shortlist)\b"
)
PRICE = re.compile(
    r"\b(?:pric(?:e|es|ing)|costs?|worth|market value|how much|best deal|retail|resale)\b"
)
RESEARCH = re.compile(
    r"\b(?:search|look up|specs?|specifications?|display|camera|processor|ram|storage|battery|refresh rate|compare|review|good|describe|tell me about|what do you think)\b"
)
BUYING_LIMIT = re.compile(
    r"\b(?:under|below|budget(?: of)?)\s*(?:₹|\$|£|inr|usd|gbp|rs\.?)?\s*(\d[\d,]{0,8})(k)?\b"
)
FOLLOWUP = re.compile(
    r"^(?:and |also |what about |how about |which (?:one|of (?:these|them))|why\b|does (?:it|that)\b|how much|cost\b|is (?:it|that)\b|what if|tell me more)"
)
SHOPPING = re.compile(
    r"\b(?:compare|pick|buy|choose|recommend|better|best|battery|memory|ram|storage|ssd|budget|phones?|laptops?|tablets?|models?|devices?|condition)\b"
)
LOWEST = re.compile(r"\b(?:lowest|least|worst|weakest|smallest|fewest|less)\b")
HIGHEST = re.compile(r"\b(?:highest|most|best|strongest|largest|more|healthiest)\b")

Intent = Literal["help", "catalog", "market", "specs", "outside"]


@dataclass(frozen=True)
class Plan:
    intent: Intent
    question: str
    history: str = ""
    models: tuple[str, ...] = ()
    market: Market = "IN"


@dataclass(frozen=True)
class Evidence:
    kind: Literal["help", "report", "listing", "web"]
    source: ChatSource
    sentence: str
    catalog_id: UUID | None = None


class Selection(Input):
    sources: list[Annotated[int, Field(ge=1, le=8)]] = Field(max_length=6)


def requested_market(text: str, fallback: Market) -> Market:
    if "$" in text or re.search(r"\b(?:united states|usa|usd|in the us)\b", text):
        return "US"
    if "£" in text or re.search(r"\b(?:united kingdom|uk|gbp|britain)\b", text):
        return "GB"
    if "₹" in text or re.search(r"\b(?:india|inr)\b", text):
        return "IN"
    return fallback


def make_plan(data: ChatRequest) -> Plan:
    question = normalized(data.message)
    if sensitive_request(question):
        return Plan("outside", "")
    history = [normalized(turn) for turn in reversed(data.history) if not sensitive_request(turn)]
    models = device_models(question)
    prior = ""
    if FOLLOWUP.search(question):
        prior = next(
            (
                turn
                for turn in history
                if device_models(turn) or find_guides(turn) or PRIVATE.search(turn)
            ),
            "",
        )
        models = models or device_models(prior)
    context = question + " " + prior
    market = requested_market(question, requested_market(prior, data.market))
    price_followup = prior and PRICE.search(prior) and not RESEARCH.search(question)
    if (
        (PRICE.search(question) or price_followup)
        and (models or SHOPPING.search(question))
        and not PRIVATE.search(context)
    ):
        return Plan("market", question, prior, tuple(models[:2]), market)
    if (
        models
        and not PRIVATE.search(context)
        and (
            RESEARCH.search(question)
            or SHOPPING.search(question)
            or question in models
            or FOLLOWUP.search(question)
        )
    ):
        return Plan("specs", question, prior, tuple(models[:2]), market)
    guides = find_guides(question)
    if (
        guides
        and (not SHOPPING.search(question) or re.search(r"^(?:how|what|where|can|do)\b", question))
        and (
            not PRIVATE.search(question)
            or re.search(
                r"^how (?:do|can|should) i (?:scan|check|open|verify|share|download|use|delete)\b",
                question,
            )
        )
    ):
        return Plan("help", question, prior)
    if PRIVATE.search(question) or re.search(
        r"\b(?:which|best|compare|recommend|pick)\b.{0,55}\b(?:battery|memory|ram|storage|phone|laptop|tablet|device)\b",
        question,
    ):
        return Plan("catalog", question, prior, market=market)
    if guides or (prior and find_guides(prior) and FOLLOWUP.search(question)):
        return Plan("help", question, prior)
    if SHOPPING.search(question) or (prior and PRIVATE.search(prior)):
        return Plan("catalog", question, prior, market=market)
    return Plan("outside", "")


def help_evidence(guides: list[Guide]) -> list[Evidence]:
    return [
        Evidence("help", ChatSource(kind="help", title=guide.title, href=guide.href), guide.text)
        for guide in guides
    ]


def wants_lowest(query: Question) -> bool:
    for message in (query.question, query.previous_question or ""):
        if LOWEST.search(message):
            return not HIGHEST.search(message)
        if HIGHEST.search(message):
            return False
    return False


async def catalog_evidence(
    data: ChatRequest,
    plan: Plan,
    search: Callable[[Question, str], Awaitable[CatalogSearch]],
    trace: AgentTrace,
) -> tuple[list[Evidence], str]:
    budget = None
    if cap := BUYING_LIMIT.search(plan.question) or BUYING_LIMIT.search(plan.history):
        amount = int(cap[1].replace(",", "")) * (1000 if cap[2] else 1)
        budget = amount if 1 <= amount <= 100_000_000 else None
    category_pattern = r"\b(phone|laptop|tablet)s?\b"
    categories = set(
        re.findall(category_pattern, plan.question) or re.findall(category_pattern, plan.history)
    )
    question = Question(
        question=plan.question[:600].ljust(3, "?"),
        previous_question=plan.history[:600] or None,
        category=categories.pop() if len(categories) == 1 else None,
        reports_only=not data.include_listings,
        budget=budget,
        currency=MARKETS[plan.market][1] if budget is not None else None,
    )
    started = perf_counter()
    result = await search(question, " ".join(filter(None, [plan.question, plan.history])))
    trace.events.append(Event("chat_catalog", result.mode, round((perf_counter() - started) * 1000)))
    measurement = requested_measurement(question)
    fields = (
        ("memory_gib", "Memory", " GiB"),
        ("storage_gb", "Largest drive", " GB"),
        ("battery_health_percent", "Battery health", "%"),
    )
    records: list[Evidence] = []
    measured: list[int] = []
    for index, item in enumerate(result.items[:4], 1):
        if item.verification_id:
            kind: Literal["report", "listing"] = "report"
            # Public device names come from a fixed grammar. Private labels never become answer prose.
            names = device_models(item.title)
            title = device_title(names[0]) if len(names) == 1 else f"Shared report {index}"
            href = f"/reports/{item.verification_id}"
        else:
            kind = "listing"
            title = f"Saved listing {index}"
            href = None
        facts = item.facts or {}
        if measurement and type(value := facts.get(measurement[0])) is int:
            measured.append(value)
        details = [
            f"{label} {value}{unit}"
            for field, label, unit in fields
            if type(value := facts.get(field)) is int
        ]
        if item.price is not None and item.currency:
            price_label = (
                "Comparable estimate up to" if facts.get("estimated_price") else "Saved asking price"
            )
            details.append(f"{price_label} {item.currency} {item.price:,}")
        detail = " · ".join(details) or "No collected measurements shown"
        records.append(
            Evidence(kind, ChatSource(kind=kind, title=title, href=href, detail=detail), "", item.id)
        )
    summary = "Open the evidence to compare the available readings and look for gaps before deciding."
    if measurement:
        _, label = measurement
        if not measured:
            summary = f"These sources have no recorded {label}. Use the reports to check which measurements are available."
        elif len(measured) == 1:
            summary = (
                f"Only one source has recorded {label}. More readings are needed to rank the devices."
            )
        else:
            order = "lowest" if wants_lowest(question) else "highest"
            if measured[0] == measured[1]:
                summary = f"The first two sources tie for the {order} recorded {label} among the results shown. Check the other readings and condition before paying."
            else:
                summary = f"The first source has the {order} recorded {label} among the results shown. Check the other readings and condition before paying."
    return records, summary


async def web_evidence(plan: Plan, trace: AgentTrace) -> tuple[list[Evidence], bool]:
    started = perf_counter()
    answers = await asyncio.gather(
        *(search_market(device, plan.market, pricing=plan.intent == "market") for device in plan.models)
    )
    records = [
        Evidence(
            "web",
            ChatSource(
                kind="web",
                title=f"{device_title(fact.device)} · {fact.merchant}",
                href=fact.href,
                detail=fact.detail,
            ),
            "",
        )
        for results in answers
        if results
        for fact in results
    ]
    trace.events.append(
        Event(
            "market_search" if plan.intent == "market" else "device_web_search",
            "found"
            if records
            else "empty"
            if any(answer is not None for answer in answers)
            else "unavailable",
            round((perf_counter() - started) * 1000),
        )
    )
    return records, all(answer is None for answer in answers)


async def review(
    evidence: list[Evidence], plan: Plan, data: ChatRequest, trace: AgentTrace
) -> list[Evidence]:
    started = perf_counter()
    if not evidence:
        return []
    allowed = {"help": {"help"}, "catalog": {"report", "listing"}, "market": {"web"}, "specs": {"web"}}
    eligible = [item for item in evidence if item.kind in allowed.get(plan.intent, set())][:6]
    verdict = "local"
    if data.allow_model and plan.intent in {"help", "market", "specs"} and eligible:
        # Candidate text is curated or deterministically extracted. The model gets no private catalog or URLs.
        facts = {
            "intent": plan.intent,
            "devices": plan.models,
            "market": plan.market,
            "evidence": [
                {"id": i, "title": item.source.title, "fact": item.sentence or item.source.detail}
                for i, item in enumerate(eligible, 1)
            ],
            "schema": Selection.model_json_schema(),
        }
        draft = await decide(
            "Select relevant evidence IDs. Return only the requested structured selection.",
            facts,
            Selection,
            trace,
            approved=True,
            operation="chat_select",
        )
        selected = (
            list(dict.fromkeys(index for index in draft.sources if index <= len(eligible)))
            if draft
            else []
        )
        if draft is None:
            verdict = "local_fallback"
        elif not selected:
            eligible, verdict = [], "withheld"
        else:
            review_result = await decide(
                "Review the proposed evidence for relevance and support. Return only IDs from the draft that you approve. Return an empty list if none qualify.",
                {**facts, "draft": selected},
                Selection,
                trace,
                approved=True,
                model=settings().agent_review_model,
                operation="chat_review",
            )
            if review_result is None:
                verdict = "local_fallback"
            else:
                accepted = set(review_result.sources) & set(selected)
                eligible = [item for i, item in enumerate(eligible, 1) if i in accepted]
                verdict = "approved" if eligible else "withheld"
    trace.events.append(Event("answer_verification", verdict, round((perf_counter() - started) * 1000)))
    return eligible


async def build_chat(
    data: ChatRequest,
    trace: AgentTrace,
    search: Callable[[Question, str], Awaitable[CatalogSearch]],
    still_owned: Callable[[set[UUID]], Awaitable[bool]],
) -> ChatResponse:
    plan = make_plan(data)
    if plan.intent == "outside":
        trace.events.append(Event("chat_scope", "declined", 0))
        return ChatResponse(status="outside_domain", message=REFUSAL)

    checked = None
    if plan.intent == "help":
        evidence = help_evidence(find_guides(plan.question) or find_guides(plan.history))
        summary = ""
    elif plan.intent == "catalog":
        evidence, summary = await catalog_evidence(data, plan, search, trace)
        if not evidence:
            return ChatResponse(
                status="needs_input",
                message="I found no devices in your available reports or listings. You can ask what to check before buying used, or name an exact device for public research.",
            )
    else:
        if not plan.models:
            return ChatResponse(
                status="needs_input",
                message="Which device should I look up? Include the exact model and variant, such as iPhone 15 Pro or Galaxy S24 Ultra. I’ll use the market selected in your chat settings unless you name another one.",
            )
        if not data.allow_web:
            return ChatResponse(
                status="needs_input",
                message="Enable public web search in chat settings to look up prices or specifications. You can still ask about your shared reports and ProofScan.",
            )
        evidence, unavailable = await web_evidence(plan, trace)
        if unavailable:
            return ChatResponse(
                status="unavailable",
                message="Public search is temporarily unavailable. I can still help compare your shared reports or explain what to verify before buying.",
            )
        checked = now().isoformat()
        country = MARKETS[plan.market][0]
        if plan.intent == "market":
            summary = f"Here are public listings in {country}. Prices shown come from indexed listing text. Open each listing to confirm the current price, storage variant, condition, and availability."
        else:
            summary = f"Here are published device details for {country}. Open the sources to confirm the exact configuration."

    verified = await review(evidence, plan, data, trace)
    if not verified:
        return ChatResponse(
            status="needs_input",
            message="I couldn’t verify a matching source for this question. Try a more specific device model or ask about the readings available in your reports.",
        )
    catalog_ids = {item.catalog_id for item in verified if item.catalog_id is not None}
    if catalog_ids and not await still_owned(catalog_ids):
        return ChatResponse(
            status="needs_input",
            message="The available reports changed during this comparison. Ask again for the latest evidence.",
        )
    return ChatResponse(
        status="answer",
        message="\n\n".join(item.sentence for item in verified) if plan.intent == "help" else summary,
        sources=[item.source for item in verified],
        checked_at=checked,
    )
