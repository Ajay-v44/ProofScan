import secrets
from datetime import timedelta
from uuid import uuid4

import pytest

from proofscan.db import Challenge, Guest, Scan, now
from proofscan.domain import InvalidTransition, Status, transition
from proofscan.services import validate_challenge
from proofscan.signing import Signer, encode


def test_transition_prevents_bypassing_seller_review():
    with pytest.raises(InvalidTransition):
        transition(Status.SCANNING, Status.SHARED)
    assert transition(Status.SELLER_REVIEW, Status.SHARED) == "SHARED"
    assert transition(Status.SHARED, Status.COMPLETED) == "COMPLETED"
    with pytest.raises(InvalidTransition):
        transition(Status.COMPLETED, Status.SELLER_REVIEW)


@pytest.mark.parametrize("reason", ["expired", "used", "wrong_scan", "wrong_guest", "wrong_platform"])
def test_challenges_reject_invalid_bindings(reason):
    guest = Guest(id=uuid4())
    scan = Scan(id=uuid4(), guest_id=guest.id, platform="windows")
    challenge = Challenge(scan_id=scan.id, expires_at=now() + timedelta(minutes=5))
    validate_challenge(challenge, scan, guest, "windows")
    platform = "windows"
    match reason:
        case "expired":
            challenge.expires_at = now() - timedelta(seconds=1)
        case "used":
            challenge.consumed_at = now()
        case "wrong_scan":
            challenge.scan_id = uuid4()
        case "wrong_guest":
            guest.id = uuid4()
        case "wrong_platform":
            platform = "simulator"
    with pytest.raises(ValueError):
        validate_challenge(challenge, scan, guest, platform)


def test_canonical_signing_tamper_and_rotation():
    original = Signer(encode(secrets.token_bytes(32)), "first", {})
    signature = original.sign({"z": 1, "a": "ü"})
    assert original.sign({"a": "ü", "z": 1}) == signature
    assert original.verify({"z": 1, "a": "ü"}, signature)
    assert not original.verify({"z": 2, "a": "ü"}, signature)
    rotated = Signer(
        encode(secrets.token_bytes(32)),
        "second",
        {"first": encode(original.public_keys["first"].public_bytes_raw())},
    )
    assert rotated.verify({"z": 1, "a": "ü"}, signature)
