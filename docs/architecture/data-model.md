# Data model

All row IDs use UUIDs. Timestamps use PostgreSQL timezone-aware types. Foreign-key columns specify ownership and scope.

| Table | Purpose |
| --- | --- |
| `users` | Local credentials or mirrored Supabase subject |
| `verification_requests` | Buyer, listing label, workflow state and expiry |
| `listing_claims` | Optional advertised RAM, largest drive and minimum battery health |
| `guest_sessions` | Scoped seller credential digest, expiry and revocation |
| `seller_consents` | Seller acceptance of a specific policy version |
| `scan_sessions` | Seller session and selected platform |
| `scan_challenges` | Challenge digest, scan binding, issued time, expiry and consumption |
| `hardware_snapshots` | Validated platform-specific hardware readings |
| `functional_test_results` | Seller-observed or explicitly simulated display, keyboard and speaker results |
| `reports` | Immutable captured report payload |
| `report_signatures` | Digest, key ID and signature created at sharing |
| `pricing_estimates` | Signed report pricing range and comparable source metadata |
| `report_invalidations` | One-way validity decision attached to a signed report |
| `external_scan_sessions` | Exterior scan within a hardware scan |
| `evidence_items` | Angle, digest, quality metrics, capped JPEG and retention deadline |
| `agent_runs` and `agent_steps` | Deterministic inspection runs and their structured results |
| `model_calls` | Per-account model request outcome and token counts |
| `assets` and `handoffs` | Owned asset and its handoff workflow |
| `handoff_checkpoints` | Baseline and return readings, photos, and owner-recorded condition |
| `handoff_acceptances` | Expiring receiver link digest and acknowledgment time |
| `comparison_results` and `comparison_invalidations` | Immutable signed comparisons and validity decisions |
| `notifications` | Buyer-visible verification events |
| `admin_audit_logs` | Actor, action, target and reason for operator actions |

The listing and notification indexes serve owner-scoped history. The expiry index supports the scheduled sweep. Unique constraints prevent multiple consent or snapshot rows in the same verification. API-managed tables enable row-level security and revoke access from Supabase's browser roles.
