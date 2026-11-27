from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Positive = Annotated[int, Field(strict=True, gt=0, le=10_000_000)]
Percent = Annotated[int, Field(strict=True, ge=0, le=100)]
Ticket = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{43}$")]
Platform = Literal["windows", "macos", "android", "ios", "simulator"]
Angle = Literal["front", "back", "left", "right"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    ),
]


class Credentials(Input):
    email: Email
    password: Annotated[str, StringConstraints(min_length=12, max_length=128)]


class AccessToken(BaseModel):
    access_token: str


class Claims(Input):
    memory_gib: Positive | None = None
    storage_gb: Positive | None = None
    battery_percent: Percent | None = None


class CreateVerification(Input):
    label: Label
    claims: Claims = Field(default_factory=Claims)


class VerificationView(BaseModel):
    id: UUID
    label: str
    status: str
    created_at: datetime
    expires_at: datetime
    require_exterior: bool = False
    is_pickup: bool = False


class CreatedVerification(VerificationView):
    guest_url: str


class ConsentIn(Input):
    policy_version: Literal["2026-11-23"]
    accepted: Literal[True]


class StartScan(Input):
    platform: Platform


class ScanTicket(BaseModel):
    scan_id: UUID
    challenge: str
    issued_at: datetime
    expires_at: datetime


class CaptureLinkView(BaseModel):
    url: str
    expires_at: datetime


class CaptureProgress(BaseModel):
    views: list[Angle]


class Drive(Input):
    model: Label | None = None
    capacity_gb: Positive


class Hardware(Input):
    manufacturer: Label | None = None
    model: Label | None = None
    cpu: list[Label] = Field(default_factory=list, max_length=16)
    gpu: list[Label] = Field(default_factory=list, max_length=16)
    memory_gib: Positive | None = None
    drives: list[Drive] = Field(default_factory=list, max_length=32)
    battery_health_percent: Percent | None = None


class FunctionalCheck(Input):
    test: Literal["display", "keyboard", "speakers"]
    result: Literal["PASS", "ISSUE"]


class FunctionalReading(FunctionalCheck):
    source: Literal["SELLER_OBSERVATION", "SIMULATED"]


class Submission(Input):
    scan_id: UUID
    challenge: Ticket
    platform: Platform
    hardware: Hardware | None = None
    fixture: Literal["verified", "misrepresented"] | None = None
    functional: list[FunctionalCheck] = Field(default_factory=list, max_length=3)


class Decision(Input):
    decision: Literal["share", "decline"]


class AdminReason(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=280)]


class Finding(BaseModel):
    metric: Literal["Memory (GiB)", "Largest storage drive (GB)", "Battery health (%)"]
    claimed: int
    observed: int | None
    status: Literal["MATCH", "MISMATCH", "UNAVAILABLE"]


class TestRequest(BaseModel):
    test: Literal["request_external_view", "request_battery_reading"]
    angle: Angle | None = None


class PhotoView(BaseModel):
    id: UUID
    angle: Angle
    digest: str
    width: int
    height: int


class PriceView(BaseModel):
    currency: str
    low: int
    high: int
    source: Literal["LOCAL_COMPARABLES", "SIMULATED"]
    sample_size: int


class VisualFinding(BaseModel):
    angle: Angle
    status: Literal["unavailable", "retake", "reused", "review", "no_clear_change"]
    detail: str


class PickupComparison(BaseModel):
    baseline_report_id: UUID
    baseline_verification_id: UUID
    baseline_captured_at: datetime
    changed_hardware: list[str] = Field(default_factory=list)
    compared_hardware: list[str] = Field(default_factory=list)
    visuals: list[VisualFinding] = Field(default_factory=list)


class ReportPayload(BaseModel):
    schema_version: Literal[1, 2, 3] = 1
    report_id: UUID
    verification_id: UUID
    captured_at: datetime
    label: str
    platform: Platform
    assurance: Literal["SIMULATED", "COLLECTOR_REPORTED"]
    hardware: Hardware
    findings: list[Finding]
    identity_confidence: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    pricing: Literal["UNAVAILABLE", "AVAILABLE"] = "UNAVAILABLE"
    visual_evidence: list[PhotoView] = Field(default_factory=list)
    inspection_requests: list[TestRequest] = Field(default_factory=list)
    functional: list[FunctionalReading] = Field(default_factory=list)
    price_estimate: PriceView | None = None
    pickup: PickupComparison | None = None


class SignedReport(BaseModel):
    payload: ReportPayload
    digest: str
    signature: str
    key_id: str
    valid: bool
    baseline_valid: bool | None = None


class VerificationResult(BaseModel):
    report_id: UUID
    valid: bool
    invalidated: bool
    digest: str
    signature: str
    key_id: str
    public_key: str | None


class NotificationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    verification_id: UUID | None
    handoff_id: UUID | None
    event: str
    created_at: datetime


class GuestExchange(Input):
    token: Ticket


class GuestView(BaseModel):
    verification: VerificationView
    claims: Claims
    simulator_enabled: bool
    preview: ReportPayload | None = None
    report_id: UUID | None = None
    photos: list[PhotoView] = Field(default_factory=list)
