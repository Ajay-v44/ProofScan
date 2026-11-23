# CODEX MASTER PROMPT — BUILD PROOFSCAN

You are the primary engineering agent responsible for designing, implementing, testing, securing, documenting and finishing **ProofScan**.

Treat this as a real product build, not a toy prototype.

The product name is:

# ProofScan

Tagline:

> **Verify what it is. Verify what changed.**

Your responsibility is to deliver a complete, polished, runnable product from the existing repository.

Do not stop after scaffolding.

Do not produce only architecture diagrams.

Do not build placeholder screens and call the product complete.

Do not mark a feature complete unless it works and is tested.

Take the implementation through frontend, backend, desktop, mobile, agent workflows, database, security, reports, admin tooling, documentation and tests.

---

# IMPORTANT WORKING RULES

## 1. Credentials

Whenever progress reaches a point requiring a credential, API key, external service account, signing identity, certificate, Apple account, Google account, Supabase project, Moonshot/Kimi API key or any information that only I can provide:

**STOP at that specific integration point and clearly ask me for exactly what you need.**

Examples:

```text
I now need:
KIMI_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Explain:

- where I obtain it;
- why ProofScan needs it;
- minimum permissions required.

Never invent credentials.

Never insert fake production credentials.

Never commit secrets.

Continue implementing independent parts that do not require the credential whenever possible.

---

# 2. Environment

Create:

```text
.env.example
```

with every required variable.

Actual `.env` must be gitignored.

Validate environment configuration at application startup and produce actionable error messages.

---

# 3. Docker

Create production-quality Dockerfiles for:

- FastAPI API;
- Celery worker;
- Next.js web/admin.

Create:

```text
docker-compose.yml
```

for local development.

Include:

- PostgreSQL;
- Redis;
- API;
- worker;
- web.

ProofScan production data architecture uses Supabase, but local PostgreSQL should allow development/testing without requiring cloud access.

DO NOT automatically build Docker images.

DO NOT push images.

DO NOT deploy images unless explicitly instructed.

Provide commands in documentation.

---

# 4. Do not overengineer V1

Use a modular monolith.

Do not introduce:

- Kubernetes;
- Kafka;
- unnecessary microservices;
- separate graph databases;
- separate vector databases;
- blockchain.

Only introduce infrastructure that directly improves ProofScan.

---

# 5. Product requirements

Read and implement the complete `README.md`.

The README is the product source of truth.

ProofScan has two primary workflows.

## A. Verify a Purchase

Buyer creates fresh verification.

Seller receives guest link.

Seller does not need account.

Seller consents.

Seller runs internal + functional + external scan.

Inspection Agent can request extra tests.

Seller previews report.

Seller explicitly shares/declines.

Buyer receives cryptographically signed report.

---

## B. Protect a Handoff

User scans asset before giving it away.

Optional receiver acceptance.

User rescans asset on return.

ProofScan compares:

- identity;
- internal state where supported;
- functional state;
- visual condition.

Generate signed difference report.

---

# 6. Platforms

Implement architecture for:

```text
Android
iOS
Windows
macOS
Web
```

Platform capability depth is intentionally different.

Do not fake feature parity.

---

# 7. Technology Stack

Use exactly these technologies unless there is a serious technical blocker.

## Backend

```text
Python
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
asyncpg
```

## Agent orchestration

```text
LangGraph
```

## AI provider

Primary:

```text
Kimi / Moonshot API
```

Build model-provider abstraction.

Do not hardwire Kimi throughout business logic.

## Database/platform

```text
Supabase PostgreSQL
Supabase Auth
Supabase Storage
```

## Queue/cache

```text
Redis
Celery
```

## Computer vision

```text
OpenCV
```

## Mobile

```text
React Native
Expo
TypeScript
Expo Router
TanStack Query
Zustand
```

Use Expo development builds/prebuild when native modules are required.

## Desktop

```text
Tauri 2
React
TypeScript
Rust
```

Desktop supports:

```text
Windows
macOS
```

## Web/Admin

```text
Next.js
TypeScript
Tailwind
shadcn/ui
TanStack Query
```

## Observability

```text
Sentry
OpenTelemetry
Langfuse
```

---

# 8. Repository architecture

Use a monorepo.

Target:

```text
proofscan/
│
├── README.md
├── CODEX_MASTER_PROMPT.md
├── .env.example
├── docker-compose.yml
│
├── apps/
│   ├── api/
│   ├── worker/
│   ├── web/
│   ├── mobile/
│   └── desktop/
│
├── packages/
│   ├── api-client/
│   ├── shared-types/
│   ├── report-schema/
│   └── design-tokens/
│
├── infrastructure/
│   ├── docker/
│   ├── github/
│   └── scripts/
│
└── docs/
    ├── architecture/
    ├── security/
    ├── api/
    ├── ux/
    └── decisions/
