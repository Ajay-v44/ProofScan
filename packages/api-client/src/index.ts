export type Claims = { memory_gib?: number | null; storage_gb?: number | null; battery_percent?: number | null };
export type Verification = { id: string; label: string; status: string; created_at: string; expires_at: string; require_exterior?: boolean; is_pickup?: boolean };
export type CaptureLink = { url: string; expires_at: string };
export type CaptureProgress = { views: Angle[] };
export type Platform = "windows" | "macos" | "android" | "ios" | "simulator";
export type Angle = "front" | "back" | "left" | "right";
export type Photo = { id: string; angle: Angle; digest: string; width: number; height: number };
export type VisualFinding = { angle: Angle; status: "unavailable" | "retake" | "reused" | "review" | "no_clear_change"; detail: string };
export type FunctionalCheck = { test: "display" | "keyboard" | "speakers"; result: "PASS" | "ISSUE" };
export type Hardware = {
  manufacturer?: string | null;
  model?: string | null;
  cpu: string[];
  gpu: string[];
  memory_gib?: number | null;
  drives: { model?: string | null; capacity_gb: number }[];
  battery_health_percent?: number | null;
};
export type Report = {
  schema_version: 1 | 2 | 3;
  report_id: string;
  verification_id: string;
  captured_at: string;
  label: string;
  platform: Platform;
  assurance: "SIMULATED" | "COLLECTOR_REPORTED";
  hardware: Hardware;
  findings: { metric: string; claimed: number; observed: number | null; status: "MATCH" | "MISMATCH" | "UNAVAILABLE" }[];
  identity_confidence: "UNAVAILABLE";
  pricing: "UNAVAILABLE" | "AVAILABLE";
  price_estimate?: { currency: string; low: number; high: number; source: "LOCAL_COMPARABLES" | "SIMULATED"; sample_size: number } | null;
  visual_evidence?: Photo[];
  inspection_requests?: { test: "request_external_view" | "request_battery_reading"; angle?: Angle | null }[];
  functional?: (FunctionalCheck & { source: "SELLER_OBSERVATION" | "SIMULATED" })[];
  pickup?: { baseline_report_id: string; baseline_verification_id: string; baseline_captured_at: string;
    changed_hardware: string[]; compared_hardware: string[]; visuals: VisualFinding[] } | null;
};
export type SignedReport = { payload: Report; digest: string; signature: string; key_id: string; valid: boolean; baseline_valid?: boolean | null };
export type VerificationResult = {
  report_id: string; valid: boolean; invalidated: boolean; digest: string; signature: string; key_id: string; public_key: string | null;
};
export type GuestView = {
  verification: Verification;
  claims: Claims;
  simulator_enabled: boolean;
  preview: Report | null;
  report_id: string | null;
  photos: Photo[];
};
export type ScanTicket = { scan_id: string; challenge: string; issued_at: string; expires_at: string };
export type Notification = { id: string; verification_id: string | null; handoff_id: string | null; event: string; created_at: string };
export type HandoffMode = "windows" | "visual" | "simulator";
export type Handoff = { id: string; asset_id: string; label: string; mode: HandoffMode; status: string;
  receiver_accepted: boolean; report_id: string | null; photos: ("baseline" | "return")[];
  photo_views: Record<string, Angle[]>; next_view: Angle | null; capture_feedback: VisualFinding | null };
type Checkpoint = { recorded_at: string; note: string | null; photo_digest: string | null };
export type HandoffReport = { digest: string; signature: string; key_id: string; valid: boolean; payload: {
  report_id: string; label: string; mode: HandoffMode; baseline: Checkpoint; return: Checkpoint;
  differences: { metric: string; before: string | number | null; after: string | number | null; status: string }[];
  visual_findings?: VisualFinding[];
} };

export type CatalogCategory = "phone" | "tablet" | "laptop" | "other";
export type CatalogItem = {
  id: string; category: CatalogCategory; title: string; notes: string;
  price: number | null; currency: string | null; source_url: string | null;
  verification_id?: string | null; facts?: Record<string, number | boolean | null> | null;
};
export type AdvisorResult = {
  status: "answer" | "needs_input" | "no_evidence"; message: string; sources: CatalogItem[];
  tools: ("search_catalog" | "compare_candidates")[]; retrieval: "lexical" | "pgvector"; model_used: boolean;
};
export type BuyerChatPrice = {
  device: string;
  market: "IN" | "US" | "GB";
  currency: string;
  launch: { year: number; price_minor: number; storage_gb: number | null; href: string } | null;
  current: {
    low_minor: number; high_minor: number; median_minor: number; storage_gb: number;
    condition: "used" | "refurbished" | "new"; merchant_count: number;
  } | null;
};
export type BuyerChatAnswer = {
  status: "answer" | "needs_input" | "outside_domain" | "unavailable";
  message: string;
  sources: { kind: "help" | "report" | "listing" | "web"; title: string; href: string | null; detail: string | null }[];
  checked_at: string | null;
  pricing?: BuyerChatPrice[];
};
export type DeviceTool = "model_name" | "model_identifier" | "memory_total";
export type ToolOutcome = "ok" | "unavailable" | "error";
export type DevicePlan = {
  id: string; revision: number; status: "awaiting_approval" | "collecting" | "complete" | "skipped";
  next_tool: DeviceTool | null;
};

export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly requestId?: string) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiResponse = Pick<Response, "ok" | "status" | "json"> & Partial<Pick<Response, "headers">>;

type GuestTransport = {
  origin: string;
  guestToken: string;
  fetcher?: (url: string, init: RequestInit) => Promise<ApiResponse>;
};

export async function api<T>(path: string, data?: unknown, transport?: GuestTransport): Promise<T> {
  return request<T>(path, data === undefined ? "GET" : "POST", data, transport);
}

export function apiDelete(path: string): Promise<void> {
  return request(path, "DELETE");
}

async function request<T>(path: string, method: "GET" | "POST" | "DELETE", data?: unknown, transport?: GuestTransport): Promise<T> {
  const body = data === undefined ? undefined : JSON.stringify(data);
  let response: ApiResponse;
  try {
    const fetcher = transport?.fetcher ?? fetch;
    response = await fetcher((transport?.origin ?? "") + "/api/v1" + path, {
      method,
      cache: "no-store",
      credentials: transport ? "omit" : "same-origin",
      // Guest credentials must stay on the configured API origin.
      redirect: transport ? "error" : "follow",
      signal: AbortSignal.timeout(30_000),
      headers: {
        ...(data === undefined ? {} : { "Content-Type": "application/json" }),
        ...(transport ? { "X-Guest-Token": transport.guestToken } : {}),
      },
      body,
    });
  } catch {
    throw new ApiError("Could not reach ProofScan. Try again.", 0);
  }
  if (response.ok && response.status === 204) return undefined as T;

  const requestId = response.headers?.get("X-Request-ID") ?? undefined;
  const payload: unknown = await response.json().catch(() => undefined);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : undefined;
    const message = typeof detail === "string" && detail.trim()
      ? detail
      : "ProofScan could not complete that request.";
    throw new ApiError(message, response.status, requestId);
  }
  if (payload === undefined) throw new ApiError("ProofScan returned an unreadable response.", response.status, requestId);
  return payload as T;
}
