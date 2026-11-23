from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph

from .capabilities import CAPABILITIES
from .schemas import Angle, Claims, Finding, Hardware, Platform, TestRequest

ANGLES: tuple[Angle, ...] = ("front", "back", "left", "right")


class Inspection(TypedDict, total=False):
    platform: Platform
    hardware: Hardware
    claims: Claims
    angles: list[Angle]
    findings: list[Finding]
    requests: list[TestRequest]


def validate(state: Inspection) -> Inspection:
    if state["platform"] not in CAPABILITIES:
        raise ValueError("Unsupported scan platform")
    return {}


def analyze(state: Inspection) -> Inspection:
    hardware = state["hardware"]
    claims = state["claims"]
    metrics = [
        ("Memory (GiB)", claims.memory_gib, hardware.memory_gib),
        (
            "Largest storage drive (GB)",
            claims.storage_gb,
            max(
                (drive.capacity_gb for drive in hardware.drives),
                default=None,
            ),
        ),
        ("Battery health (%)", claims.battery_percent, hardware.battery_health_percent),
    ]
    findings = []
    for metric, claimed, observed in metrics:
        if claimed is None:
            continue
        if observed is None:
            match = "UNAVAILABLE"
        elif metric == "Battery health (%)":
            match = "MATCH" if observed >= claimed else "MISMATCH"
        else:
            match = "MATCH" if observed == claimed else "MISMATCH"
        findings.append(
            Finding.model_validate(
                {
                    "metric": metric,
                    "claimed": claimed,
                    "observed": observed,
                    "status": match,
                }
            )
        )
    return {"findings": findings}


def plan_tests(state: Inspection) -> Inspection:
    capability = CAPABILITIES[state["platform"]]
    if not capability.external_visual_scan:
        return {"requests": []}
    angles = state["angles"]
    requests = [
        TestRequest(test="request_external_view", angle=angle) for angle in ANGLES if angle not in angles
    ]
    if (
        capability.battery_health
        and state["claims"].battery_percent is not None
        and state["hardware"].battery_health_percent is None
    ):
        requests.insert(0, TestRequest(test="request_battery_reading"))
    return {"requests": requests[:3]}


builder = StateGraph(Inspection)
builder.add_node("validate", validate)
builder.add_node("analyze_claims", analyze)
builder.add_node("determine_missing_evidence", plan_tests)
builder.add_edge(START, "validate")
builder.add_edge("validate", "analyze_claims")
builder.add_edge("analyze_claims", "determine_missing_evidence")
builder.add_edge("determine_missing_evidence", END)
graph = builder.compile()


def inspect(platform: Platform, hardware: Hardware, claims: Claims, angles: list[Angle]) -> Inspection:
    return cast(
        Inspection,
        graph.invoke(
            {"platform": platform, "hardware": hardware, "claims": claims, "angles": angles},
            config={"recursion_limit": 5},
        ),
    )
