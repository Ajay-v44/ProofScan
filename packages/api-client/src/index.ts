export type Claims = { memory_gib?: number | null; storage_gb?: number | null; battery_percent?: number | null };
export type Verification = { id: string; label: string; status: string; created_at: string; expires_at: string };
export type Platform = "windows" | "macos" | "android" | "ios" | "simulator";
export type Angle = "front" | "back" | "left" | "right";
export type Photo = { id: string; angle: Angle; digest: string; width: number; height: number };
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
  schema_version: 1 | 2;
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
};
export type SignedReport = { payload: Report; digest: string; signature: string; key_id: string; valid: boolean };
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
  receiver_accepted: boolean; report_id: string | null; photos: ("baseline" | "return")[] };
type Checkpoint = { recorded_at: string; note: string | null; photo_digest: string | null };
export type HandoffReport = { digest: string; signature: string; key_id: string; valid: boolean; payload: {
  report_id: string; label: string; mode: HandoffMode; baseline: Checkpoint; return: Checkpoint;
  differences: { metric: string; before: string | number | null; after: string | number | null; status: string }[];
} };

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
  }
}

export async function api<T>(path: string, data?: unknown, transport?: { origin: string; guestToken: string }): Promise<T> {
  let response;
  try {
    response = await fetch((transport?.origin ?? "") + "/api/v1" + path, {
      method: data === undefined ? "GET" : "POST",
      cache: "no-store",
      credentials: transport ? "omit" : "same-origin",
      headers: {
        ...(data === undefined ? {} : { "Content-Type": "application/json" }),
        ...(transport ? { "X-Guest-Token": transport.guestToken } : {}),
      },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
  } catch {
    throw new ApiError("Could not reach ProofScan. Try again.", 0);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(error.detail ?? "ProofScan could not complete that request.", response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
