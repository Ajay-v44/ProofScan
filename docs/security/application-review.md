# ProofScan code review

This review covered authorization and session handling, data passed to the model provider, report and image access, public pricing, private catalog retrieval, Buyer Chat, and the web-to-native workspace boundary. Findings below describe code paths and the observed hosted environment. Hosted authentication, physical-device acceptance, and adversarial load need their own test results.

## Security and privacy

| Priority | Finding | Remediation |
| --- | --- | --- |
| P1 before hosting the API | [Request policy](../../apps/api/proofscan/request_policy.py) limits body size and read time. [Auth](../../apps/api/proofscan/auth.py) bounds local password work. The API has no distributed source limit before unauthenticated requests reach login, registration, guest exchange, or image endpoints. Chat’s per-account quota also leaves the provider budget exposed across many accounts. | Enforce route-specific request and concurrency limits at the ingress, with an independent provider spend cap and alert. Verify these controls against the deployment topology and across replicas. |
| P1 before hosted sign-in | [Logout](../../apps/api/proofscan/auth.py) clears the browser cookie. Session validation checks expiry and signature with no server-side revocation. A copied bearer token can remain usable until expiry. | Define session revocation for logout, credential changes, and reported compromise. Verify provider logout and access-token behavior separately. |
| P2 | [Listing assistance](../../apps/api/proofscan/suggestions.py) sanitizes common URLs, email addresses, and phone numbers. The remaining free text goes to Moonshot and can still contain names, addresses, serial numbers, and other copied identifiers. | Keep approval and the external-processing notice. Send only the snippets or fields needed to extract the three supported claims. Test representative device listings and private data patterns. |
| P2 before store submission | The [mobile privacy screen](../../apps/mobile/app/privacy.tsx) relies on a configured account-deletion URL. This repository has no account-deletion route, and the [release checklist](../release-readiness.md) still calls for the complete lifecycle. | Verify the live destination and document how deletion affects evidence retention, signed reports and active guest links. |
| P2 dependency maintenance | `npm audit --omit=dev` flagged three moderate entries in the Expo fingerprint dependency chain. The underlying advisory affects `minimatch`. | Validate an Expo-compatible dependency update with Expo Doctor and native builds. [GitHub advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249) |

Retain the existing owner checks, token scoping, short-lived scan tickets, signed report validation, image normalization, and no-store API responses. The public pricing tool reaches only the configured search provider. It sends a canonical model, market and bounded product options. It passes no saved listing content, photos, identifiers, session data or transcript to web search.

## Buyer Chat and agent quality

| Area | Observed behavior | Evaluation gap |
| --- | --- | --- |
| Routing and interaction | [Buyer Chat](../../apps/api/proofscan/agent/chat.py) routes by a bounded intent and device grammar. Straightforward lookup and help requests can run without an LLM. It uses four recent user turns for follow-ups. | Add a representative query set for colloquial phrasing, misspelled models, corrections, ambiguous preferences, and unsupported markets. Measure correct intent, useful clarification and false refusals by category. |
| Private retrieval | [Catalog retrieval](../../apps/api/proofscan/agent/catalog.py) filters by signed-in owner, validity, source, and budget before ranking. Deterministic measurements can sort eligible candidates. Backfill and missing vectors can add work to a chat request. The ranking query has no relevance cutoff for open-ended questions. | Evaluate relevant-source recall and ranking, including genuinely empty matches. Measure cold versus warm latency and move reindexing away from the hot path if it dominates. |
| Model selection and review | The optional two-pass model call selects and reviews source IDs. The model sees typed public facts. The UI renders application-owned copy. The same four-turn bound and fixed guides limit conversational depth. | Measure whether the optional reviewer improves citation precision and false-answer rate enough to justify its latency and tokens. Include cases where it rejects all safe evidence or the provider times out. |
| Device pricing | The [pricing skill](../../apps/api/proofscan/agent/pricing_skill.py) combines official launch evidence with matching retailer asking prices. Ineligible quotes never enter the range. Forecast quality and resale prices require different datasets. | Measure eligible-source coverage and compare estimates against held-out, local-currency sold transactions by model, configuration and condition before claiming resale accuracy. |

Use the [agent docs](../architecture/agent.md#device-pricing-skill) for the pricing rules, supported markets and a test question. Prices are handled as integer minor units. The phone estimate uses the median and observed range after condition, capacity, source and price filters. It computes a launch comparison only for the same storage tier. Price prediction accuracy has not been benchmarked against sold transactions.

## Web and native UX

| Priority | Finding | Remediation |
| --- | --- | --- |
| P1 for an end-to-end hosted demo | The [live marketing page](https://proofscan1.vercel.app/) offers **Open workspace**. The public Vercel deployment currently has no `API_INTERNAL_ORIGIN`. [Next.js configuration](../../apps/web/next.config.ts) routes the API through a loopback origin in that case. The live session endpoint returned a Vercel private-host error during the review. | Use the working on-page demo and runnable release as public entry points until the workspace API is deployed with hosted auth and smoke testing. |
| P2 | The shared chat composer carries settings in client state, with a short rolling conversation. A server reply of `unavailable` currently renders as a regular message. The transport-level retry control only appears on request errors. | Give temporary failures their own accessible recovery control, and make it clear that a new conversation or browser session resets context. |
| P2 | The workspace browser suite exercises reflow and navigation. Expo and Tauri still use platform-specific shells and permissions around the shared experience. | Validate the camera flows, keyboard resize, large text, and external-source copy on physical iOS and Android devices. |

The new price card separates current asking prices from the manufacturer’s starting price. It labels the storage and condition, counts independent retailers, and exposes the announcement beside the price. The external source controls keep a copy option for native shells that restrict external navigation.

## Verification

- The PostgreSQL and pgvector regression run passed 63 tests. A final run covering Buyer Chat and pricing passed 31 tests after adding market and storage clarification.
- The production web build, workspace type checks, Python type checks and lints passed. Twelve browser scenarios passed across the main run and a readiness-gated rerun. The real-Windows collector scenario was skipped. The price card was exercised at 320 px.
- A live India iPhone 15 Pro search took about 2.7 seconds at the provider stage. It returned one eligible 128 GB refurbished quote. The reply cited Apple’s 2023 launch price and withheld the market range. A controlled two-retailer fixture verified range and median calculation.