```

Use workspaces appropriate for JS/TS portions.

Generate TypeScript API types/client from FastAPI OpenAPI where practical.

---

# 9. Database

Implement proper Alembic migrations.

Use UUID primary keys.

Use UTC timestamps.

Use strong foreign keys.

Use PostgreSQL indexes.

Do not create one enormous JSON document for everything.

Normalize queryable business concepts.

Use JSONB only for flexible platform-specific telemetry.

Implement the database model described in README including at minimum:

```text
users
assets
verification_requests
listing_claims
guest_sessions
scan_sessions
device_identities
hardware_snapshots
hardware_components
functional_test_results
external_scan_sessions
evidence_items
observations
agent_runs
agent_steps
seller_consents
reports
report_signatures
pricing_estimates
handoffs
handoff_checkpoints
handoff_acceptances
comparison_results
notifications
admin_audit_logs
```

Add indexes based on realistic access patterns.

Document all tables.

---

# 10. State machines

Do not scatter status checks randomly through controllers.

Implement explicit domain-state transitions.

Verification:

```text
DRAFT
→ LINK_CREATED
→ SELLER_OPENED
→ CONSENTED
→ SCANNING
→ REPORT_READY
→ SELLER_REVIEW
→ SHARED / DECLINED
→ COMPLETED
```

Also:

```text
FAILED
EXPIRED
CANCELLED
```

Handoff:

```text
DRAFT
→ BASELINE_SCANNING
→ BASELINE_CREATED
→ ACTIVE_HANDOFF
→ RETURN_SCANNING
→ COMPARING
→ REPORT_READY
→ CLOSED
```

Invalid transitions must fail.

Test them.

---

# 11. Guest seller architecture

Seller must not need an account.

Build guest-session mechanism using:

```text
opaque random token
+
server-side token hash
+
verification ID
+
allowed scope
+
expiry
```

Guest sessions must not grant access to unrelated ProofScan resources.

Example permission:

```text
verification:PV-84X921
actions:
scan
upload_evidence
preview_report
share_or_decline
```

Token must expire.

Token must be revocable.

Do not expose sensitive data through guest URLs.

---

# 12. Fresh verification challenge

Buyer verification must create a fresh cryptographic challenge.

Challenge must be bound to:

```text
verification_id
guest_session
scan
timestamp
platform
```

Prevent replay.

Do not accept scan evidence against an already-consumed challenge.

Implement tests for:

- expired challenge;
- reused challenge;
- wrong verification;
- wrong session.

---

# 13. Report signing

Implement canonical report JSON.

Hash:

```text
SHA-256
```

Sign with:

```text
Ed25519
```

Development private key can come from environment variable.

Never store it in mobile/desktop/web code.

Expose endpoint:

```text
GET /api/v1/reports/{id}/verify
```

Public verification page must validate:

```text
report hash
signature
invalidation state
```

Once signed, report data is immutable.

Admins can invalidate but cannot edit signed contents.

---

# 14. Device Identity

Implement separate models for:

```text
DeviceIdentity
DeviceState
```

Do not treat changing RAM/SSD as automatically meaning a different device.

Identity engine should return:

```text
confidence:
HIGH
MEDIUM
LOW
UNAVAILABLE
```

and evidence.

---

# 15. Desktop collectors

Create Rust interfaces.

Example conceptual trait:

```rust
trait HardwareCollector {
    fn capabilities(&self) -> Capabilities;
    fn identity(&self) -> DeviceIdentity;
    fn collect_snapshot(&self) -> HardwareSnapshot;
    fn run_test(&self, test: TestRequest) -> TestResult;
}
```

Implement platform-specific collectors.

---

# Windows

Use appropriate supported Windows APIs/WMI/CIM/native interfaces.

Collect as safely available:

```text
system information
CPU
GPU
RAM
RAM modules
storage
storage health
battery
display
network interfaces
camera
microphone
TPM/security state
```

Do not execute destructive benchmarks.

All performance tests must have timeout/resource limits.

---

# macOS

Implement native macOS collector using appropriate APIs.

Collect where supported:

```text
model
chip
unified memory
storage
battery
cycle count
display
camera
microphone
network capabilities
supported identity
```

Respect Apple Silicon limitations.

---

# 16. Mobile collectors

Use React Native modules.

Where standard Expo APIs are insufficient, create custom Kotlin/Swift modules.

Do not use restricted/private OS APIs that would make the application unsuitable for Play Store/App Store distribution.

---

# Android

Integrate:

```text
Play Integrity
```

when credentials are available.

Use only legitimate Android APIs.

---

# iOS

Integrate:

```text
App Attest
```

when credentials/signing are available.

Do not claim inaccessible hardware information.

---

# 17. Platform capability profiles

Create capability registry.

Example:

```json
{
  "platform": "windows",
  "battery_health": true,
  "storage_serial": true,
  "memory_module_identity": true,
  "external_visual_scan": true
}
```

The Inspection Agent must know what tests are possible.

UI must say:

```text
Not supported on this platform
```

rather than failing silently.

---

# 18. Inspection Agent

Use LangGraph.

Initial V1 should use one orchestrator rather than many superficial agents.

Graph:

```text
Initial Evidence
→ Validate
→ Analyze Claims
→ Identify Anomalies
→ Determine Missing Evidence
→ Request Test
→ Receive Result
→ Re-evaluate
→ External Scan
→ Produce Findings
```

Use maximum-loop limit.

Use structured outputs.

Never use model prose as authoritative measurements.

---

# Agent tools

Design explicit tools such as:

```text
get_device_capabilities
get_initial_snapshot
request_memory_rescan
request_storage_test
request_battery_test
request_cpu_test
request_gpu_test
request_display_test
request_camera_test
request_microphone_test
request_external_view
compare_listing_claims
compare_checkpoints
lookup_market_price
```

Tools must have strict Pydantic schemas.

---

# Kimi Integration

Implement model provider.

Credentials:

```text
KIMI_API_KEY
KIMI_BASE_URL
KIMI_MODEL
KIMI_VISION_MODEL
```

If the existing Kimi subscription does not include API access, stop and ask me for Moonshot API credentials.

Do not assume consumer Kimi subscription equals API credits.

---

# 19. AI cost controls

AI cost should be minimal.

Do not send routine telemetry through the model.

Use deterministic code for:

```text
RAM comparison
storage comparison
serial comparison
battery calculations
state machine
hashing
signatures
basic pricing rules
blur detection
image alignment
```

Use Kimi only for:

```text
claim understanding
adaptive test planning
ambiguous evidence
visual reasoning
human explanation
historical summary
```

Cache repeated model-safe outputs where appropriate.

Set token limits.

Track AI cost.

---

# 20. External visual scan

Build guided capture.

Use local computer vision before cloud AI.

Check:

```text
blur
brightness
coverage
frame quality
alignment
```

Upload selected evidence rather than entire high-resolution videos where possible.

For Handoff return scan, guide user toward matching prior viewpoints.

---

# 21. Storage

Use Supabase Storage.

Buckets:

```text
proofscan-evidence
proofscan-reports
```

Use private storage.

Serve through short-lived signed URLs.

Do not expose permanent public media URLs.

Implement configurable retention.

Example:

```text
raw media:
24h

