import asyncio
import os
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

import cv2
import httpx
import numpy as np
import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from proofscan.config import settings
from proofscan.db import (
    Base,
    CaptureLink,
    Challenge,
    Evidence,
    Guest,
    ModelCall,
    Notification,
    User,
    Verification,
    now,
    session,
)
from proofscan.domain import Status
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
        async with factory() as db:
            yield db
            await db.commit()

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


@pytest.mark.asyncio
async def test_profile_updates_and_local_recovery_are_account_scoped(clients):
    factory, _ = clients
    async with factory() as buyer, factory() as other, factory() as reset:
        _, credentials = await register(buyer)
        await register(other)
        old_token = buyer.cookies["proofscan_session"]
        profile = await buyer.post("/api/v1/auth/profile", json={"display_name": " Workshop Buyer "})
        assert profile.json()["display_name"] == "Workshop Buyer"
        assert not (await other.get("/api/v1/auth/profile")).json()["display_name"]
        first = (await buyer.post("/api/v1/auth/recovery-code", json={})).json()["code"]
        code = (await buyer.post("/api/v1/auth/recovery-code", json={})).json()["code"]
        assert first != code
        body = {"email": credentials["email"], "password": "replacement-fixture-password", "code": first}
        assert (await reset.post("/api/v1/auth/reset", json=body)).status_code == 400
        body["code"] = code
        assert (await reset.post("/api/v1/auth/reset", json=body)).status_code == 204
        assert (await reset.post("/api/v1/auth/reset", json=body)).status_code == 400
        assert (
            await buyer.get("/api/v1/auth/session", headers={"Authorization": "Bearer " + old_token})
        ).status_code == 401
        assert (await reset.post("/api/v1/auth/login", json=credentials)).status_code == 401
        assert (
            await reset.post(
                "/api/v1/auth/login", json={"email": body["email"], "password": body["password"]}
            )
        ).is_success
        assert (await reset.get("/api/v1/auth/profile")).json()["display_name"] == "Workshop Buyer"


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


def exterior_image(seed: int) -> bytes:
    tiles = np.random.default_rng(seed).integers(45, 215, (24, 24), dtype=np.uint8)
    photo = cv2.resize(tiles, (384, 384), interpolation=cv2.INTER_NEAREST)
    ok, encoded = cv2.imencode(".jpg", photo)
    assert ok
    return encoded.tobytes()


async def upload_views(guest, path, ticket, seeds=(1, 2)):
    for angle, seed in zip(("front", "back"), seeds, strict=True):
        result = await guest.post(
            path + f"/photos?angle={angle}",
            content=exterior_image(seed),
            headers={"Content-Type": "image/jpeg", "X-Scan-Challenge": ticket["challenge"]},
        )
        assert result.status_code == 201, result.text


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
        await upload_views(mobile, path, ticket)
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


async def test_guest_reads_do_not_wait_for_writes(clients):
    client, factory = clients
    async with client() as buyer, client() as guest, client() as stranger:
        await register(buyer)
        verification, token = await new_request(buyer)
        path = await open_guest(guest, verification, token)
        async with factory.begin() as db:
            await db.scalar(
                select(Verification).where(Verification.id == UUID(verification)).with_for_update()
            )
            result, denied = await asyncio.wait_for(
                asyncio.gather(
                    guest.get(path),
                    stranger.post(path + "/exchange", json={"token": "x" * 43}),
                ),
                timeout=2,
            )
            assert result.is_success
            assert denied.status_code == 404
        async with factory.begin() as db:
            await db.execute(
                update(Guest).where(Guest.verification_id == UUID(verification)).values(revoked_at=now())
            )
        assert (await guest.get(path)).status_code == 404


