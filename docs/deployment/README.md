# Deployment

## Local Compose

Copy `.env.example` to `.env`, generate the two secrets and set `COMPOSE_DATABASE_URL` to the internal `db` hostname and matching `POSTGRES_*` values. Enable the simulator only when needed.

```powershell
docker compose config --quiet
docker compose build
docker compose up
```

Compose creates a local PostgreSQL volume and starts a one-shot migration before starting the API and worker. The web and API are exposed on loopback. Check `docker compose ps` and `docker compose logs --tail=50` to verify startup.

## Hosted environment

Use HTTPS, a restricted database role on an isolated application database or schema, and separate migration credentials. Grant the runtime role the required table permissions and RLS access. Keep secrets outside the source and image layers. Set `WEB_ORIGIN` to the exact public origin, and use the internal API address when building Next.js. Deploy the worker and a single scheduler with private Redis access. Validate login, seller expiry, certificate trust and public signature verification before routing user traffic.

Set `DEPLOYMENT_ENVIRONMENT=production` for the public release. This requires HTTPS, Supabase Auth, and the simulator disabled. The API can still use your own PostgreSQL server. Complete the [public launch gates](../release-readiness.md#public-launch-gates) before enabling public traffic.

### Public marketing and downloads

The public pitch is available at `/` and `/home`, with `/` as the canonical URL. The buyer app starts at `/workspace` and the operator dashboard remains at `/admin` for authorized accounts. The presentation at `/home#demo` uses clearly labeled illustrative reports, so it works without signing in or enabling the API simulator.

Set `PROOFSCAN_SITE_URL` to the final public HTTPS origin **before building the web app**. That origin supplies the canonical URL, absolute social image URL, structured data and sitemap. Local or unconfigured builds are excluded from indexing. For `npm run build -w @proofscan/web`, export the values to the web build environment. Compose passes the same values as Docker build arguments. Rebuild the web app when changing them.

| Build variable | Public destination |
| --- | --- |
| `PROOFSCAN_WINDOWS_DOWNLOAD_URL` | Windows installer. The built-in PowerShell collector is linked when the variable is absent. |
| `PROOFSCAN_MACOS_DOWNLOAD_URL` | Signed macOS installer. A setup guide is linked when the variable is absent. |
| `PROOFSCAN_ANDROID_DOWNLOAD_URL` | Public Play Store listing or Android installer. A setup guide is linked when the variable is absent. |
| `PROOFSCAN_IOS_DOWNLOAD_URL` | Public App Store or TestFlight link. A setup guide is linked when the variable is absent. |

Use public HTTPS destinations without private credentials or expiring tokens in those variables. After release, verify that each download reaches the intended package and that `/robots.txt`, `/sitemap.xml`, `/manifest.webmanifest` and the share image respond from the final domain. [Google canonical URL guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) · [Next.js metadata and Open Graph](https://nextjs.org/docs/app/getting-started/metadata-and-og-images)

Use `/health/live` for process liveness and `/health` for database readiness. Readiness requires the Alembic head packaged with that API version and `SELECT` access to `alembic_version` for the API role. Ingress should only route to ready instances. Use a planned cutover for schema changes because versions with different Alembic heads cannot both report ready against the same database. The application allows five pooled connections and five overflow connections per process by default. Budget `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW` across all API replicas and Celery processes against the server connection limit. Plan a migration window for index creation on large tables.

The expiry worker commits batches of up to 250 verification rows. Evidence retention batches remove bytes in a separate transaction from serving requests, preserving photo digests. Keep a single scheduler and monitor worker latency so pending jobs drain. Keep deployment-level connection and request rate limits in place around public traffic.

For Supabase Auth, supply `SUPABASE_URL` for the project and its publishable browser-safe key as `SUPABASE_PUBLISHABLE_KEY`. Use asymmetric JWT signing and set `AUTH_MODE=supabase`. To exercise hosted PostgreSQL, also supply a restricted `DATABASE_URL`. These credentials are available from Supabase Project Settings. Storage provisioning and live integrations require separate validation.

Moonshot inference, hosted storage, store attestation and telemetry services require their own configuration at their integration milestones.
