from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ..schemas import Input

Category = Literal["phone", "tablet", "laptop", "other"]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Amount = Annotated[int, Field(ge=1, le=100_000_000)]


class CatalogInput(Input):
    category: Category
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=3000)]
    price: Amount | None = None
    currency: Currency | None = None
    source_url: Annotated[str, StringConstraints(max_length=600)] | None = None

    @field_validator("source_url")
    @classmethod
    def public_source(cls, value: str | None) -> str | None:
        if value is not None:
            url = urlsplit(value)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username is not None
                or url.query
                or url.fragment
                or any(character.isspace() or character == "\\" for character in value)
            ):
                raise ValueError("Use a public HTTPS source URL without query parameters or fragments")
        return value

    @model_validator(mode="after")
    def priced(self) -> "CatalogInput":
        if (self.price is None) != (self.currency is None):
            raise ValueError("Provide both price and currency when recording a price")
        return self


class CatalogView(CatalogInput):
    id: UUID
    verification_id: UUID | None = None
    facts: dict[str, int | bool | None] | None = None


class Question(Input):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=600)]
    category: Category | None = "phone"
    previous_question: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] | None
    ) = None
    budget: Amount | None = None
    currency: Currency | None = None
    allow_model: bool = False
    reports_only: bool = False

    @model_validator(mode="after")
    def budget_needs_currency(self) -> "Question":
        if (self.budget is None) != (self.currency is None):
            raise ValueError("Provide both budget and currency when applying a price limit")
        return self


RetrievalMode = Literal["lexical", "pgvector"]


class Recommendation(BaseModel):
    status: Literal["answer", "needs_input", "no_evidence"]
    message: str
    sources: list[CatalogView] = Field(default_factory=list)
    tools: list[Literal["search_catalog", "compare_candidates"]] = Field(default_factory=list)
    retrieval: RetrievalMode
    model_used: bool


ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Market = Literal["IN", "US", "GB"]
QuoteCondition = Literal["used", "refurbished", "new"]


class ChatRequest(Input):
    message: ChatText
    history: list[ChatText] = Field(default_factory=list, max_length=4)
    market: Market = "IN"
    include_listings: bool = False
    allow_web: bool = True
    allow_model: bool = False


class ChatSource(BaseModel):
    kind: Literal["help", "report", "listing", "web"]
    title: str
    href: str | None = None
    detail: str | None = None


class LaunchPrice(BaseModel):
    year: int
    price_minor: int
    storage_gb: int | None = None
    href: str


class MarketRange(BaseModel):
    low_minor: int
    high_minor: int
    median_minor: int
    storage_gb: int
    condition: QuoteCondition
    merchant_count: int


class PriceAssessment(BaseModel):
    device: str
    market: Market
    currency: str
    launch: LaunchPrice | None = None
    current: MarketRange | None = None


class ChatResponse(BaseModel):
    status: Literal["answer", "needs_input", "outside_domain", "unavailable"]
    message: str
    sources: list[ChatSource] = Field(default_factory=list)
    checked_at: str | None = None
    pricing: list[PriceAssessment] = Field(default_factory=list)


DeviceTool = Literal["model_name", "model_identifier", "memory_total"]
ToolStatus = Literal["ok", "unavailable", "error"]
MobilePlatform = Literal["android", "ios"]


class DeviceStart(Input):
    platform: MobilePlatform


class DeviceAdvance(Input):
    revision: Annotated[int, Field(ge=0, le=2_147_483_647)]
    action: Literal["approve", "skip", "observe"]
    tool: DeviceTool | None = None
    outcome: ToolStatus | None = None

    @model_validator(mode="after")
    def observation_must_identify_tool(self) -> "DeviceAdvance":
        if self.action == "observe" and (self.tool is None or self.outcome is None):
            raise ValueError("Provide a tool and outcome when reporting a reading")
        if self.action != "observe" and (self.tool is not None or self.outcome is not None):
            raise ValueError("Only observations can include a tool or outcome")
        return self


class DevicePlan(BaseModel):
    id: UUID
    revision: int
    status: Literal["awaiting_approval", "collecting", "complete", "skipped"]
    next_tool: DeviceTool | None = None
