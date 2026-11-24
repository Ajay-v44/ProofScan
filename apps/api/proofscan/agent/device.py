from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import select, update

from ..auth import DB
from ..db import Guest, Scan, Verification, now
from ..domain import Status
from ..schemas import Input
from ..verification import GuestSession
from .middleware import MAX_MODEL_CALLS
from .model import decide
from .models import AgentExecution
from .schemas import DeviceAdvance, DevicePlan, DeviceStart, DeviceTool, MobilePlatform, ToolStatus
from .telemetry import AgentTrace, Event
from .usage import record_usage

router = APIRouter(prefix="/guest/{verification_id}/agent", tags=["guided device scan"])
PLAN_TTL = timedelta(minutes=20)


class Observation(Input):
    tool: DeviceTool
    outcome: ToolStatus


class DeviceState(Input):
    platform: MobilePlatform
    observations: list[Observation] = Field(default_factory=list, max_length=3)
    next_tool: DeviceTool | None = None
    model_attempts: int = Field(default=0, ge=0, le=MAX_MODEL_CALLS)


class ToolChoice(Input):
    tool: DeviceTool


def candidates(state: DeviceState) -> list[DeviceTool]:
    seen = {item.tool: item.outcome for item in state.observations}
    available: list[DeviceTool] = []
    if "model_name" not in seen:
        available.append("model_name")
    if seen.get("model_name") in {"unavailable", "error"} and "model_identifier" not in seen:
        available.append("model_identifier")
    if "memory_total" not in seen:
        available.append("memory_total")
    return available


def plan_view(run: AgentExecution) -> DevicePlan:
    return DevicePlan.model_validate(
        {
            "id": run.id,
            "revision": run.revision,
            "status": run.status,
            "next_tool": DeviceState.model_validate(run.state).next_tool,
        }
    )


async def active_scan(current: GuestSession, db: DB) -> Scan:
    verification, guest = current
    if verification.status != Status.SCANNING:
        raise HTTPException(409, "Start a scan after granting seller consent.")
    scan = await db.scalar(select(Scan).where(Scan.guest_id == guest.id))
    if scan is None or scan.platform not in {"android", "ios"}:
        raise HTTPException(409, "Start a supported mobile device scan.")
    return scan


@router.post("/plan", response_model=DevicePlan)
async def create_plan(data: DeviceStart, current: GuestSession, db: DB) -> DevicePlan:
    verification, _ = current
    scan = await active_scan(current, db)
    if scan.platform != data.platform:
        raise HTTPException(409, "The scanner platform changed. Open a new scan ticket.")
    run = await db.scalar(
        select(AgentExecution).where(AgentExecution.scan_id == scan.id).with_for_update()
    )
    attempts = 0
    if run is None:
        run = AgentExecution(scan_id=scan.id, owner_id=verification.owner_id, kind="device", revision=0)
        db.add(run)
    elif run.status == "planning" and run.expires_at > now():
        raise HTTPException(409, "The previous step is still processing. Try again shortly.")
    else:
        run.revision += 1
        attempts = DeviceState.model_validate(run.state).model_attempts
    run.state = DeviceState(platform=data.platform, model_attempts=attempts).model_dump()
    run.status = "awaiting_approval"
    run.expires_at = now() + PLAN_TTL
    await db.flush()
    return plan_view(run)


@router.post("/plan/{run_id}", response_model=DevicePlan)
async def advance_plan(run_id: UUID, data: DeviceAdvance, current: GuestSession, db: DB) -> DevicePlan:
    verification, guest = current
    scan = await active_scan(current, db)
    run = await db.scalar(
        select(AgentExecution)
        .where(AgentExecution.id == run_id, AgentExecution.scan_id == scan.id)
        .with_for_update()
    )
    if run is None or run.expires_at <= now():
        raise HTTPException(404, "This collection plan has expired. Start a new plan.")
    state = DeviceState.model_validate(run.state)
    if run.revision != data.revision or state.platform != scan.platform:
        raise HTTPException(409, "This collection plan has changed. Start a new plan.")
    trace = AgentTrace(run_id, "device")
    if data.action == "skip" and run.status in {"awaiting_approval", "collecting"}:
        run.status = "skipped"
        state.next_tool = None
        run.state = state.model_dump()
        run.revision += 1
        trace.publish("skipped")
        return plan_view(run)
    if data.action == "observe":
        if (
            run.status != "collecting"
            or data.tool != state.next_tool
            or data.tool is None
            or data.outcome is None
        ):
            raise HTTPException(409, "Report the outcome of the approved tool.")
        state.observations.append(Observation(tool=data.tool, outcome=data.outcome))
        trace.events.append(Event(data.tool, data.outcome, 0))
    elif run.status != "awaiting_approval":
        raise HTTPException(409, "This collection plan is already approved.")

    available = candidates(state)
    run.revision += 1
    state.next_tool = None
    if len(available) < 2 or state.model_attempts >= MAX_MODEL_CALLS:
        state.next_tool = next(iter(available), None)
        run.state = state.model_dump()
        run.status = "collecting" if available else "complete"
        trace.publish(run.status)
        await record_usage(db, "guided_device", accepted=True, trace=trace)
        return plan_view(run)

    # Reserve this revision before contacting the model. The short lease allows a safe restart after a crash.
    state.model_attempts += 1
    run.status = "planning"
    run.state = state.model_dump()
    run.expires_at = now() + timedelta(seconds=15)
    revision = run.revision
    await db.commit()

    choice = await decide(
        "Return JSON with a single tool field. Choose only an available read-only device tool. "
        "Prefer an approved fallback when a primary reader failed. Never ask for commands or identifiers.",
        {
            "platform": state.platform,
            "available": available,
            "response_schema": ToolChoice.model_json_schema(),
            "observations": [item.model_dump() for item in state.observations],
        },
        ToolChoice,
        trace,
        approved=True,
    )
    state.next_tool = choice.tool if choice is not None and choice.tool in available else available[0]
    trace.publish("collecting")
    eligible_guest = (
        select(Guest.id)
        .where(
            Guest.id == guest.id,
            Guest.revoked_at.is_(None),
            Guest.expires_at > now(),
        )
        .exists()
    )
    eligible_scan = select(Scan.id).where(Scan.id == scan.id, Scan.platform == state.platform).exists()
    eligible_verification = (
        select(Verification.id)
        .where(
            Verification.id == verification.id,
            Verification.status == Status.SCANNING,
        )
        .exists()
    )
    updated = await db.scalar(
        update(AgentExecution)
        .where(
            AgentExecution.id == run_id,
            AgentExecution.revision == revision,
            AgentExecution.status == "planning",
            eligible_guest,
            eligible_scan,
            eligible_verification,
        )
        .values(status="collecting", state=state.model_dump(), expires_at=now() + PLAN_TTL)
        .returning(AgentExecution.id)
    )
    if updated is None:
        raise HTTPException(409, "The collection session changed. Open your active seller link again.")
    await record_usage(db, "guided_device", accepted=True, trace=trace)
    return DevicePlan(id=run_id, revision=revision, status="collecting", next_tool=state.next_tool)