processed evidence:
30 days

report:
long-term
```

Provide cleanup task.

---

# 22. Verify UX

Buyer should be able to create verification quickly.

Seller should experience:

```text
Open link
→ privacy
→ consent
→ scanner
→ tests
→ external scan
→ preview
→ share
```

No forced seller signup.

---

# 23. Handoff UX

Owner:

```text
Protect a Handoff
→ choose asset/category
→ baseline scan
→ optional receiver acceptance
→ active handoff
→ returned
→ return scan
→ comparison
```

Generic objects use visual-only verification.

Label limitations.

---

# 24. Pricing MVP

Build pricing as a replaceable service.

For V1:

```text
rule-based
+
optional external comparable-data adapter
```

Do not invent market values.

If reliable market data is unavailable:

```text
Pricing unavailable
```

is preferable to fake values.

Define:

```python
class PricingProvider:
    async def estimate(...):
        ...
```

Provide local/demo pricing fixture for hackathon testing.

---

# 25. Admin Dashboard

Implement:

```text
Overview
Verifications
Handoffs
Scan failures
Agent runs
Fraud signals
Reports
Platform health
Storage usage
Model usage
Audit logs
```

Provide search by:

```text
verification code
report ID
asset ID
user ID
```

---

# 26. Admin permissions

Admin accounts must be separate from ordinary user permissions.

Critical actions require audit.

Never allow admin UI to mutate signed report fields.

Allowed:

```text
invalidate report
revoke guest session
review failure
flag abuse
```

---

# 27. UI / Design

Do not create a generic Tailwind dashboard.

Research strong current product design references.

Review UX/design patterns from products such as:

```text
Canva
Linear
Stripe
Apple
Revolut
Back Market
Carfax
Cashify
modern diagnostics/security products
```

The goal is not to copy them.

Analyse:

- information hierarchy;
- typography;
- spacing;
- onboarding;
- trust UX;
- card design;
- scan progress;
- success/error states;
- report visualization;
- mobile interaction;
- dashboard density.

ProofScan visual language should communicate:

```text
TRUST
EVIDENCE
CLARITY
CONTROL
```

Avoid:

- neon AI aesthetic;
- excessive gradients;
- fake cyber-security imagery;
- dense engineering screens for consumers.

Use accessible contrast.

Make Android/iOS/desktop feel native enough while maintaining common branding.

---

# 28. Consumer UX language

Avoid technical jargon such as:

```text
TPM EK certificate
NVMe SMART attribute
cryptographic nonce
```

unless user opens technical details.

Translate into:

```text
Device identity verified
Storage health good
Fresh verification confirmed
```

Provide:

```text
Technical details
```

for advanced users.

---

# 29. Testing

You are responsible for testing the complete product.

Do not state that ProofScan works until critical tests pass.

---

## Backend tests

Use pytest.

Cover:

```text
auth
authorization
guest access
state machines
challenge expiry
replay protection
report hashing
report signing
signature verification
consent
handoff state
comparison logic
admin restrictions
storage metadata
```

---

## Agent tests

Create fixture dataset.

Examples:

### Fixture A

Claim:

```text
16GB RAM
1TB SSD
```

Actual:

```text
8GB
512GB
```

Expected:

```text
mismatch found
additional verification requested if necessary
```

### Fixture B

Unsupported iOS metric.

Agent must not request impossible test.

### Fixture C

Evidence incomplete.

Agent requests missing angle.

### Fixture D

Kimi unavailable.

Workflow must fail gracefully.

### Fixture E

Agent repeatedly requests same test.

Loop guard must stop it.

---

## Desktop tests

Unit test collectors.

Create test abstraction so CI does not depend entirely on one physical machine.

Support:

```text
real collectors
mock collectors
fixture collectors
```

Real-device testing must also be documented.

---

## Mobile tests

Test:

```text
deep links
guest session restoration
consent
camera flow
scan flow
seller preview
decline
share
handoff flow
```

---

## Web tests

Use Playwright.

Required E2E:

```text
Buyer creates verification
→ seller opens guest link
→ simulator scan runs
→ seller approves
→ buyer receives report
→ report signature verifies
```

Required Handoff E2E:

```text
baseline
→ active handoff
→ return
→ simulated changed component
→ comparison report
```

---

# 30. Simulator

Build a ProofScan simulator specifically for:

- automated tests;
- demo;
- development without having all physical devices.

It must clearly display:

```text
SIMULATED DATA
```

Never sign simulator reports as equivalent to hardware-backed real verification.

---

# 31. Demo fixtures

Implement at least:

## Verified Device

```text
16GB
1TB
90% battery
everything passes
```

## Misrepresented Device

Seller claims:

```text
16GB
1TB
excellent battery
```

Actual:

```text
8GB
512GB
69%
```

## Handoff Change

Before:

```text
Samsung 16GB RAM
```

After:

```text
Crucial 8GB RAM
```

Visual:

```text
new scratch
```

---

# 32. Notifications

Notify registered user when:

```text
seller opens
seller begins scan
seller shares
seller declines
verification expires
report ready
handoff return comparison ready
```

Use push where configured.

Provide in-app notifications regardless.

---

# 33. Observability

Instrument:

```text
FastAPI
Celery
LangGraph
Kimi calls
storage
frontend errors
desktop collector failures
```

Use correlation IDs.

Every verification must be traceable across:

```text
web/mobile
backend
worker
agent
desktop/mobile scanner
```

without storing sensitive personal data unnecessarily.

---

# 34. Privacy

Collect minimum required data.

Avoid storing PII when not needed.

Hash device identifiers when raw values are unnecessary.

Do not log:

```text
tokens
API keys
raw secrets
personal files
```

Add privacy documentation.

---

# 35. API Documentation

FastAPI OpenAPI must be clean.

Create documentation describing:

```text
authentication
guest sessions
verifications
scans
handoffs
reports
admin
errors
```

Generate/share TypeScript types where practical.

---

# 36. Documentation

Create:

```text
docs/architecture/overview.md
docs/architecture/data-model.md
docs/architecture/agent.md
docs/security/threat-model.md
docs/security/report-signing.md
docs/ux/flows.md
docs/api/integration.md
docs/development/setup.md
docs/deployment/README.md
```

Also create architecture diagrams using Mermaid.

---

# 37. Threat model

Explicitly document threats including:

```text
seller submitting old scan
replayed challenge
modified desktop client
modified mobile client
fake telemetry
stolen guest link
report tampering
admin abuse
storage URL leakage
model hallucination
model prompt injection through listing text
malicious uploaded image
DoS / excessive scans
```

Add mitigations where feasible.

Do not claim ProofScan is impossible to bypass.

Use trust/confidence levels.

---

# 38. CI

Configure GitHub Actions.

Run:

```text
Python lint/type checks/tests
TS lint/type checks/tests
Rust fmt/clippy/tests
Next.js tests/build validation
Playwright tests where feasible
```

Do not require unavailable secrets for ordinary PR tests.

Use mocks.

Separate secret-dependent integration jobs.

---

# 39. Coding quality

Use:

```text
clean modules
typed boundaries
domain services
repositories where justified
dependency injection where useful
structured logging
clear errors
idempotency
transactions
timeouts
retry policies
```

Do not create abstraction layers simply for ceremony.

---

# 40. Performance

Optimize:

```text
scan startup
hardware collection
image preprocessing
upload bandwidth
API response time
agent latency
```

Run independent collectors concurrently when safe.

Do not block FastAPI event loop with CPU-heavy image work.

Use Celery workers.

Compress media.

Use pagination.

Use database indexes.

---

# 41. Accessibility

All user-facing apps should have:

```text
clear labels
keyboard navigation where relevant
screen-reader-friendly controls
adequate contrast
large touch targets
error descriptions
```

---

# 42. One-month execution order

Implement in this order.

## Phase 1 — Foundation

```text
monorepo
backend
database
Supabase integration
Redis
auth
guest sessions
state machines
web shell
desktop shell
mobile shell
```

## Phase 2 — Hero Verify Flow

Make this work completely:

```text
buyer
→ link
→ seller
→ Windows scan
→ seller preview
→ share
→ signed report
→ buyer report
```

DO NOT move on until this works.

## Phase 3 — Agent + External Scan

Add:

```text
Kimi
LangGraph
adaptive testing
external capture
evidence analysis
```

## Phase 4 — Handoff

Add:

```text
asset
baseline
return
comparison
```

## Phase 5 — Android/macOS/iOS capability implementation

Implement realistic capabilities.

## Phase 6 — Admin + hardening

```text
admin
fraud signals
observability
retention
audit logs
```

## Phase 7 — Polish

```text
UX
animations
error states
loading states
empty states
docs
tests
performance
security review
```

---

# 43. Milestone requirement

The most important milestone is:

> A real Windows laptop must be able to receive a buyer-created verification challenge, run ProofScan, collect real supported hardware information, allow the seller to review it, share it, and generate a server-signed buyer report.

Treat this as the first non-negotiable end-to-end success criterion.

---

# 44. Completion criteria

Do not tell me ProofScan is complete until:

```text
critical product flows work
database migrations work
backend tests pass
frontend tests pass
desktop tests pass
agent tests pass
report signatures verify
guest flow works
replay tests pass
seller consent works
handoff comparison works
Dockerfiles exist
docker-compose exists
.env.example exists
documentation exists
admin dashboard works
error states are handled
```

Run final test suites.

Run linting.

Run type checks.

Run build validation.

Review logs for failures.

Fix issues before declaring completion.

---

# 45. Credential checkpoints

You should proactively ask me for credentials when required.

Likely requirements:

```text
Supabase project URL
Supabase anon key
Supabase service-role key
Kimi/Moonshot API key

