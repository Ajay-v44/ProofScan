# Run the ProofScan challenge demo

Use Docker with Compose v2 and a browser. The first build downloads the runtime images and dependencies. Run these commands from the root of the release source archive or checkout, using a fresh terminal.

```sh
docker run --rm --mount "type=bind,source=$PWD,target=/workspace" --workdir /workspace python:3.12-slim python scripts/create-demo-env.py
docker compose --project-name proofscan-hackathon --env-file .env.hackathon config --quiet
docker compose --project-name proofscan-hackathon --env-file .env.hackathon up --build -d
docker compose --project-name proofscan-hackathon --env-file .env.hackathon ps -a
```

The first command generates a private, ignored `.env.hackathon`. Keep it for later runs. If Python 3.12 is already installed on the host, `python scripts/create-demo-env.py` also generates the file. The demo uses local accounts, a fresh PostgreSQL volume, and loopback-only ports. It requires no hosted service keys. Allow the one-shot migration to finish and the API to become healthy. Open [ProofScan](http://localhost:3000/home#demo) or check [API health](http://127.0.0.1:8000/health). Ports `3000` and `8000` must be available.

## Judge walkthrough

1. Try the interactive purchase, pickup, and return examples on the [presentation](http://localhost:3000/home#demo).
2. Open the [workspace](http://localhost:3000/workspace), create a local account using a synthetic email, and start a verification with a device name and a claimed memory or storage value. Open the generated link in a private browser window, consent, and use the simulator. Review the evidence and choose **Share signed report**. Return to the buyer window and open the report. The simulated assurance is visible in the report.
3. Open **Buyer chat** and ask about ProofScan or compare shared eligible reports. The app excludes simulated reports from the private comparison catalog. The public report examples, ProofScan help, and local seller flow can all be exercised without a model key. See the [agent docs](../architecture/agent.md) for a real-device comparison, optional public price lookup, and pgvector setup.
4. Open **Handoffs** to create an asset, record its baseline, and record the return. Open the resulting signed comparison. The [workflow guide](../ux/flows.md) covers the receiver acknowledgment and pickup recheck paths.

If startup fails, inspect migration, API, and web logs.

```sh
docker compose --project-name proofscan-hackathon --env-file .env.hackathon logs --tail=60 migrate api web
```

Stop the demo and keep the local test data for the next run.

```sh
docker compose --project-name proofscan-hackathon --env-file .env.hackathon down
```

The [Codex evidence pack](codex-evidence-pack.md) links the lifecycle artifacts and test evidence. The [release review](../release-readiness.md) documents the separate public launch and native distribution gates.
