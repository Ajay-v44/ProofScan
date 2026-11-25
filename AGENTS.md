# ProofScan contributor guide

ProofScan verifies used-device listings and records asset handoffs. Start with the [architecture](docs/architecture/overview.md), [local setup](README.md), and [trust boundaries](docs/security/threat-model.md). The [Codex evidence pack](docs/hackathon/codex-evidence-pack.md) records the challenge work.

## Repository map

- `apps/api` contains FastAPI, Alembic migrations, report signing, authorization, and agent tools.
- `apps/web` contains the Next.js presentation, workspace, seller pages, and operator tools. Read its `AGENTS.md` before editing Next.js code.
- `apps/mobile` and `apps/desktop` contain the Expo and Tauri clients. Keep native collection and permissions within the supported platform boundaries.
- `apps/worker` handles scheduled expiry and retention. The shared API client and design tokens live in `packages`.

## Changes and checks

- Use a disposable database for test runs and migration checks. Keep `.env` files, keys, transcripts, and database exports outside Git and container build contexts. Use synthetic devices and photos in public fixtures.
- Preserve owner authorization, seller consent, signed report compatibility, and evidence retention. Rank reports after applying ownership and eligibility filters. Keep raw account data out of model calls, search queries, and tracing.
- For API changes, run Ruff, mypy, and pytest using the setup in the README. For web changes, run the workspace lint and type checks, then exercise the user flow in Playwright at phone and desktop widths. Use the [CI workflow](.github/workflows/checks.yml) for platform checks.
- For release work, use the [deployment guide](docs/deployment/README.md) and [launch gates](docs/release-readiness.md). Record what ran, what passed, and any unverified platform or provider behavior.
