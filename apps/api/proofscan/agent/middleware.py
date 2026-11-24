from time import perf_counter

from .telemetry import AgentTrace

MAX_MODEL_CALLS = 3
MAX_MODEL_CALL_SECONDS = 10.0
MODEL_WINDOW_SECONDS = 24.0


def model_timeout(trace: AgentTrace, *, approved: bool) -> float:
    """Enforce approval and inference limits at the provider boundary."""
    if not approved or sum(event.model is not None for event in trace.events) >= MAX_MODEL_CALLS:
        return 0.0
    return max(0.0, min(MAX_MODEL_CALL_SECONDS, MODEL_WINDOW_SECONDS - (perf_counter() - trace.started)))