Google Play Integrity configuration
Apple Developer configuration
Apple Team ID
Apple Bundle ID

Expo account/token if needed

Sentry credentials
Langfuse credentials
```

Do not block the entire project if optional credentials are unavailable.

Build adapters, mocks and documentation, then continue with independent modules.

---

# 46. Final deliverables

When work is complete, provide me with:

```text
1. Product summary
2. Architecture summary
3. Complete repository structure
4. Setup instructions
5. Required environment variables
6. How to run locally
7. How to run backend
8. How to run web/admin
9. How to run desktop
10. How to run mobile
11. Database migration commands
12. Test commands
13. Test results
14. Known platform limitations
15. Security assumptions
16. Credentials still required
17. Deployment guide
18. Demo guide
19. Hackathon presentation/demo flow
20. Future roadmap
```

Also clearly state:

```text
IMPLEMENTED
PARTIALLY IMPLEMENTED
BLOCKED BY CREDENTIALS
NOT IMPLEMENTED
```

for every major feature.

Never hide incomplete work.

---

# 47. Final instruction

Treat **ProofScan as your own product**.

Make sensible engineering decisions.

Prioritize:

```text
working product
correctness
security
performance
privacy
UX
testability
maintainability
```

over unnecessary architecture.

When something in this specification conflicts with a genuine platform restriction, do not fake the capability.

Document the restriction and design the best legitimate fallback.

Use Codex aggressively for implementation, testing, refactoring and verification.

The end result must feel like a polished product that could realistically be shown to:

- hackathon judges;
- a used-device buyer;
- a seller;
- a mobile/laptop reseller;
- an investor;
- an engineering interviewer.

Build the complete product.

Test it.

Verify it.

Only then report completion.
