# Local development

## Configuration

Copy `.env.example` to `.env`. The API reads the root file when launched from the repository root. Supply an asyncpg PostgreSQL URL with percent-encoded credentials. Use `WEB_ORIGIN=http://localhost:3000` for the commands below. Set `ENABLE_SIMULATOR=true` for demos and browser tests.

Use these commands from the repository root. Store the printed values only in the ignored environment file or a secret manager.

```powershell
uv sync --python 3.12 --no-install-project
npm ci
uv run --no-sync python -c 'import secrets; print(secrets.token_urlsafe(48))'
uv run --no-sync python -c 'import base64; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; print(base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode().rstrip("="))'
```

Put the first value in `LOCAL_AUTH_SECRET` and the second in `REPORT_PRIVATE_KEY`. Set a stable `REPORT_KEY_ID`. Create the named database before migrating it. The application creates its tables through Alembic.

## API and web

```powershell
uv run --no-sync alembic upgrade head
$env:PYTHONPATH = "apps/api"
uv run --no-sync uvicorn proofscan.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, run `npm run dev` and open [ProofScan](http://localhost:3000). The Next.js server forwards `/api/v1` to the API at `API_INTERNAL_ORIGIN`, which defaults to `http://127.0.0.1:8000`. [OpenAPI docs](http://127.0.0.1:8000/docs) are available directly from the API.

Register an ordinary account. To provision operator access locally, read its UUID from `/api/v1/auth/session` while signed in, set `ADMIN_SUBJECTS=["<uuid>"]` and restart the API. Operator functions then appear in the sidebar.

## Windows desktop

Install Rust stable, Visual Studio Build Tools with MSVC and the Windows SDK, and the Edge WebView2 runtime. Start the web workspace, then run `npm run tauri -w @proofscan/desktop -- dev`. The desktop development app opens the workspace at `http://localhost:3000`. Choose **ProofScan → Device scanner** to load a scan ticket and export readings. Use `PROOFSCAN_WEB_ORIGIN` in the Tauri build environment to set a release workspace origin over HTTPS. The Windows collector is also downloadable from the seller page.

## macOS and mobile

On a Mac, install Xcode command-line tools and Rust stable. Run the same Tauri development command and choose macOS when issuing a desktop seller ticket. The macOS collector reads system model and memory, plus processor name where available. It requires a separate native build and device check.

For Android and iOS, use an Expo development host and a phone that can reach the configured ProofScan origin. Set `WEB_ORIGIN` on the API and `EXPO_PUBLIC_PROOFSCAN_ORIGIN` in the Expo process to that same origin. Use HTTPS for a device build. Run `npm run dev -w @proofscan/mobile` and open a compatible Expo client or development build. The app opens the same workspace as the browser. Choose **Device scanner** and paste the original seller link to collect native readings. The app retains the scoped seller session in the OS secure store.

Run `npm run export -w @proofscan/mobile -- --platform all` to produce Android and iOS JavaScript bundles. Native packaging, universal links and attestation also require platform configuration.

## Worker

Start Redis before starting the worker. Run these commands in two terminals. Windows needs the Celery solo pool.

```powershell
$env:PYTHONPATH = "apps/api;apps/worker"
uv run --no-sync celery -A tasks:celery worker --pool=solo --loglevel=INFO
```

```powershell
$env:PYTHONPATH = "apps/api;apps/worker"
uv run --no-sync celery -A tasks:celery beat --loglevel=INFO
```

## Checks

```powershell
uv run --no-sync alembic check
uv run --no-sync ruff check apps/api apps/worker
uv run --no-sync mypy apps/api/proofscan apps/worker
uv run --no-sync pytest -q
npm run typecheck
npm run lint -w @proofscan/web
npm run build
cargo test --locked --manifest-path apps/desktop/src-tauri/Cargo.toml
```

Set `TEST_DATABASE_URL` to a PostgreSQL test URL for integration tests. The suite creates and drops its own randomly named schemas. Playwright expects the API and web servers running, with local authentication and simulator enabled. Run `npx playwright install chromium` and `npm run e2e -w @proofscan/web`. Set `PROOFSCAN_BROWSER_CHANNEL=msedge` to use installed Edge. Set `PROOFSCAN_REAL_WINDOWS=1` on Windows to include the actual CIM collector test.

On this workspace host, Windows Application Control blocked uv's generated launcher. The official Python.org embeddable executable could load the workspace virtual environment's installed packages via its `python312._pth`. The commands above use the standard uv launcher on development hosts that allow it.

On this checkout, the API can also be run with `& .python/official312/python.exe -m uvicorn proofscan.main:app --host 127.0.0.1 --port 8000`. The real Windows browser test uses PowerShell 7 by default and respects the configured script execution policy. The native Tauri build still requires a Windows environment allowed to execute Cargo build outputs.

## Comparable pricing

Set `PRICING_COMPARABLES_FILE` to an operator-supplied JSON array of sold listings. Each record needs `device` matching the reported manufacturer plus model, `currency` as a three-letter code, `amount` as a whole unit in that currency, `sold_on` in ISO date format and a unique `reference`. ProofScan requires at least three distinct recent sales in a single currency. Without enough source data, real reports display pricing unavailable. Simulator ranges are labeled demo fixtures.
