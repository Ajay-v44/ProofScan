# ProofScan Codex evidence pack

ProofScan helps a used-device buyer check the seller’s claims and detect changes between the online listing and pickup. The buyer can request evidence with a private link, review a signed report after the seller shares it, and compare fresh readings and matching exterior photos at pickup. An equipment owner can record the same kind of before-and-after evidence for a handoff and return. A signature confirms report integrity. Physical identity and condition still require inspection.

The [challenge rubric](https://www.geeksforgeeks.org/build-with-codex-access-code) and [submission form](https://docs.google.com/forms/d/e/1FAIpQLScmhNGybHj5MBDIqfYy_u_bZWBR7xec9_VbiInaSVbRYESVjg/viewform) describe the public deliverables. The first repository commit is dated November 23, 2026. Use the workshop date from the attendance record to establish the one-month window.

## Lifecycle evidence

| Stage | Work and outcome | Evidence |
| --- | --- | --- |
| Understand | Defined the buyer’s uncertainty before paying, including misleading listing claims, a device swap at pickup, and changes while equipment is away. Separated the buyer, seller, receiver, and operator actions. | [Workflow walkthrough](../ux/flows.md), [threat model](../security/threat-model.md) |
| Plan | Chose private seller links, consent and explicit sharing, signed reports, separate capture and review, and a local PostgreSQL release path. Defined the trust boundaries between clients, agent tools, and private evidence. These architecture records describe the implemented decisions. | [Architecture](../architecture/overview.md), [data model](../architecture/data-model.md), [report signing](../security/report-signing.md) |
| Build | Implemented the web workspace, API, local persistence, seller and handoff flows, native collection paths, and Buyer Chat. Chat identifies allowed requests, filters private reports before ranking, and checks evidence before displaying responses. | [Initial implementation](https://github.com/Ajay-v44/ProofScan/commit/11d6137), [advisor and guided scan](https://github.com/Ajay-v44/ProofScan/commit/9ee57a4), [pickup recheck](https://github.com/Ajay-v44/ProofScan/commit/1b84613), [Buyer Chat](https://github.com/Ajay-v44/ProofScan/commit/85068e2) |
| Test | Ran database-backed API and Playwright tests for consent, signed reports, rechecks, handoffs, catalog access, and responsive chat. Checked the public device search with a synthetic device query and the reviewer’s ability to withhold evidence. | [API tests](../../apps/api/tests), [browser tests](../../apps/web/tests), [agent architecture](../architecture/agent.md), [public workflow run](https://github.com/Ajay-v44/ProofScan/actions/runs/45549803927) |
| Review | Reviewed authorization, evidence handling, abuse boundaries, UI reflow, and release gaps. Compared local and hosted test evidence. Recorded the remaining deployment and physical-device checks. | [Release review](../release-readiness.md), [security model](../security/threat-model.md), [Buyer Chat pull request](https://github.com/Ajay-v44/ProofScan/pull/3), [workspace image review](https://github.com/Ajay-v44/ProofScan/pull/4) |
| Document | Wrote setup and tests for each service, explained platform-specific collection, and documented privacy boundaries for local retrieval and public search. | [README](../../README.md), [agent operations](../architecture/agent.md), [mobile release](../development/mobile-release.md), [contributor guidance](../../AGENTS.md) |
| Ship | Produced a Next.js production build and installed testable local workflows. The marketing page demonstrates purchase, pickup, and return scenarios. The Compose source bundle is the candidate for a versioned challenge release. | [Marketing implementation](https://github.com/Ajay-v44/ProofScan/pull/1), [runnable demo guide](run-proofscan.md), [release status](#release-status) |
| Automate | Added GitHub Actions for web and API checks, Expo exports, and Windows and macOS validation. Celery schedules expiry and retention. The scheduler and GitHub Actions are separate from any Codex scheduled task. | [GitHub Actions](../../.github/workflows/checks.yml), [worker schedule](../../apps/worker/tasks.py) |

## Codex capability use and fit

| Capability | How it was used |
| --- | --- |
| Repository and terminal work | Traced workflow boundaries, implemented changes across Python and TypeScript, and ran linters, builds, migration checks, and tests from the checkout. Git commits and the linked pull requests record the resulting changes. |
| MCP | Verified the shadcn, Context7, and Sequential Thinking servers responded during project setup. Used the GitHub connector for repository visibility and the Vercel connector to check for an existing linked deployment during submission prep. Tool availability and deployment status were checked separately from product features. |
| Skills and browser verification | Used the build-agents skill to assess the existing workflow and retain the project’s FastAPI and LangGraph architecture. Used the verification skill and Playwright/Edge to exercise workspace navigation and responsive image cards. |
| Documentation and evaluation | Converted feature decisions, test results, environment assumptions, and known limits into public review and setup docs. Used first-party documentation to verify Moonshot public search behavior and the challenge rubric. |

## Models and reasoning effort

| Context | Recorded use |
| --- | --- |
| Codex engineering | Project session metadata on November 23 recorded `gpt-6.2-sol` at medium and high effort. Medium and high were both observed during early setup. Subsequent recorded development turns that day used high effort. This is a partial record. Historical per-stage attribution and effort for the remaining turns are unverified. |
| Codex effort guidance for follow-up | Reserve high effort for cross-module changes involving authorization, buyer and seller trust boundaries, signed evidence, and release diagnostics. Use medium for scoped documentation and UI checks. Record the actual model and effort alongside the resulting commit or test output as each task completes. |
| ProofScan application models | Buyer Chat’s configured decision model defaults to `kimi-k3`; a separate optional reviewer and the inexpensive synthetic test model default to `kimi-k2.6`. These are runtime integrations. Private report verification is local. The optional FastEmbed model is a local retrieval dependency. [Runtime model configuration](../architecture/agent.md#base-api-and-moonshot) |

## Verification and release status

- Local verification during the chat work included a 50-test API suite with PostgreSQL and pgvector, followed by 19 focused checks after the final changes. The production web build and 11 browser tests passed. One real-Windows collector case was skipped in that browser run. Earlier Windows collector validation is recorded in the [implementation status](../status.md).
- On November 25, 2026, the challenge source archive built from a clean extraction with Docker Compose and generated demo secrets. Migrations completed and the web and API health checks returned HTTP 200. Three browser tests passed against that stack. They covered the responsive presentation, seller consent through a buyer’s signed simulator report, and a receiver-acknowledged handoff through signed return comparison.
- In the [public workflow](https://github.com/Ajay-v44/ProofScan/actions/runs/45549803927), the mobile and two desktop jobs passed. The web/API job reached post-run cleanup and failed when `uv cache prune --ci` timed out on a cache lock. The workflow now starts the test API with the installed Python and shuts down both test servers on exit. This change needs a hosted CI run to confirm the fix.
- The challenge demo uses simulated inputs with an explicit diagnostic assurance label. The [runnable demo guide](run-proofscan.md) covers local setup. The [public launch review](../release-readiness.md) tracks hosted authentication, operational validation, and signed native distribution separately.
