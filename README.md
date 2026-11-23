# ProofScan

**Verify what it is. Verify what changed.**

ProofScan gives a buyer a private seller link for a used-device listing. The seller consents, downloads a one-time scan ticket, collects Windows hardware readings and reviews them before sharing. The buyer receives a report signed by ProofScan and can check its integrity publicly using its ID. An explicitly labeled simulator exercises the same consent and sharing flow.

For handoffs, the owner records a baseline, optionally asks the receiver to acknowledge the handoff, and generates a signed comparison after recording the return. Generic items use condition records and photos. Windows handoffs can also compare hardware readings.

## Start locally

1. Install Python 3.12, uv, Node.js 22.13 or later in the Node.js 22 line, and PostgreSQL. Copy `.env.example` to `.env` and follow the [development setup](docs/development/setup.md) to generate application secrets.
2. Run `uv sync --no-install-project` and `npm ci` from the root.
3. Run `uv run --no-sync alembic upgrade head`. Then start FastAPI and Next.js using the development commands in the setup guide.
4. Open [ProofScan](http://localhost:3000), create an account and start a verification. Use the guest link in a separate browser session.

| Path | Contents |
| --- | --- |
| `apps/api` | FastAPI routes, domain services, PostgreSQL models, migrations and tests |
| `apps/web` | Next.js buyer workspace, seller flow, signature check and operator tools |
| `apps/desktop` | Tauri source, desktop UI and Rust collectors for Windows and macOS |
| `apps/mobile` | Expo seller client for Android and iOS |
| `apps/worker` | Celery expiry and notification job |
| `packages/api-client` | Shared TypeScript API contracts and fetch client |
| `infrastructure/docker` | API, worker and web Dockerfiles |
| `docs` | Setup, architecture, API, design, security and deployment notes |

## Guides

- [Local setup and test commands](docs/development/setup.md)
- [Demo and platform status](docs/ux/flows.md)
- [Architecture](docs/architecture/overview.md) and [data model](docs/architecture/data-model.md)
- [API integration](docs/api/integration.md)
- [Threat model](docs/security/threat-model.md) and [report signing](docs/security/report-signing.md)
- [Deployment](docs/deployment/README.md)
- [Implementation status and remaining work](docs/status.md)
