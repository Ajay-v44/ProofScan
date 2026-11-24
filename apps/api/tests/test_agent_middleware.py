from contextlib import contextmanager
from uuid import uuid4

from proofscan.agent import middleware, telemetry


def test_model_middleware_enforces_approval_time_and_step_budget(monkeypatch):
    trace = telemetry.AgentTrace(uuid4(), "probe")
    assert middleware.model_timeout(trace, approved=False) == 0
    monkeypatch.setattr(middleware, "perf_counter", lambda: trace.started + 21)
    assert middleware.model_timeout(trace, approved=True) == 3
    trace.events.extend(telemetry.Event("decide", "valid", 10, "model") for _ in range(3))
    assert middleware.model_timeout(trace, approved=True) == 0


def test_langfuse_payload_has_operational_metadata_only(monkeypatch):
    observations = []

    class Client:
        def create_trace_id(self, **kwargs):
            return "fixture-trace"

        @contextmanager
        def start_as_current_observation(self, **kwargs):
            observations.append(kwargs)
            yield None

    monkeypatch.setattr(telemetry, "langfuse_client", Client)
    trace = telemetry.AgentTrace(
        uuid4(),
        "recommendation",
        [
            telemetry.Event("decide", "valid", 10, "configured-model", 32, 8),
            telemetry.Event("search_catalog", "ok", 7),
        ],
    )
    trace.publish("answer")
    assert len(observations) == 3
    assert observations[1]["usage_details"] == {"input": 32, "output": 8}
    assert observations[2]["metadata"] == {"outcome": "ok", "duration_ms": 7}
    assert all("input" not in item and "output" not in item for item in observations)
