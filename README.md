# ProofScan

ProofScan helps buyers verify claims about a used device. A buyer creates a private seller link. For a new real-device check, the seller consents, collects supported hardware readings and photographs the front and back. The seller reviews the evidence and decides whether to share a signed report. The buyer can compare shared reports in Buyer chat and run a fresh check at pickup.

ProofScan also records asset handoffs. Owners capture a baseline, can request receiver acknowledgment, and record the return to generate a signed comparison. Generic items use notes and photos. Windows handoffs can additionally compare hardware readings.

For the GeeksforGeeks × OpenAI challenge, see the [Codex evidence pack](docs/hackathon/codex-evidence-pack.md) and the [runnable demo guide](docs/hackathon/run-proofscan.md).

## Contents

- [Services and ports](#services-and-ports)
- [Install and configure](#install-and-configure)
- [Run with Docker Compose](#run-with-docker-compose)
- [Run services locally](#run-services-locally)
- [Desktop, Windows collector, and mobile](#desktop-windows-collector-and-mobile)
- [Optional integrations](#optional-integrations)
- [First verification and handoff](#first-verification-and-handoff)
- [Tests and builds](#tests-and-builds)
- [Configuration reference](#configuration-reference)
- [Deployment and operations](#deployment-and-operations)
- [Troubleshooting](#troubleshooting)
- [Repository map and guides](#repository-map-and-guides)

## Services and ports

| Service | What it does | Default address or entry point | Dependencies |
| --- | --- | --- | --- |
| Web | Public product presentation, buyer workspace, seller pages, handoffs, signature check, and operator tools | [Presentation](http://localhost:3000/home) · [Workspace](http://localhost:3000/workspace) | API for workspace workflows |
| API | FastAPI authentication, verification state, evidence, reports, signing, and operator endpoints | [Health](http://127.0.0.1:8000/health), [OpenAPI docs](http://127.0.0.1:8000/docs) | Migrated PostgreSQL, report signing key |
| PostgreSQL | Stores accounts, verification state, private evidence, report records, and audit events | Host port `5432` or Compose service `db` | Database credentials and migrations |
| Migrations | Alembic applies schema changes before the API and worker start | `alembic upgrade head`; one-shot Compose service `migrate` | PostgreSQL |
| Redis | Celery message broker | Host port `6379` or Compose service `redis` | Worker and scheduler connect here |
| Worker | Executes scheduled verification expiry, evidence cleanup, and agent execution cleanup | `apps/worker/tasks.py`; Compose service `worker` | PostgreSQL, Redis |
| Scheduler | Celery Beat enqueues verification expiry every minute and retention jobs hourly | Compose service `scheduler` | Redis, a running worker to execute jobs |
| Desktop | Tauri workspace window and native collector | Local app; Vite on `127.0.0.1:1420` during development | Rust, platform toolchain, reachable web workspace |
| Mobile | Expo workspace window and native seller scanner for Android and iOS | Expo development client and Metro | Device or emulator, reachable web workspace |

PostgreSQL, the API, and the web app are enough to try the verification flow. Run Redis, the worker, and the scheduler to exercise background processing. Guest links expire on access even while the worker is stopped. The scheduled cleanup removes expired image bytes while retaining the signed digests.

## Install and configure

Clone the repository and open a terminal in the checkout that contains `package.json`, `pyproject.toml`, and `docker-compose.yml`. Run commands from that directory unless a block specifies another location.

| Tool | When to install it |
| --- | --- |
| Git | To clone and update the repository. [Git downloads](https://git-scm.com/downloads) |
| Docker Engine or Docker Desktop with Compose v2 | To run the container stack, or to run Redis for a local worker. [Docker Compose installation](https://docs.docker.com/compose/install/) |
| Node.js 22.13+ in the 22.x line and npm | To run or build the web, Tauri frontend, or Expo app on your host. [Node.js downloads](https://nodejs.org/en/download) |
| uv and Python 3.12 | To run Python dependency setup, the API, migrations, worker, and tests on your host. uv can download Python when needed. [uv installation](https://docs.astral.sh/uv/getting-started/installation/) |
| PostgreSQL 17 | To run the API against a locally installed database. Compose supplies its own PostgreSQL 17 instance. [PostgreSQL downloads](https://www.postgresql.org/download/) |
| Redis 7 | To run the worker and scheduler with a local broker. Compose also supplies it. [Redis installation](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/) |

On a fresh checkout, copy the environment template once. Keep an existing `.env` when updating a checkout.

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

Edit the ignored root `.env`. For a local verification demo, use `AUTH_MODE=local`, `WEB_ORIGIN=http://localhost:3000`, and `ENABLE_SIMULATOR=true`. Choose the database settings below for the run path you use. A local browser should open the same origin as `WEB_ORIGIN`, including the hostname and port.

Generate the two secrets on your machine. With uv installed, these commands work in PowerShell and Bash.

```sh
uv sync --locked --python 3.12 --no-install-project
uv run --no-sync python -c 'import secrets; print(secrets.token_urlsafe(48))'
uv run --no-sync python -c 'import base64; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; print(base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode().rstrip(chr(61)))'
```

For a Docker-only setup, generate the same values with the API image.

```sh
docker build -f infrastructure/docker/api.Dockerfile -t proofscan-api:local .
docker run --rm proofscan-api:local python -c 'import secrets; print(secrets.token_urlsafe(48))'
docker run --rm proofscan-api:local python -c 'import base64; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; print(base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode().rstrip(chr(61)))'
```

Save the first value as `LOCAL_AUTH_SECRET` and the second as `REPORT_PRIVATE_KEY`. Give the signing key a stable ID in `REPORT_KEY_ID`, such as the template’s `local-1`. Keep credentials in the ignored `.env` or a secret manager. Reuse the signing key across restarts and back it up securely to support report verification and key rotation. [Report signing](docs/security/report-signing.md)

## Run with Docker Compose

1. Start Docker. Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in `.env`. Replace the template password before the first boot.
2. Set `COMPOSE_DATABASE_URL` to use the same credentials and the `db` hostname. The template format is `postgresql+asyncpg://postgres:CHANGE_ME@db:5432/proofscan`. Percent-encode special characters in the URL credentials. Use the actual password in `POSTGRES_PASSWORD`.
3. Run these commands.

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps -a
docker compose logs --tail=50 migrate api web worker scheduler
```

The database initializes a named volume on first boot. Once PostgreSQL is healthy, `migrate` applies the migrations and should exit with code 0. The API and worker then start. Next.js proxies `/api/v1` to the container API at `http://api:8000`. The Compose file publishes only the web and API ports on the host loopback interface. PostgreSQL and Redis are available to the services over the Compose network.

Open [ProofScan](http://localhost:3000) and check [API health](http://127.0.0.1:8000/health). To inspect the database, run the following in an interactive terminal.

```sh
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec redis redis-cli ping
```

Use `docker compose down` to stop the stack while keeping the database volume. PostgreSQL uses the bootstrap user, password, and database values when the volume is first initialized. If you change credentials later, update the existing database role and connection URL together.

## Run services locally

### PostgreSQL

Install and start PostgreSQL. Create an application database, for example `proofscan`. If PostgreSQL’s command-line tools are on your PATH and the server has a `postgres` role, run the following and enter the local password when prompted. You can also create the database in pgAdmin. Use the existing database name if one is already provisioned for this checkout.

```sh
createdb -h 127.0.0.1 -p 5432 -U postgres -W proofscan
```

In `.env`, set `DATABASE_URL` to your database, with the form `postgresql+asyncpg://USER:PASSWORD@127.0.0.1:5432/DATABASE`. Percent-encode the username and password in the URL if they contain special characters. Compose uses `COMPOSE_DATABASE_URL` for its services.

### Migrations and API

Install the Python dependencies and apply migrations. Repeat `upgrade head` after pulling changes that include migrations.

```sh
uv sync --locked --python 3.12 --no-install-project
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

Start FastAPI in its own terminal.

```powershell
$env:PYTHONPATH = "apps/api"
uv run --no-sync uvicorn proofscan.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
PYTHONPATH=apps/api uv run --no-sync uvicorn proofscan.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [health](http://127.0.0.1:8000/health) and confirm it returns `{"status":"ok"}`. [OpenAPI docs](http://127.0.0.1:8000/docs) and the [API integration guide](docs/api/integration.md) describe the endpoints. FastAPI reads `.env` from the repository root and checks that the database schema and signing configuration are available at startup.

### Web workspace

In a second terminal, install the npm workspaces and start Next.js.

```sh
npm ci
npm run dev
```

Open the [buyer workspace](http://localhost:3000/workspace) or the [public presentation](http://localhost:3000/home). Next.js sends browser API requests through its same-origin `/api/v1` rewrite. The upstream defaults to `http://127.0.0.1:8000`. If the API uses a different address, set `API_INTERNAL_ORIGIN` in the web process environment before starting Next.js. Set it before the production build as well when using the generated standalone server.

The presentation includes interactive sample reports for purchase, pickup, and return checks. See [marketing settings](docs/deployment/README.md#public-marketing-and-downloads) to configure the public domain and platform downloads.

To enable operator tools, sign in with the intended account. Open `/api/v1/auth/session` on the web origin in that browser session, copy its user ID, and add the UUID to the JSON array in `ADMIN_SUBJECTS`. Restart the API and refresh the workspace.

### Redis, worker, and scheduler

Start Redis 7. If you have Docker and want a broker for local development, leave this command running in its own terminal.

```sh
docker run --rm --name proofscan-redis -p 127.0.0.1:6379:6379 redis:7-alpine
```

It listens on the default `REDIS_URL=redis://127.0.0.1:6379/0`. Use a different port in both settings if the default is occupied. Run the worker and the scheduler in two more terminals after applying database migrations.

PowerShell worker

```powershell
$env:PYTHONPATH = "apps/api;apps/worker"
uv run --no-sync celery -A tasks:celery worker --pool=solo --loglevel=INFO
```

PowerShell scheduler

```powershell
$env:PYTHONPATH = "apps/api;apps/worker"
uv run --no-sync celery -A tasks:celery beat --loglevel=INFO --schedule="$env:TEMP/proofscan-beat"
```

On macOS or Linux, use the following in separate terminals.

```bash
PYTHONPATH=apps/api:apps/worker uv run --no-sync celery -A tasks:celery worker --loglevel=INFO
PYTHONPATH=apps/api:apps/worker uv run --no-sync celery -A tasks:celery beat --loglevel=INFO --schedule=/tmp/proofscan-beat
```

Check the worker logs for a broker connection and the scheduler logs for dispatched jobs. Use the Windows solo pool for development. A Linux container is the deployment path for the worker. Run one scheduler per environment.

## Desktop, Windows collector, and mobile

### Tauri desktop app

Install Rust stable and the platform prerequisites. On Windows, install the Visual Studio C++ build tools, Windows SDK, and Edge WebView2 runtime. On macOS, install the Xcode command-line tools for development. [Tauri platform prerequisites](https://v2.tauri.app/start/prerequisites/)

Keep the API and web workspace running, then start the desktop app.

```sh
npm ci
npm run tauri -w @proofscan/desktop -- dev
```

The development app opens the browser workspace at `http://localhost:3000/workspace`. In the app menu, select **ProofScan → Device scanner**, open a matching platform ticket, and export the readings. Import the scan into the seller page to review it. On macOS the collector reads available model, CPU name, and memory. See the [implementation status](docs/status.md) for platform validation.

To build the native desktop executable, export an HTTPS `PROOFSCAN_WEB_ORIGIN` in the build terminal, then run the matching command.

```powershell
$env:PROOFSCAN_WEB_ORIGIN = "https://proofscan.example"
npm run tauri -w @proofscan/desktop -- build
```

```bash
PROOFSCAN_WEB_ORIGIN=https://proofscan.example npm run tauri -w @proofscan/desktop -- build
```

Replace the reserved example domain with the deployed workspace origin. The current Tauri config disables installer bundling. Signed installers require platform-specific packaging and signing configuration.

### Windows PowerShell collector

This collector can run on the device being sold without installing the desktop app. On the seller page, consent, choose Windows, and download the collector and its ticket. Use PowerShell on the Windows device and run this from the directory containing both files.

```powershell
./collect-windows.ps1 -TicketFile ./proofscan-ticket.json -OutputFile ./proofscan-scan.json
```

Import the generated JSON on the seller page before the ticket expires. Keep the ticket and scan output private. The workspace serves the script from [`apps/web/public/collect-windows.ps1`](apps/web/public/collect-windows.ps1). Windows host policy applies to the downloaded script.

### Expo mobile app

Install Android Studio and the Android SDK for a local Android development build. Local iOS builds require macOS and Xcode. Start the API and web workspace, and set `EXPO_PUBLIC_PROOFSCAN_ORIGIN` to the workspace origin reachable by the device. The API’s `WEB_ORIGIN` must match the origin users actually open. A physical phone’s `localhost` points to the phone. Use a reachable HTTPS workspace for device checks. [Expo development build setup](https://docs.expo.dev/develop/development-builds/create-a-build/)

Place the public mobile variables in `apps/mobile/.env.local` or export them in the Expo process. From the repository root, run `npm ci`, then build and install the development client with the command for your platform.

```sh
npm exec -w @proofscan/mobile -- expo run:android
# Or, on macOS
npm exec -w @proofscan/mobile -- expo run:ios
```

The first native run generates the platform project locally. Start Metro for subsequent development sessions and open the installed development client.

```sh
npm run dev -w @proofscan/mobile
```

Tap **Scan device**, paste the original seller link, and follow consent, optional photo capture, hardware collection, review, and the sharing decision. Use a physical device to collect native hardware readings. To use a signed internal build instead, follow the EAS development and preview profiles, signing steps, and device checklist in the [mobile release guide](docs/development/mobile-release.md).

## Optional integrations

| Integration | Setup and verification |
| --- | --- |
| Supabase Auth | Set `AUTH_MODE=supabase`, the HTTPS `SUPABASE_URL`, and its `SUPABASE_PUBLISHABLE_KEY`. Use an asymmetric signing key in the Supabase project. Restart the API and test registration, any email confirmation, sign-in, and sign-out. |
| Hosted PostgreSQL | Set `DATABASE_URL` for an isolated, compatible database or schema with the appropriate PostgreSQL role. Apply migrations before switching the API and worker to that database. Authentication and database hosting can be configured independently. |
| Moonshot listing assistance | In the API environment, set `KIMI_API_KEY`, an HTTPS `KIMI_BASE_URL`, and a `KIMI_MODEL` that supports JSON responses. Restart the API and use the listing suggestion action from an authenticated account. The manual claims flow works without this integration. `KIMI_VISION_MODEL` is reserved; image checks currently use local OpenCV. [Agent and model integration](docs/architecture/agent.md) |
| Comparable pricing | Set `PRICING_COMPARABLES_FILE` to a JSON file available to the API process. Each saved sale needs `device`, `currency`, `amount`, `sold_on`, and a unique `reference`. Matching pricing requires at least three recent, distinct sales in one currency. For a container deployment, mount the file and use its container path. [Comparable pricing format](docs/development/setup.md#comparable-pricing) |
| Buyer chat and guided scan | Open `/advisor` to ask about ProofScan, compare your shared reports, or look up public prices and specifications. The Expo scanner supports approval-gated collection and fixed alternate readers. The operator dashboard shows aggregate usage. [Agent setup and architecture](docs/architecture/agent.md) |

Processed exterior photos currently live in PostgreSQL. See [implementation status](docs/status.md) for hosted object storage, mobile attestation, and other integrations awaiting implementation or live verification.

## First verification and handoff

### Purchase verification

1. In the [buyer workspace](http://localhost:3000/workspace), create a buyer account and sign in. Create a verification with a device name and one or more listing claims.
2. Open the generated seller link in a separate browser profile or private window. Give consent and complete the enabled simulator flow or collect supported device readings and clear front and back photos.
3. Review the collected information and select **Share signed report**. Return to the buyer workspace and open the completed verification’s report.
4. Use the public **Verify** page at `/verify` and enter the report ID. Test a separate seller request with the decline option to verify that the buyer cannot open a private report.
5. Open **Buyer chat** to ask about your shared devices. At pickup, select **Create pickup recheck link** on the original report to compare fresh readings and photos of the device in hand.

When checking a phone in the Expo scanner, use **Share camera link** to take its front and back photos on another device. Select **Refresh photos** on the original scanner to continue.

### Asset handoff

1. Open **Handoffs**, create an asset, then record its baseline using photos, the Windows collector, or the enabled simulator.
2. If receiver acknowledgment is required, open the invitation in a separate session and accept it. Refresh the owner’s workspace and mark the asset as handed off.
3. Record the return and open the signed comparison report. For photo comparisons, capture the same angle at baseline and return.

See [demo scenarios and platform coverage](docs/ux/flows.md) for matching and mismatched claims, supported device readings, and additional workflows.

See the [release review](docs/release-readiness.md) for the platform decisions and public launch gates.

## Tests and builds

Run the Python checks after dependency setup.

```sh
uv run --no-sync alembic check
uv run --no-sync ruff check apps/api apps/worker
uv run --no-sync mypy apps/api/proofscan apps/worker
uv run --no-sync pytest -q
```

Set `TEST_DATABASE_URL` in the shell before running pytest to include PostgreSQL integration tests. Use a separate test database and a role that can create and drop the temporary schemas. The tests skip the PostgreSQL suite when this variable is unset.

```sh
npm run typecheck
npm run lint -w @proofscan/web
npm run build -w @proofscan/web
npm run build -w @proofscan/desktop
cargo test --locked --manifest-path apps/desktop/src-tauri/Cargo.toml
npm run test -w @proofscan/mobile
npm exec --yes --workspace @proofscan/mobile --package=expo-doctor@1.21.8 -- expo-doctor
npm run export -w @proofscan/mobile -- --platform all --max-workers 3
```

The desktop npm build produces the frontend assets. Tauri builds the native executable. The Expo export produces Android and iOS JavaScript bundles under `apps/mobile/dist`. EAS produces installable or store artifacts with the selected signing configuration.

To run the standalone web build locally, first build the web workspace, stop the development web server, and keep the API running. Copy the static assets and start the generated server.

```powershell
Copy-Item -Recurse -Force apps/web/.next/static apps/web/.next/standalone/apps/web/.next/
Copy-Item -Recurse -Force apps/web/public apps/web/.next/standalone/apps/web/
$env:HOSTNAME = "127.0.0.1"
$env:PORT = "3000"
node apps/web/.next/standalone/apps/web/server.js
```

```bash
cp -r apps/web/.next/static apps/web/.next/standalone/apps/web/.next/
cp -r apps/web/public apps/web/.next/standalone/apps/web/
HOSTNAME=127.0.0.1 PORT=3000 node apps/web/.next/standalone/apps/web/server.js
```

For browser tests, use a development environment with local authentication and the simulator enabled. Start both the API and the web app, then run the following.

```sh
npx playwright install chromium
npm run e2e -w @proofscan/web
```

The E2E tests create test accounts and records through the running API. Use test data. Set `PROOFSCAN_BROWSER_CHANNEL=msedge` to use installed Edge. On Windows, set `PROOFSCAN_REAL_WINDOWS=1` to include the actual CIM collector test. See the [CI workflow](.github/workflows/checks.yml) for the full test matrix.

## Configuration reference

The [environment template](.env.example) lists server and app values. Server variables belong in the backend process or ignored root `.env`. Set the web and desktop variables in their own process environments. Expo loads its public variables from the app project or build environment.

| Variable | Where it is used |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL URL for the host API, Alembic, and worker |
| `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` | Persistent and additional PostgreSQL connections allowed per application process, each defaulting to 5 |
| `COMPOSE_DATABASE_URL` | The connection URL passed to Python services by Compose, normally with hostname `db` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | First-boot settings of the Compose PostgreSQL service |
| `REDIS_URL` | Celery broker URL. Compose supplies `redis://redis:6379/0` to its services. |
| `WEB_ORIGIN` | Exact browser origin for API origin checks and secure-cookie behavior |
| `API_INTERNAL_ORIGIN` | Upstream API origin used by Next.js when serving or building the web app |
| `AUTH_MODE`, `LOCAL_AUTH_SECRET` | Auth provider selection and the private signing secret for local browser sessions |
| `REPORT_KEY_ID`, `REPORT_PRIVATE_KEY`, `REPORT_TRUSTED_KEYS` | Active report key ID, its private Ed25519 key, and the optional JSON map of older public keys |
| `ENABLE_SIMULATOR`, `ADMIN_SUBJECTS` | Labeled demo fixtures and a JSON array of operator user UUIDs |
| `EVIDENCE_RETENTION_DAYS` | Evidence lifetime in days. Defaults to 30 and accepts 1 through 365. |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | Project settings for the optional Supabase Auth integration |
| `KIMI_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL`, `KIMI_VISION_MODEL` | Moonshot listing-assistance configuration and the reserved vision model setting |
| `AGENT_MODEL`, `AGENT_TEST_MODEL`, `AGENT_REVIEW_MODEL` | Models for agent decisions, synthetic probes, and the optional second-pass Buyer Chat review |
| `AGENT_VECTOR_ENABLED`, `AGENT_EMBEDDING_CACHE` | Enable PostgreSQL semantic retrieval and set the local model cache path |
| `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Optional server-side metadata tracing |
| `PROOFSCAN_POSTGRES_IMAGE`, `PROOFSCAN_INSTALL_AGENT` | Compose PostgreSQL image override and optional API image dependencies |
| `PRICING_COMPARABLES_FILE` | Optional local path to operator-provided sold listings |
| `PROOFSCAN_WEB_ORIGIN` | Desktop workspace origin embedded when compiling the native app |
| `EXPO_PUBLIC_PROOFSCAN_ORIGIN` | Workspace origin embedded in the mobile app |
| `EXPO_PUBLIC_PROOFSCAN_PRIVACY_URL`, `EXPO_PUBLIC_PROOFSCAN_DELETE_ACCOUNT_URL` | Public HTTPS links required for mobile preview and production builds |
| `TEST_DATABASE_URL`, `PROOFSCAN_WEB_URL` | Separate PostgreSQL integration test URL and optional Playwright base URL override |

Expo public values are readable from the app bundle. Database passwords, auth and report signing keys, provider API keys, and signing credentials belong in private environment or credential stores. Git ignores local environment files and Codex configuration.

## Deployment and operations

1. Provision PostgreSQL and Redis. Keep the broker and database private. Apply Alembic migrations using a deployment role, then run the API and worker with a restricted runtime role.
2. Build the web image with `API_INTERNAL_ORIGIN` pointing to the API service. Deploy it behind HTTPS and preserve browser access to `/api/v1` through the same origin.
3. Set `WEB_ORIGIN` to the public origin, provide the real secrets to the API and worker, and set `ENABLE_SIMULATOR=false` for normal use. Run a single Celery Beat scheduler.
4. Check API health, sign-in, an end-to-end seller verification, signature verification, scheduler activity, and database backups before routing user traffic. Protect private seller links, photos, and scan files when collecting support diagnostics.
5. For mobile distribution, link the EAS project, configure signing, and validate internal builds on physical Android and iOS devices. Point the app to the deployed HTTPS privacy and `/account/delete` pages. Test hosted account deletion with the configured API, worker, and scheduler before store submission.

See the [deployment guide](docs/deployment/README.md), [report key rotation guide](docs/security/report-signing.md), and [mobile release guide](docs/development/mobile-release.md).

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Compose reports a missing required variable | Confirm the root `.env` has `POSTGRES_PASSWORD`, `COMPOSE_DATABASE_URL`, `REPORT_KEY_ID`, and `REPORT_PRIVATE_KEY`. Run `docker compose config --quiet` again. |
| API fails with a connection or missing-table error | Confirm PostgreSQL is running, the URL points to the intended database, and migrations ran against that same URL. |
| Browser sign-in or other writes return 403 | Compare the browser URL with `WEB_ORIGIN`. `localhost` and `127.0.0.1` are different origins. Check API reachability and the web proxy upstream. |
| Worker connects but expiry jobs never run | Confirm Beat is running, both Celery processes use the same `REDIS_URL`, and the task is visible in the worker log after scheduling. |
| Compose web or API fails to bind its port | Check whether a host development process is already listening on port 3000 or 8000. Stop that process or update the Compose mapping and matching browser origin. |
| Expo opens but the workspace does not load | Check the workspace URL from the device's browser. Confirm the installed build received `EXPO_PUBLIC_PROOFSCAN_ORIGIN` and that the device trusts the HTTPS certificate. Metro reachability and workspace reachability are separate checks. |
| Windows collector rejects a ticket or fails to execute | Download a fresh ticket for the matching platform and confirm the script runs on Windows with access to CIM and permission under the host’s script policy. |
| A mobile release reports a missing public URL | Set all three public Expo URLs in the EAS environment selected by the build profile. Ensure the privacy and account-deletion pages are reachable from a device. |

## Repository map and guides

| Path | Contents |
| --- | --- |
| [`apps/api`](apps/api) | FastAPI, domain services, PostgreSQL models, migrations, and API tests |
| [`apps/web`](apps/web) | Next.js workspace, seller and handoff pages, reports, operator tools, and Playwright tests |
| [`apps/desktop`](apps/desktop) | Tauri window, React frontend, and native Rust collectors |
| [`apps/mobile`](apps/mobile) | Expo app, native scanner, secure session storage, and EAS profiles |
| [`apps/worker`](apps/worker) | Celery job implementations and scheduling |
| [`packages/api-client`](packages/api-client) | Shared TypeScript API contracts and transport |
| [`packages/design-tokens`](packages/design-tokens) | Shared workspace and native UI tokens |
| [`infrastructure/docker`](infrastructure/docker) | API, worker, and web Dockerfiles |

- [Local development notes](docs/development/setup.md) and [mobile release](docs/development/mobile-release.md)
- [Architecture](docs/architecture/overview.md), [data model](docs/architecture/data-model.md), and [API integration](docs/api/integration.md)
- [Agent workflows, pgvector, and Langfuse](docs/architecture/agent.md)
- [Threat model](docs/security/threat-model.md) and [report signing](docs/security/report-signing.md)
- [Deployment](docs/deployment/README.md), [demo flows](docs/ux/flows.md), and [implementation status](docs/status.md)
