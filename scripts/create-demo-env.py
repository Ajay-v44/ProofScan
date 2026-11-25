import os
from pathlib import Path
from secrets import token_hex, token_urlsafe


def main() -> None:
    if not Path("docker-compose.yml").is_file():
        raise SystemExit("Run this script from the ProofScan repository root.")

    destination = Path(".env.hackathon")
    password = token_hex(32)
    values = {
        "POSTGRES_USER": "proofscan",
        "POSTGRES_DB": "proofscan_demo",
        "POSTGRES_PASSWORD": password,
        "COMPOSE_DATABASE_URL": f"postgresql+asyncpg://proofscan:{password}@db:5432/proofscan_demo",
        "WEB_ORIGIN": "http://localhost:3000",
        "AUTH_MODE": "local",
        "LOCAL_AUTH_SECRET": token_urlsafe(48),
        "REPORT_KEY_ID": "hackathon-local",
        "REPORT_PRIVATE_KEY": token_urlsafe(32),
        "ENABLE_SIMULATOR": "true",
    }
    try:
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit(
            ".env.hackathon already exists. Reuse it to keep the demo database accessible."
        ) from None
    with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as config:
        config.writelines(f"{name}={value}\n" for name, value in values.items())
    print(f"Created {destination} with local-only demo configuration.")


if __name__ == "__main__":
    main()
