# Implementation status

## Implemented

- Local PostgreSQL migrations, local buyer authentication, scoped account-free seller links, consent, explicit sharing and decline, in-app request updates and transactional replay protection.
- Windows CIM collector and browser workflow for hardware readings, required front and back photos on new real purchase checks, and seller-observed display, keyboard and speaker checks.
- RFC 8785, SHA-256 and Ed25519 purchase and handoff reports. Public signature checks disclose cryptographic metadata. Operator invalidation leaves signed records append-only.
- LangGraph claim comparisons and bounded evidence suggestions. Private photo processing includes blur and brightness checks, local descriptors, matching-angle alignment and a retention task.
- Handoff and return flows use matching-angle photos, live browser camera guidance and signed visual findings. The buyer can also run a linked pickup check against the original signed purchase report.
- Operator overview, search, audit, scan and model counts, guest revocation and report invalidation.
- Request correlation IDs and structured API logs with route templates, latency and status.
- Dockerfiles, Compose configuration, npm and uv locks, GitHub Actions and development and deployment guides.

## Partially implemented

- The desktop frontend, Windows Tauri source and native development flow are implemented. Signed installers and physical macOS acceptance remain pending. The separately tested PowerShell collector uses the same native readings as the Windows Tauri adapter.
- macOS, Android and iOS collectors expose a narrower set of supported readings. Expo handles seller consent, camera capture, preview and the share decision. Buyer chat is available in the shared workspace. Handoff capture uses the web workspace. Physical-device validation and packaged desktop/mobile apps remain pending.
- Adaptive inspection records missing evidence and flags visible differences for review. Native automated retests, independent hardware identity, device attestation and validated damage classification remain pending.
- Operator tools expose scan volumes, evidence bytes, claim discrepancies and model usage. Abuse review workflows, live platform health and hosted observability remain pending.

## Blocked by credentials or environment

- Moonshot's structured listing adapter has a mock test. Live testing needs the project API key and configured model ID in the local environment.
- Supabase authentication has a configuration path. The selected deployment for this build uses local PostgreSQL. Live Supabase Auth, hosted database and private Storage still need project configuration.
- Play Integrity and App Attest require platform configuration, signing and physical-device tests. No hardware-attested assurance is issued by this build.

## Not implemented

- A production Supabase Storage adapter, signed object URLs, push delivery, Sentry integration, and general application OpenTelemetry export.
- Play Integrity and App Attest provider code and associated device trust signals.
- Live market lookup. A labeled simulator pricing fixture and an optional local sold-comparables file are supported.
- Comprehensive native diagnostics, component identity/health, signing and distribution, and remote deployment.

The next milestones are physical-device and native desktop validation, private cloud storage, attestation, and comparison validation on real capture datasets. See the [local setup](development/setup.md) and [demo flow](ux/flows.md).

## Verification on November 23, 2026

- PostgreSQL migrated to revision `0005`. Alembic reported no schema drift. A rolled-back attempt to update a test report was rejected by its append-only trigger.
- All 15 pytest tests passed with PostgreSQL-backed coverage for authorization, consent, replay, privacy, signing, pricing, operator restrictions and handoffs.
- All four Playwright tests passed in Edge. They covered a real Windows CIM scan with a private photo and a seller-entered check, simulator sharing, seller decline and receiver acknowledgment followed by a signed handoff comparison.
- Python lint and types, TypeScript types and web lint passed. The Next.js production build and desktop frontend bundle passed. Expo exported Android and iOS JavaScript bundles.
- Compose configuration validated. Container execution, native Cargo build and physical macOS and mobile checks remain unverified.

The browser suite created test-only users and reports in the local database. PostgreSQL API tests used temporary schemas.

## Workspace redesign

- The web workspace uses one set of pages inside the configured desktop and mobile app windows. Native scanner screens use the same design tokens.
- Six Playwright tests passed, covering keyboard search, the report preview, phone navigation, verification filters, the real Windows purchase flow and handoffs.
- The Next.js production build, desktop frontend bundle, Android and iOS JavaScript exports, workspace TypeScript checks and web lint passed.
- The Windows Tauri configuration and source passed `cargo check --locked`. The native Windows development app built, launched, and its WebView connected to the local workspace. Physical-device validation on macOS, Android and iOS is still pending.

## Production hardening

- Requests are bounded by bytes received and time, with correlation IDs on rejected requests. PostgreSQL pools are configurable per process. The worker clears evidence and expires requests in bounded batches.
- Handoff lists use one query for the page. Owner lists have cursor pagination. Scan ticket renewal on the same platform preserves evidence while retiring old challenges.
- PostgreSQL integration tests and Playwright verified consent, sharing, signed reports, handoffs, cursor pagination and the Windows collector. Migrations were tested on a disposable database.

## Device advisor and guided scan

- Buyer chat defaults to signed reports shared with the signed-in buyer. The search supports text retrieval and optional pgvector semantic ranking. The bounded LangGraph tool loop requires model permission per question.
- Guided collection selects among fixed read-only Expo readers after seller approval. Invalid or unavailable model decisions use the local policy. Physical Android and iOS acceptance is still pending.
- The ProofScan operator dashboard shows aggregate agent usage. Optional Langfuse instrumentation exports agent metadata and requires the target project’s credentials. [Agent setup and architecture](architecture/agent.md)

## Public release review

- Buyer Chat provides an evidence-first comparison, with optional structured model actions and scoped text search if the vector index is unavailable.
- Expo and the desktop seller page can issue a short-lived camera link that accepts photos for the current scan. Readings and sharing remain on the original seller session.
- API readiness checks the deployed migration head. The [release review](release-readiness.md) lists the account, operational, and physical-device checks still required for public launch.