async def test_scan_ticket_refresh_preserves_photos_until_platform_changes(clients, monkeypatch):
    from apps.worker import tasks

    client, factory = clients
    image = np.where(np.indices((256, 256)).sum(axis=0) // 20 % 2, 80, 190).astype(np.uint8)
    ok, jpeg = cv2.imencode(".jpg", image)
    assert ok
    async with client() as buyer, client() as guest:
        await register(buyer)
        verification, token = await new_request(buyer)
        path = await open_guest(guest, verification, token)
        assert (
            await guest.post(path + "/consent", json={"policy_version": "2026-11-23", "accepted": True})
        ).is_success
        initial = (await guest.post(path + "/scan", json={"platform": "ios"})).json()
        content = jpeg.tobytes()
        photo = await guest.post(
            path + "/photos?angle=front",
            content=content,
            headers={"X-Scan-Challenge": initial["challenge"], "Content-Type": "image/jpeg"},
        )
        assert photo.is_success, photo.text
        renewed = (await guest.post(path + "/scan", json={"platform": "ios"})).json()
        assert renewed["challenge"] != initial["challenge"]
        assert renewed["scan_id"] == initial["scan_id"]
        assert (await guest.get(path)).json()["photos"] == [photo.json()]
        expired_upload = await guest.post(
            path + "/photos?angle=back",
            content=content,
            headers={"X-Scan-Challenge": initial["challenge"], "Content-Type": "image/jpeg"},
        )
        assert expired_upload.status_code == 422

        async with factory.begin() as db:
            await db.execute(update(Evidence).values(expires_at=now() - timedelta(hours=1)))
        monkeypatch.setattr(tasks, "database", lambda: factory.kw["bind"])
        assert await tasks.purge_evidence() == 1
        assert await tasks.purge_evidence() == 0
        async with factory.begin() as db:
            assert (await db.execute(select(Evidence.jpeg, Evidence.digest))).one() == (
                None,
                photo.json()["digest"],
            )
        replacement = await guest.post(
            path + "/photos?angle=front",
            content=content,
            headers={"X-Scan-Challenge": renewed["challenge"], "Content-Type": "image/jpeg"},
        )
        assert replacement.is_success
        assert (await guest.post(path + "/scan", json={"platform": "android"})).is_success
        assert (await guest.get(path)).json()["photos"] == []


async def test_handoff_lists_use_one_query_for_the_page(clients):
    client, factory = clients
    statements: list[str] = []

    def record(_conn, _cursor, statement, _params, _context, _executemany):
        statements.append(statement)

    async with client() as owner, client() as other:
        await register(owner)
        await register(other)
        for label in ("A", "B", "C"):
            assert (
                await owner.post("/api/v1/handoffs", json={"label": label, "mode": "visual"})
            ).is_success
        assert (
            await other.post("/api/v1/handoffs", json={"label": "Private", "mode": "visual"})
        ).is_success
        engine = factory.kw["bind"].sync_engine
        event.listen(engine, "before_cursor_execute", record)
        try:
            listed = await owner.get("/api/v1/handoffs")
        finally:
            event.remove(engine, "before_cursor_execute", record)
        assert listed.is_success
        assert {row["label"] for row in listed.json()} == {"A", "B", "C"}
        assert len(statements) == 2  # Owner lookup and the complete page.


async def test_worker_drains_multiple_batches_without_duplicate_events(clients, monkeypatch):
    from apps.worker import tasks

    _, factory = clients
    async with factory.begin() as db:
        user = User()
        db.add(user)
        await db.flush()
        db.add_all(
            [
                Verification(
                    owner_id=user.id,
                    label="Expired",
                    status=Status.LINK_CREATED,
                    expires_at=now() - timedelta(minutes=1),
                )
                for _ in range(5)
            ]
        )
    monkeypatch.setattr(tasks, "database", lambda: factory.kw["bind"])
    monkeypatch.setattr(tasks, "BATCH_SIZE", 2)
    assert await tasks.expire_due() == 5
    assert await tasks.expire_due() == 0
    async with factory.begin() as db:
        assert (await db.scalars(select(Verification.status))).all() == [Status.EXPIRED] * 5
        assert (await db.scalars(select(Notification.event))).all() == [Status.EXPIRED] * 5


async def test_listing_provider_runs_after_quota_transaction_is_committed(clients, monkeypatch):
    from proofscan import suggestions
    from proofscan.providers import Suggestion
    from proofscan.schemas import Claims

    client, factory = clients
    started = asyncio.Event()
    release = asyncio.Event()

    class Provider:
        async def suggest(self, listing):
            assert "16 GiB" in listing
            assert not any(
                value in listing for value in ("seller@example.test", "555", "private.example")
            )
            started.set()
            await release.wait()
            return Suggestion(Claims(memory_gib=16), 32, 8)

    monkeypatch.setattr(suggestions, "model_provider", Provider)
    async with client() as buyer:
        owner, _ = await register(buyer)
        pending = asyncio.create_task(
            buyer.post(
                "/api/v1/claims/suggest",
                json={
                    "listing": "16 GiB advertised memory. Private contact seller@example.test or +1 (555) 012-4455 at https://private.example/path",
                },
            )
        )
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            async with factory.begin() as db:
                assert await db.scalar(
                    select(User.id).where(User.id == UUID(owner)).with_for_update(nowait=True)
                ) == UUID(owner)
                call = await db.scalar(select(ModelCall))
                assert call is not None and not call.accepted
        finally:
            release.set()
            result = await pending
        assert result.json()["memory_gib"] == 16
        async with factory.begin() as db:
            call = await db.scalar(select(ModelCall))
            assert call is not None and call.accepted and call.input_tokens == 32


async def test_verification_cursor_handles_ties_and_new_inserts(clients):
    client, factory = clients
    async with client() as owner, client() as other:
        owner_id, _ = await register(owner)
        foreign, _ = await register(other)
        timestamp = now()
        async with factory.begin() as db:
            items = [
                Verification(
                    owner_id=UUID(owner_id),
                    label=f"Record {index}",
                    status=Status.LINK_CREATED,
                    expires_at=timestamp + timedelta(days=1),
                    created_at=timestamp,
                )
                for index in range(35)
            ]
            private = Verification(
                owner_id=UUID(foreign),
                label="Private",
                status=Status.LINK_CREATED,
                expires_at=timestamp + timedelta(days=1),
            )
            db.add_all([*items, private])
        first = (await owner.get("/api/v1/verifications")).json()
        assert len(first) == 30
        await new_request(owner)
        second = (await owner.get("/api/v1/verifications", params={"before": first[-1]["id"]})).json()
        assert len(second) == 5
        assert [row["id"] for row in first + second] == sorted(
            (str(item.id) for item in items), reverse=True
        )
        assert (
            await owner.get("/api/v1/verifications", params={"before": str(private.id)})
        ).json() == []


async def test_advisor_scopes_retrieval_and_requires_model_permission(clients, monkeypatch):
    from proofscan.agent import recommendations

    client, _ = clients
    async with client() as owner, client() as other:
        await register(owner)
        await register(other)
        specification = {
            "category": "phone",
            "notes": "Battery life and a bright screen for outdoor use.",
            "price": 17000,
            "currency": "INR",
        }
        ours = await owner.post("/api/v1/agent/catalog", json={**specification, "title": "Owner phone"})
        foreign = await other.post(
            "/api/v1/agent/catalog", json={**specification, "title": "Private phone"}
        )
        assert ours.status_code == foreign.status_code == 201
        assert (
            await owner.post(
                "/api/v1/agent/catalog",
                json={
                    **specification,
                    "title": "Over budget",
                    "price": 40000,
                },
            )
        ).is_success
        question = {"question": "Which phone has good battery life?", "budget": 20000, "currency": "INR"}
        calls: list = []

        async def model(_prompt, facts, _shape, _trace, *, approved):
            assert approved
            calls.append(facts)
            actions = facts["allowed_actions"]
            assert "search_catalog" not in actions
            assert "message" not in facts["action_schema"]["properties"]
            if "compare_candidates" in actions:
                return recommendations.Action(action="compare_candidates", candidates=[1])
            return recommendations.Action(action="recommend", candidates=[1])

        monkeypatch.setattr(recommendations, "decide", model)
        path = "/api/v1/agent/ask"
        fallback = await owner.post(path, json=question)
        assert fallback.is_success, fallback.text
        assert fallback.json()["model_used"] is False and not calls
        result = await owner.post(path, json={**question, "allow_model": True})
        assert result.is_success, result.text
        assert result.json()["tools"] == ["search_catalog", "compare_candidates"]
        assert result.json()["model_used"]
        assert [item["title"] for item in result.json()["sources"]] == ["Owner phone"]
        assert len(calls) == 2 and "Private phone" not in str(calls)
        assert (await owner.delete("/api/v1/agent/catalog/" + foreign.json()["id"])).status_code == 404
        assert (await owner.delete("/api/v1/agent/catalog/" + ours.json()["id"])).status_code == 204
        empty = await owner.post(path, json=question)
        assert empty.json()["status"] == "no_evidence" and not empty.json()["sources"]


async def test_guided_scan_requires_approval_and_chooses_fallback(clients, monkeypatch):
    from proofscan.agent import device

    async def choose(_prompt, facts, *_, approved):
        assert approved
        return device.ToolChoice(tool=facts["available"][0])

    monkeypatch.setattr(device, "decide", choose)
    client, _ = clients
    async with client() as buyer, client() as guest, client() as other:
        await register(buyer)
        record, token = await new_request(buyer)
        path = await open_guest(guest, record, token)
        target = path + "/agent/plan"
        assert (await guest.post(target, json={"platform": "ios"})).status_code == 409
        assert (
            await guest.post(path + "/consent", json={"accepted": True, "policy_version": "2026-11-23"})
        ).is_success
        assert (await guest.post(path + "/scan", json={"platform": "ios"})).is_success
        plan = (await guest.post(target, json={"platform": "ios"})).json()
        assert plan["status"] == "awaiting_approval" and plan["next_tool"] is None
        advance = target + "/" + plan["id"]
        approval = {"revision": plan["revision"], "action": "approve"}
        assert (await other.post(advance, json=approval)).status_code == 404
        unapproved = {
            "revision": plan["revision"],
            "action": "observe",
            "tool": "model_name",
            "outcome": "ok",
        }
        assert (await guest.post(advance, json=unapproved)).status_code == 409
        first = (await guest.post(advance, json=approval)).json()
        assert first["next_tool"] == "model_name"
        failed = {
            "revision": first["revision"],
            "action": "observe",
            "tool": "model_name",
            "outcome": "error",
        }
        fallback = (await guest.post(advance, json=failed)).json()
        assert fallback["next_tool"] == "model_identifier"
        assert (await guest.post(advance, json=failed)).status_code == 409
        memory = (
            await guest.post(
                advance,
                json={
                    "revision": fallback["revision"],
                    "action": "observe",
                    "tool": "model_identifier",
                    "outcome": "ok",
                },
            )
        ).json()
        assert memory["next_tool"] == "memory_total"
        done = (
            await guest.post(
                advance,
                json={
                    "revision": memory["revision"],
                    "action": "observe",
                    "tool": "memory_total",
                    "outcome": "ok",
                },
            )
        ).json()
        assert done["status"] == "complete" and done["next_tool"] is None


@pytest.mark.skipif(
    os.environ.get("TEST_AGENT_VECTOR") != "1", reason="Install pgvector to test semantic retrieval"
)
async def test_agent_pgvector_filters_before_cosine_similarity(clients, monkeypatch):
    from proofscan.agent import catalog

    client, factory = clients
    async with factory.begin() as db:
        await db.execute(
            text("""
            CREATE TABLE agent_catalog_vectors (
                item_id uuid PRIMARY KEY REFERENCES agent_catalog_items (id) ON DELETE CASCADE,
                embedding public.vector(384) NOT NULL,
                model text NOT NULL
            )
        """)
        )
    settings().agent_vector_enabled = True

    async def embedding(value, *, query):
        positive = query or value.startswith("Similar")
        return "[" + ",".join(map(str, [int(positive), int(not positive)] + [0] * 382)) + "]"

    monkeypatch.setattr(catalog, "vector_for", embedding)
    async with client() as owner, client() as other:
        await register(owner)
        await register(other)
        document = {"category": "phone", "notes": "Public manufacturer specification sheet."}
        for account, title in (
            (owner, "Similar owned"),
            (owner, "Unrelated owned"),
            (other, "Similar foreign"),
        ):
            assert (
                await account.post("/api/v1/agent/catalog", json={**document, "title": title})
            ).is_success
        result = await owner.post("/api/v1/agent/ask", json={"question": "Which one fits?"})
        assert result.is_success, result.text
        assert result.json()["retrieval"] == "pgvector"
        assert [item["title"] for item in result.json()["sources"]] == ["Similar owned"]

        async def missing_model(*_args, **_kwargs):
            raise catalog.VectorUnavailable("fixture embedding unavailable")

        monkeypatch.setattr(catalog, "vector_for", missing_model)
        assert (
            await owner.post("/api/v1/agent/catalog", json={**document, "title": "Deferred vector"})
        ).is_success
        fallback = await owner.post("/api/v1/agent/ask", json={"question": "Unrelated owned"})
        assert fallback.is_success, fallback.text
        assert fallback.json()["retrieval"] == "lexical"
        assert [item["title"] for item in fallback.json()["sources"]] == ["Unrelated owned"]


async def test_readiness_requires_the_release_migration_version(clients, monkeypatch):
    from proofscan import main

    client, factory = clients
    monkeypatch.setattr(main, "database", lambda: factory.kw["bind"])
    async with client() as probe:
        assert (await probe.get("/health/live")).is_success
        assert (await probe.get("/health")).status_code == 503
        async with factory.begin() as db:
            await db.execute(text("CREATE TABLE alembic_version (version_num text PRIMARY KEY)"))
            await db.execute(text("INSERT INTO alembic_version VALUES ('old')"))
        assert (await probe.get("/health")).status_code == 503
        async with factory.begin() as db:
            await db.execute(text("DELETE FROM alembic_version"))
            for head in main.migration_heads():
                await db.execute(text("INSERT INTO alembic_version VALUES (:head)"), {"head": head})
        assert (await probe.get("/health")).is_success


async def test_camera_link_has_photo_only_access_and_expires(clients):
    client, factory = clients
    async with client() as buyer, client() as seller, client() as camera:
        await register(buyer)
        verification, token = await new_request(buyer)
        seller_path = await open_guest(seller, verification, token)
        camera_path = f"/api/v1/capture/{verification}"
        assert (await seller.post(seller_path + "/photo-link", json={})).status_code == 409
        await seller.post(
            seller_path + "/consent", json={"policy_version": "2026-11-23", "accepted": True}
        )
        ticket = (await seller.post(seller_path + "/scan", json={"platform": "ios"})).json()

        async def camera_header():
            response = await seller.post(seller_path + "/photo-link", json={})
            assert response.status_code == 201, response.text
            return {"X-Photo-Token": response.json()["url"].split("#")[1]}

        headers = await camera_header()
        assert (await camera.get(camera_path, headers=headers)).json() == {"views": []}
        assert (
            await camera.get(seller_path, headers={"X-Guest-Token": headers["X-Photo-Token"]})
        ).status_code == 404
        assert (
            await camera.post(seller_path + "/decision", json={"decision": "share"}, headers=headers)
        ).status_code == 404
        assert (await camera.get(f"/api/v1/capture/{uuid4()}", headers=headers)).status_code == 404
        first = exterior_image(1)
        assert (
            await camera.post(camera_path + "/photos?angle=front", content=first, headers=headers)
        ).is_success
        assert (
            await camera.post(camera_path + "/photos?angle=back", content=first, headers=headers)
        ).status_code == 422
        async with factory.begin() as db:
            await db.execute(update(CaptureLink).values(expires_at=now() - timedelta(seconds=1)))
        assert (await camera.get(camera_path, headers=headers)).status_code == 404
        fresh = await camera_header()
        assert (await camera.get(camera_path, headers=fresh)).json() == {"views": ["front"]}
        assert (
            await camera.post(
                camera_path + "/photos?angle=back", content=exterior_image(2), headers=fresh
            )
        ).is_success
        assert (
            await seller.post(
                seller_path + "/submit",
                json={
                    "platform": "ios",
                    "scan_id": ticket["scan_id"],
                    "challenge": ticket["challenge"],
                    "hardware": {"manufacturer": "Example", "model": "Phone", "memory_gib": 8},
                },
            )
        ).is_success
        assert (await camera.get(camera_path, headers=fresh)).status_code == 404


async def test_purchase_views_pickup_and_private_report_retrieval(clients, monkeypatch):
    from proofscan.agent import recommendations

    client, _ = clients
    async with client() as buyer, client() as seller, client() as other, client() as admin:
        await register(buyer)
        await register(other)
        administrator, _ = await register(admin)
        settings().admin_subjects.add(UUID(administrator))
        verification, token = await new_request(buyer)
        path = await open_guest(seller, verification, token)

        async def request_scan(guest, base, model):
            assert (
                await guest.post(
                    base + "/consent", json={"policy_version": "2026-11-23", "accepted": True}
                )
            ).is_success
            ticket = (await guest.post(base + "/scan", json={"platform": "ios"})).json()
            return ticket, {
                "scan_id": ticket["scan_id"],
                "challenge": ticket["challenge"],
                "platform": "ios",
                "hardware": {"manufacturer": "Example", "model": model, "memory_gib": 8},
            }

        ticket, reading = await request_scan(seller, path, "Verified phone seller@example.test")
        assert (await seller.post(path + "/submit", json=reading)).status_code == 422
        await upload_views(seller, path, ticket)
        preview = (await seller.post(path + "/submit", json=reading)).json()["preview"]
        question = {
            "question": "Which phone has more memory? My contact is buyer@example.test",
            "reports_only": True,
            "category": "phone",
            "allow_model": True,
        }
        messages = []

        async def model(_prompt, facts, _shape, _trace, *, approved):
            assert approved
            messages.append(facts)
            return recommendations.Action(
                action="search_catalog" if "search_catalog" in facts["allowed_actions"] else "recommend",
                candidates=[1],
            )

        monkeypatch.setattr(recommendations, "decide", model)
        assert (await buyer.post("/api/v1/agent/ask", json=question)).json()["sources"] == []
        shared = await seller.post(path + "/decision", json={"decision": "share"})
        assert shared.is_success, shared.text
        result = await buyer.post("/api/v1/agent/ask", json=question)
        assert result.is_success, result.text
        source = result.json()["sources"][0]
        assert source["verification_id"] == verification
        assert "@" not in source["title"]
        assert "example.test" not in str(messages) and verification not in str(messages)
        assert (await other.post("/api/v1/agent/ask", json=question)).json()["sources"] == []
        alternative, token = await new_request(buyer)
        alternative_path = await open_guest(seller, alternative, token)
        ticket, reading = await request_scan(seller, alternative_path, "16 GiB phone")
        reading["hardware"]["memory_gib"] = 16
        await upload_views(seller, alternative_path, ticket)
        assert (await seller.post(alternative_path + "/submit", json=reading)).is_success
        assert (await seller.post(alternative_path + "/decision", json={"decision": "share"})).is_success
        ranked = await buyer.post("/api/v1/agent/ask", json={**question, "allow_model": False})
        assert [item["verification_id"] for item in ranked.json()["sources"]] == [
            alternative,
            verification,
        ]
        assert "ranks highest for recorded memory" in ranked.json()["message"]
        free_text = {"message": "Which of my devices has the most memory?", "allow_model": True}
        scoped = await buyer.post("/api/v1/agent/chat", json=free_text)
        assert scoped.is_success, scoped.text
        assert [item["href"] for item in scoped.json()["sources"]] == [
            f"/reports/{alternative}",
            f"/reports/{verification}",
        ]
        assert "highest recorded memory" in scoped.json()["message"]
        assert "example.test" not in scoped.text
        followup = await buyer.post(
            "/api/v1/agent/chat",
            json={"message": "What about the least?", "history": [free_text["message"]]},
        )
        assert followup.json()["sources"][0]["href"] == f"/reports/{verification}"
        assert "lowest recorded memory" in followup.json()["message"]
        unauthorized = await other.post("/api/v1/agent/chat", json=free_text)
        assert unauthorized.json()["status"] == "needs_input"
        assert not unauthorized.json()["sources"]
        route = f"/api/v1/verifications/{verification}/recheck"
        assert (await other.post(route, json={})).status_code == 404
        pickup = await buyer.post(route, json={})
        assert pickup.status_code == 201, pickup.text
        pickup_record = pickup.json()
        next_path = await open_guest(
            seller, pickup_record["id"], pickup_record["guest_url"].split("#")[1]
        )
        ticket, reading = await request_scan(seller, next_path, "Different phone")
        await upload_views(seller, next_path, ticket)
        response = await seller.post(next_path + "/submit", json=reading)
        assert response.is_success, response.text
        comparison = response.json()["preview"]["pickup"]
        assert comparison["baseline_report_id"] == preview["report_id"]
        assert "Model" in comparison["changed_hardware"]
        assert {item["status"] for item in comparison["visuals"]} == {"reused"}
        assert (await buyer.get("/api/v1/admin/agent-usage")).status_code == 403
        usage = (await admin.get("/api/v1/admin/agent-usage")).json()["workflows"]
        assert {row["kind"] for row in usage} == {"buyer_chat", "purchase_visual"}
        assert all("owner_id" not in row and "question" not in row for row in usage)
        assert (
            await admin.post(
                "/api/v1/admin/reports/" + preview["report_id"] + "/invalidate",
                json={"reason": "Fixture baseline revoked"},
            )
        ).status_code == 204
        remaining = (await buyer.post("/api/v1/agent/ask", json=question)).json()["sources"]
        assert [item["verification_id"] for item in remaining] == [alternative]
        current = (await buyer.post("/api/v1/agent/chat", json=free_text)).json()
        assert [item["href"] for item in current["sources"]] == [f"/reports/{alternative}"]
        assert (
            await seller.post(next_path + "/decision", json={"decision": "share"})
        ).status_code == 404

        pickup = await buyer.post(f"/api/v1/verifications/{alternative}/recheck", json={})
        pickup_record = pickup.json()
        next_path = await open_guest(
            seller, pickup_record["id"], pickup_record["guest_url"].split("#")[1]
        )
        ticket, reading = await request_scan(seller, next_path, "16 GiB phone")
        await upload_views(seller, next_path, ticket)
        assert (await seller.post(next_path + "/submit", json=reading)).is_success
        assert (await seller.post(next_path + "/decision", json={"decision": "share"})).is_success
        signed = await buyer.get(f"/api/v1/verifications/{pickup_record['id']}/report")
        assert signed.is_success and signed.json()["valid"] and signed.json()["baseline_valid"]
        assert signed.json()["payload"]["pickup"]["baseline_verification_id"] == alternative


async def test_handoff_guide_rejects_dark_views_and_compares_matching_angles(clients):
    client, _ = clients
    async with client() as owner:
        await register(owner)
        created = await owner.post("/api/v1/handoffs", json={"label": "Camera bag", "mode": "visual"})
        path = "/api/v1/handoffs/" + created.json()["id"]
        assert (await owner.post(path + "/start", json={})).json()["handoff"]["next_view"] == "front"
        _, dark = cv2.imencode(".jpg", np.zeros((384, 384), dtype=np.uint8))
        assert (
            await owner.post(path + "/photos?angle=front", content=dark.tobytes())
        ).status_code == 422
        photo = exterior_image(3)
        saved = await owner.post(path + "/photos?angle=front", content=photo)
        assert saved.is_success, saved.text
        assert saved.json()["next_view"] == "back"
        assert (await owner.post(path + "/record", json={"condition": "clean"})).is_success
        assert (await owner.post(path + "/activate", json={})).is_success
        assert (await owner.post(path + "/start", json={})).json()["handoff"]["next_view"] == "front"
        returned = await owner.post(path + "/photos?angle=front", content=photo)
        assert returned.json()["capture_feedback"]["status"] == "reused"
        assert returned.json()["next_view"] == "front"
        assert (await owner.get(path + "/photos/baseline?angle=front")).is_success
        assert (await owner.post(path + "/record", json={"condition": "clean"})).is_success
        report = (await owner.get(path + "/report")).json()
        assert report["valid"]
        assert report["payload"]["visual_findings"][0]["status"] == "reused"
