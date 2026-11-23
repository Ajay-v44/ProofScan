import asyncio
import os
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from proofscan.config import settings
from proofscan.db import Base, Challenge, now, session
from proofscan.main import app
from proofscan.services import signer, token_hash
from proofscan.signing import encode

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL")
PASSWORD = "integration-test-password"


@pytest.fixture
async def clients(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("WEB_ORIGIN", "http://testserver")
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("LOCAL_AUTH_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("REPORT_KEY_ID", "test")
    monkeypatch.setenv("REPORT_PRIVATE_KEY", encode(secrets.token_bytes(32)))
    monkeypatch.setenv("ENABLE_SIMULATOR", "true")
    settings.cache_clear()
    signer.cache_clear()

    schema = "proofscan_test_" + uuid4().hex
    ddl = create_async_engine(url, hide_parameters=True)
    engine = create_async_engine(
        url, hide_parameters=True, connect_args={"server_settings": {"search_path": schema}}
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def test_session():
        async with factory.begin() as db:
            yield db

    try:
        async with ddl.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        app.dependency_overrides[session] = test_session

        def client():
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            )

        yield client, factory
    finally:
        app.dependency_overrides.pop(session, None)
        await engine.dispose()
        async with ddl.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await ddl.dispose()
        signer.cache_clear()
        settings.cache_clear()


async def register(client):
    data = {"email": f"unit-{uuid4()}@example.test", "password": PASSWORD}
    response = await client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 201, response.text
    return response.json()["user_id"], data


async def new_request(buyer):
    response = await buyer.post(
        "/api/v1/verifications",
        json={
            "label": "Sample listing",
            "claims": {"memory_gib": 16, "storage_gb": 1000, "battery_percent": 85},
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    return result["id"], result["guest_url"].split("#")[1]


async def open_guest(guest, verification, token):
    path = f"/api/v1/guest/{verification}"
    response = await guest.post(path + "/exchange", json={"token": token})
    assert response.status_code == 200, response.text
    return path


async def consent_and_scan(guest, path):
    response = await guest.post(
        path + "/consent", json={"policy_version": "2026-11-23", "accepted": True}
    )
    assert response.status_code == 200, response.text
    response = await guest.post(path + "/scan", json={"platform": "simulator"})
    assert response.status_code == 200, response.text
    ticket = response.json()
    return {
        "scan_id": ticket["scan_id"],
        "challenge": ticket["challenge"],
        "platform": "simulator",
        "fixture": "misrepresented",
    }


async def test_consent_replay_privacy_and_admin_invalidation(clients):
    client, _ = clients
    async with client() as buyer, client() as guest, client() as other, client() as admin:
        _, login = await register(buyer)
        admin_id, _ = await register(admin)
        await register(other)
        settings().admin_subjects.add(UUID(admin_id))
        assert (await buyer.post("/api/v1/auth/logout", json={})).status_code == 204
        assert (await buyer.get("/api/v1/verifications")).status_code == 401
        assert (await buyer.post("/api/v1/auth/login", json=login)).status_code == 200
        verification, token = await new_request(buyer)
        path = await open_guest(guest, verification, token)
        assert (await guest.get("/api/v1/verifications")).status_code == 401
        assert (await guest.post(path + "/scan", json={"platform": "simulator"})).status_code == 409
        assert (
            await guest.post(path + "/consent", json={"policy_version": "2026-11-23", "accepted": False})
        ).status_code == 422
        assert (await guest.post(path + "/decision", json={"decision": "share"})).status_code == 409
        evidence = await consent_and_scan(guest, path)
        responses = await asyncio.gather(
            guest.post(path + "/submit", json=evidence),
            guest.post(path + "/submit", json=evidence),
        )
        assert sorted(item.status_code for item in responses) == [200, 409]
        preview = next(item for item in responses if item.is_success).json()["preview"]
        assert preview["assurance"] == "SIMULATED"
        assert {finding["status"] for finding in preview["findings"]} == {"MISMATCH"}
        report_id = preview["report_id"]
        report_path = f"/api/v1/verifications/{verification}/report"
        verify_path = f"/api/v1/reports/{report_id}/verify"
        assert (await buyer.get(report_path)).status_code == 404
        assert (await other.get(verify_path)).status_code == 404
        assert (await guest.post(path + "/decision", json={"decision": "share"})).status_code == 200
        assert (await guest.post(path + "/decision", json={"decision": "share"})).status_code == 200
        assert (await other.get(report_path)).status_code == 404
        assert (await buyer.get(report_path)).json()["valid"]
        public = (await other.get(verify_path)).json()
        assert public["valid"] and "payload" not in public
        invalidate_path = f"/api/v1/admin/reports/{report_id}/invalidate"
        reason = {"reason": "Confirmed test invalidation"}
        assert (await buyer.post(invalidate_path, json=reason)).status_code == 403
        assert (await buyer.get("/api/v1/admin/metrics")).status_code == 403
        metrics = await admin.get("/api/v1/admin/metrics")
        assert metrics.is_success, metrics.text
        assert metrics.json()["agent_runs"] == 1
        assert metrics.json()["listing_mismatch_scans"] == 0
        assert (await admin.post(invalidate_path, json=reason)).status_code == 204
        invalid = (await other.get(verify_path)).json()
        assert invalid["invalidated"] and not invalid["valid"]
        assert invalid["digest"] == public["digest"]


async def test_expiry_cross_session_and_decline(clients):
    client, factory = clients
    async with client() as buyer, client() as guest_a, client() as guest_b:
        await register(buyer)
        a, token_a = await new_request(buyer)
        b, token_b = await new_request(buyer)
        forbidden = await guest_b.post(f"/api/v1/guest/{b}/exchange", json={"token": token_a})
        assert forbidden.status_code == 404
        path_a = await open_guest(guest_a, a, token_a)
        path_b = await open_guest(guest_b, b, token_b)
        evidence_a = await consent_and_scan(guest_a, path_a)
        evidence_b = await consent_and_scan(guest_b, path_b)
        assert (await guest_b.post(path_b + "/submit", json=evidence_a)).status_code == 404
        assert (
            await guest_b.post(
                path_b + "/submit",
                json={
                    **evidence_b,
                    "challenge": evidence_a["challenge"],
                },
            )
        ).status_code == 409
        async with factory.begin() as db:
            await db.execute(
                update(Challenge)
                .where(Challenge.token_hash == token_hash(evidence_a["challenge"]))
                .values(expires_at=now() - timedelta(seconds=1))
            )
        assert (await guest_a.post(path_a + "/submit", json=evidence_a)).status_code == 409
        assert (await guest_b.post(path_b + "/submit", json=evidence_b)).status_code == 200
        assert (
            await guest_b.post(path_b + "/decision", json={"decision": "decline"})
        ).status_code == 200
        assert (await guest_b.get(path_b)).json()["preview"] is None
        assert (await buyer.get(f"/api/v1/verifications/{b}/report")).status_code == 404


async def test_handoff_owner_scope_and_signed_comparison(clients):
    client, _ = clients
    async with client() as owner, client() as other, client() as receiver:
        await register(owner)
        await register(other)
        result = await owner.post("/api/v1/handoffs", json={"label": "Loaner", "mode": "simulator"})
        assert result.status_code == 201, result.text
        path = "/api/v1/handoffs/" + result.json()["id"]
        assert (await other.get(path)).status_code == 404
        assert (await owner.post(path + "/activate", json={})).status_code == 409
        assert (await owner.post(path + "/start", json={})).json()["handoff"][
            "status"
        ] == "BASELINE_SCANNING"
        assert (await owner.post(path + "/record", json={"condition": "clean"})).json()[
            "status"
        ] == "BASELINE_CREATED"
        invite = await owner.post(path + "/invite", json={})
        assert invite.is_success
        token = invite.json()["url"].split("#")[1]
        assert (await receiver.post(path + "/accept", json={"token": token})).is_success
        assert (await owner.get(path)).json()["receiver_accepted"]
        assert (await owner.post(path + "/activate", json={})).json()["status"] == "ACTIVE_HANDOFF"
        assert (await owner.post(path + "/start", json={})).json()["handoff"][
            "status"
        ] == "RETURN_SCANNING"
        assert (await owner.post(path + "/record", json={"condition": "clean"})).json()[
            "status"
        ] == "REPORT_READY"
        payload = (await owner.get(path + "/report")).json()
        assert payload["valid"] and payload["payload"]["return"]["note"] == "New scratch"
        assert (await other.get(path + "/report")).status_code == 404
        verified = (
            await receiver.get(f"/api/v1/reports/{payload['payload']['report_id']}/verify")
        ).json()
        assert verified["valid"] and "payload" not in verified
        assert (await owner.get("/api/v1/notifications")).json()[0]["event"] == "HANDOFF_REPORT_READY"
        assert (await owner.post(path + "/close", json={})).json()["status"] == "CLOSED"


async def test_native_guest_header_and_platform_limitations(clients):
    client, _ = clients
    async with client() as buyer, client() as mobile:
        await register(buyer)
        verification, token = await new_request(buyer)
        path = f"/api/v1/guest/{verification}"
        issued = await mobile.post(path + "/exchange", json={"token": token})
        assert issued.is_success
        mobile.cookies.clear()
        mobile.headers["X-Guest-Token"] = token
        assert (await mobile.get(path)).is_success
        assert (await mobile.get("/api/v1/verifications")).status_code == 401
        await mobile.post(path + "/consent", json={"policy_version": "2026-11-23", "accepted": True})
        ticket = (await mobile.post(path + "/scan", json={"platform": "ios"})).json()
        result = await mobile.post(
            path + "/submit",
            json={
                "scan_id": ticket["scan_id"],
                "challenge": ticket["challenge"],
                "platform": "ios",
                "hardware": {"manufacturer": "Apple", "model": "Fixture phone", "memory_gib": 8},
            },
        )
        assert result.is_success, result.text
        report = result.json()["preview"]
        assert report["platform"] == "ios"
        assert all(item["test"] != "request_battery_reading" for item in report["inspection_requests"])
        assert (await mobile.post(path + "/decision", json={"decision": "decline"})).is_success
