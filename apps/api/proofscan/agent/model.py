import asyncio
import json
from collections.abc import Mapping
from time import perf_counter

import httpx
from pydantic import BaseModel

from ..config import settings
from ..providers import model_controls, token_count
from .middleware import model_timeout
from .telemetry import AgentTrace, Event

DECISION_TOOL = "submit_decision"


def output_options(shape: type[BaseModel], *, use_tool: bool) -> dict[str, object]:
    if not use_tool:
        return {"response_format": {"type": "json_object"}}
    return {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": DECISION_TOOL,
                    "description": "Submit exactly one next action from the allowed values.",
                    "parameters": shape.model_json_schema(),
                },
            }
        ],
        "tool_choice": "required",
    }


def decision_arguments(message: dict, *, use_tool: bool) -> str:
    if not use_tool:
        return message["content"]
    calls = message["tool_calls"]
    if len(calls) != 1 or calls[0]["function"]["name"] != DECISION_TOOL:
        raise ValueError("Expected one decision call")
    return calls[0]["function"]["arguments"]


async def decide[T: BaseModel](
    prompt: str,
    facts: Mapping[str, object],
    response_type: type[T],
    trace: AgentTrace,
    *,
    approved: bool,
    model: str | None = None,
) -> T | None:
    config = settings()
    timeout = model_timeout(trace, approved=approved)
    if not config.kimi_api_key or not timeout:
        return None
    model_id = model or config.agent_model
    use_tool = model_id.startswith("kimi-k3")
    started = perf_counter()
    usage: dict = {}
    outcome = "unavailable"
    try:
        async with (
            asyncio.timeout(timeout),
            httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client,
        ):
            result = await client.post(
                config.kimi_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + config.kimi_api_key.get_secret_value()},
                json={
                    "model": model_id,
                    "max_tokens": 700 if use_tool else 260,
                    "messages": [
                        {
                            "role": "system",
                            "content": prompt
                            + (" Call submit_decision once with the result." if use_tool else ""),
                        },
                        {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
                    ],
                    **model_controls(model_id),
                    **output_options(response_type, use_tool=use_tool),
                },
            )
            result.raise_for_status()
            payload = result.json()
            if isinstance(payload.get("usage"), dict):
                usage = payload["usage"]
            message = payload["choices"][0]["message"]
            decision = response_type.model_validate_json(decision_arguments(message, use_tool=use_tool))
            outcome = "valid"
            return decision
    except (TimeoutError, httpx.HTTPError):
        return None
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        outcome = "invalid"
        return None
    finally:
        trace.events.append(
            Event(
                "decide",
                outcome,
                round((perf_counter() - started) * 1000),
                model_id,
                token_count(usage.get("prompt_tokens")),
                token_count(usage.get("completion_tokens")),
            )
        )
