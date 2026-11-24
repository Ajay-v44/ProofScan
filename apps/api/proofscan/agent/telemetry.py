import logging
from dataclasses import dataclass, field
from functools import lru_cache
from time import perf_counter
from uuid import UUID

from ..config import settings

log = logging.getLogger(__name__)


@dataclass
class Event:
    name: str
    outcome: str
    elapsed_ms: int
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class AgentTrace:
    run_id: UUID
    kind: str
    events: list[Event] = field(default_factory=list)
    started: float = field(default_factory=perf_counter, init=False)

    def publish(self, status: str) -> None:
        try:
            client = langfuse_client()
            if client is None:
                return
            # Observability is deliberately metadata-only. Never pass model prompts or tool data here.
            with client.start_as_current_observation(
                as_type="span",
                name="proofscan." + self.kind,
                trace_context={"trace_id": client.create_trace_id(seed=str(self.run_id))},
                metadata={"execution_id": str(self.run_id), "status": status},
            ):
                for event in self.events:
                    metadata = {"outcome": event.outcome, "duration_ms": event.elapsed_ms}
                    if event.model:
                        usage = {
                            name: value
                            for name, value in {
                                "input": event.input_tokens,
                                "output": event.output_tokens,
                            }.items()
                            if value is not None
                        }
                        with client.start_as_current_observation(
                            as_type="generation",
                            name=event.name,
                            model=event.model,
                            metadata=metadata,
                            usage_details=usage,
                        ):
                            pass
                    else:
                        with client.start_as_current_observation(
                            as_type="tool", name=event.name, metadata=metadata
                        ):
                            pass
        except Exception:
            log.warning("Agent telemetry export could not be queued")


@lru_cache(maxsize=1)
def langfuse_client():
    config = settings()
    if not config.langfuse_secret_key:
        return None
    from langfuse import Langfuse  # type: ignore[import-not-found]

    return Langfuse(
        public_key=config.langfuse_public_key,
        secret_key=config.langfuse_secret_key.get_secret_value(),
        base_url=config.langfuse_base_url,
        timeout=3,
    )


def flush_telemetry() -> None:
    if langfuse_client.cache_info().currsize == 0:
        return
    try:
        client = langfuse_client()
        if client is not None:
            client.flush()
    except Exception:
        log.warning("Agent telemetry could not be flushed")
