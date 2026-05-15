"""Electronic signature tests (21 CFR Part 11)"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from myeap.core.exceptions import AuthenticationError, ValidationError
from myeap.security.models import (
    SignatureMeaning,
    SignatureRecord,
    SignatureRequest,
    SignatureStatus,
    Role,
    User,
)
from myeap.security.signature import ElectronicSignature


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_SECRET = "test-secret-for-signatures-1234567890"


@pytest.fixture
def sig():
    return ElectronicSignature(secret_key=TEST_SECRET)


@pytest.fixture
def user1():
    return User(username="user1", full_name="User One", role=Role.ENGINEER, is_active=True)


@pytest.fixture
def user2():
    return User(username="user2", full_name="User Two", role=Role.ADMIN, is_active=True)


@pytest.fixture
def user3():
    return User(username="user3", full_name="User Three", role=Role.OPERATOR, is_active=True)


@pytest.fixture
def inactive_user():
    return User(username="inactive", full_name="Inactive User", role=Role.VIEWER, is_active=False)


@pytest.fixture
def locked_user():
    return User(
        username="locked",
        full_name="Locked User",
        role=Role.VIEWER,
        is_active=True,
        is_locked=True,
    )


def _valid_signature_token(username: str) -> str:
    """Create a valid signature token for the internal verification scheme.

    The ElectronicSignature._verify_identity method expects:
      expected = SHA256(f"{username}:{username}_sig")
      actual   = SHA256(f"{username}:{signature}")
    For these to match, signature must be f"{username}_sig".
    """
    return f"{username}_sig"


def _dummy_doc(recipe_id: str = "recipe-001") -> dict:
    return {
        "type": "recipe",
        "id": recipe_id,
        "title": "Recipe Approval",
        "description": "Sign to approve recipe",
    }


# ---------------------------------------------------------------------------
# Request Creation
# ---------------------------------------------------------------------------

class TestRequestCreation:
    @pytest.mark.asyncio
    async def test_request_signature(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by=user1.username,
        )
        assert isinstance(request_id, str)
        assert len(request_id) > 0

    @pytest.mark.asyncio
    async def test_request_signature_returns_unique_ids(self, sig, user1):
        id1 = await sig.request_signature(
            document=_dummy_doc(), signatories=[user1.username], requested_by=user1.username
        )
        id2 = await sig.request_signature(
            document=_dummy_doc(), signatories=[user1.username], requested_by=user1.username
        )
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_request_stored(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(), signatories=[user1.username], requested_by=user1.username
        )
        request = sig.get_request(request_id)
        assert request is not None
        assert request.document_type == "recipe"
        assert request.document_id == "recipe-001"
        assert request.status == SignatureStatus.PENDING

    @pytest.mark.asyncio
    async def test_request_with_multiple_signatories(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username, user2.username],
            requested_by="admin",
            min_signatures=2,
        )
        request = sig.get_request(request_id)
        assert len(request.signatories) == 2
        assert request.min_signatures == 2

    @pytest.mark.asyncio
    async def test_request_with_metadata(self, sig, user1):
        doc = _dummy_doc()
        doc["metadata"] = {"priority": "high", "category": "approval"}
        request_id = await sig.request_signature(
            document=doc, signatories=[user1.username], requested_by="admin"
        )
        request = sig.get_request(request_id)
        assert request.metadata["priority"] == "high"

    @pytest.mark.asyncio
    async def test_request_with_expiration(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
            expires_in_hours=24,
        )
        request = sig.get_request(request_id)
        assert request.expires_at is not None
        assert request.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_request_missing_doc_type_raises(self, sig, user1):
        with pytest.raises(ValidationError, match="type"):
            await sig.request_signature(
                document={"id": "r-001"},
                signatories=[user1.username],
                requested_by="admin",
            )

    @pytest.mark.asyncio
    async def test_request_missing_doc_id_raises(self, sig, user1):
        with pytest.raises(ValidationError, match="id"):
            await sig.request_signature(
                document={"type": "recipe"},
                signatories=[user1.username],
                requested_by="admin",
            )

    @pytest.mark.asyncio
    async def test_request_empty_signatories_raises(self, sig, user1):
        with pytest.raises(ValidationError, match="signatory"):
            await sig.request_signature(
                document=_dummy_doc(),
                signatories=[],
                requested_by="admin",
            )

    @pytest.mark.asyncio
    async def test_request_min_signatures_too_high_raises(self, sig, user1):
        with pytest.raises(ValidationError, match="min_signatures"):
            await sig.request_signature(
                document=_dummy_doc(),
                signatories=[user1.username],
                requested_by="admin",
                min_signatures=5,
            )


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------

class TestSigning:
    @pytest.mark.asyncio
    async def test_sign_success(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        result = await sig.sign(
            request_id=request_id,
            user=user1,
            signature=sig_token,
            meaning="approver",
            comment="Approved after review",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_sign_updates_request_status(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        request = sig.get_request(request_id)
        assert request.status == SignatureStatus.FULLY_SIGNED

    @pytest.mark.asyncio
    async def test_sign_record_stored(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        records = sig.get_signatures(request_id)
        assert len(records) == 1
        assert records[0].username == user1.username
        assert records[0].meaning == "approver"
        assert records[0].signature_hash

    @pytest.mark.asyncio
    async def test_sign_nonexistent_request_raises(self, sig, user1):
        with pytest.raises(ValidationError, match="not found"):
            await sig.sign("nonexistent", user1, "token", meaning="approver")

    @pytest.mark.asyncio
    async def test_sign_non_signatory_raises(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user2.username)
        with pytest.raises(ValidationError, match="not a required signatory"):
            await sig.sign(request_id, user2, sig_token, meaning="approver")

    @pytest.mark.asyncio
    async def test_sign_twice_raises(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username, "other_user"],
            requested_by="admin",
            min_signatures=2,
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        with pytest.raises(ValidationError, match="already"):
            await sig.sign(request_id, user1, sig_token, meaning="reviewer")

    @pytest.mark.asyncio
    async def test_sign_invalid_identity_raises(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        with pytest.raises(AuthenticationError, match="identity"):
            await sig.sign(request_id, user1, "wrong_token", meaning="approver")

    @pytest.mark.asyncio
    async def test_sign_inactive_user_raises(self, sig, inactive_user):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[inactive_user.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(inactive_user.username)
        with pytest.raises(AuthenticationError, match="identity"):
            await sig.sign(request_id, inactive_user, sig_token, meaning="approver")

    @pytest.mark.asyncio
    async def test_sign_locked_user_raises(self, sig, locked_user):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[locked_user.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(locked_user.username)
        with pytest.raises(AuthenticationError, match="identity"):
            await sig.sign(request_id, locked_user, sig_token, meaning="approver")

    @pytest.mark.asyncio
    async def test_sign_expired_request_raises(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        request = sig.get_request(request_id)
        request.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        sig_token = _valid_signature_token(user1.username)
        with pytest.raises(ValidationError, match="expired"):
            await sig.sign(request_id, user1, sig_token, meaning="approver")

    @pytest.mark.asyncio
    async def test_sign_completed_request_raises(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        request = sig.get_request(request_id)
        request.status = SignatureStatus.FULLY_SIGNED
        sig_token = _valid_signature_token(user1.username)
        with pytest.raises(ValidationError, match="already"):
            await sig.sign(request_id, user1, sig_token, meaning="approver")

    @pytest.mark.asyncio
    async def test_sign_empty_meaning_raises(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        with pytest.raises(ValidationError, match="meaning"):
            await sig.sign(request_id, user1, sig_token, meaning="")

    @pytest.mark.asyncio
    async def test_sign_meaning_too_long_raises(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        with pytest.raises(ValidationError, match="meaning"):
            await sig.sign(request_id, user1, sig_token, meaning="x" * 501)

    @pytest.mark.asyncio
    async def test_sign_with_ip_address(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(
            request_id, user1, sig_token, meaning="approver", ip_address="192.168.1.1"
        )
        records = sig.get_signatures(request_id)
        assert records[0].ip_address == "192.168.1.1"


# ---------------------------------------------------------------------------
# Multi-Signatory Workflow
# ---------------------------------------------------------------------------

class TestMultiSignature:
    @pytest.mark.asyncio
    async def test_partial_sign(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username, user2.username],
            requested_by="admin",
            min_signatures=2,
        )
        sig_token1 = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token1, meaning="author")
        request = sig.get_request(request_id)
        assert request.status == SignatureStatus.PARTIALLY_SIGNED

    @pytest.mark.asyncio
    async def test_fully_sign_after_all_signed(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username, user2.username],
            requested_by="admin",
            min_signatures=2,
        )
        sig_token1 = _valid_signature_token(user1.username)
        sig_token2 = _valid_signature_token(user2.username)
        await sig.sign(request_id, user1, sig_token1, meaning="author")
        await sig.sign(request_id, user2, sig_token2, meaning="approver")
        request = sig.get_request(request_id)
        assert request.status == SignatureStatus.FULLY_SIGNED
        assert len(sig.get_signatures(request_id)) == 2

    @pytest.mark.asyncio
    async def test_different_meanings(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username, user2.username],
            requested_by="admin",
            min_signatures=2,
        )
        sig_token1 = _valid_signature_token(user1.username)
        sig_token2 = _valid_signature_token(user2.username)
        await sig.sign(request_id, user1, sig_token1, meaning="author")
        await sig.sign(request_id, user2, sig_token2, meaning="reviewer")
        records = sig.get_signatures(request_id)
        meanings = {r.meaning for r in records}
        assert "author" in meanings
        assert "reviewer" in meanings


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class TestVerification:
    @pytest.mark.asyncio
    async def test_verify_valid_signature(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        records = sig.get_signatures(request_id)
        result = await sig.verify_signature(records[0].id)
        assert result.valid is True
        assert result.is_valid is True
        assert result.username == user1.username
        assert result.meaning == "approver"

    @pytest.mark.asyncio
    async def test_verify_revoked_signature(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        records = sig.get_signatures(request_id)
        await sig.revoke_signature(records[0].id, "admin")
        result = await sig.verify_signature(records[0].id)
        assert result.valid is False
        assert "revoked" in result.errors[0]

    @pytest.mark.asyncio
    async def test_verify_nonexistent_signature(self, sig):
        result = await sig.verify_signature("nonexistent")
        assert result.valid is False
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_verify_signatures_for_request(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username, user2.username],
            requested_by="admin",
            min_signatures=2,
        )
        sig_token1 = _valid_signature_token(user1.username)
        sig_token2 = _valid_signature_token(user2.username)
        await sig.sign(request_id, user1, sig_token1, meaning="author")
        await sig.sign(request_id, user2, sig_token2, meaning="approver")
        results = await sig.verify_signatures_for_request(request_id)
        assert len(results) == 2
        assert all(r.valid for r in results)


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------

class TestRevoke:
    @pytest.mark.asyncio
    async def test_revoke_signature(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        records = sig.get_signatures(request_id)
        result = await sig.revoke_signature(records[0].id, "admin")
        assert result is True
        assert records[0].revoked is True
        assert records[0].revoked_by == "admin"
        assert records[0].revoked_at is not None

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_raises(self, sig):
        with pytest.raises(ValidationError, match="not found"):
            await sig.revoke_signature("nonexistent", "admin")

    @pytest.mark.asyncio
    async def test_revoke_already_revoked_raises(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        records = sig.get_signatures(request_id)
        await sig.revoke_signature(records[0].id, "admin")
        with pytest.raises(ValidationError, match="already revoked"):
            await sig.revoke_signature(records[0].id, "admin")


# ---------------------------------------------------------------------------
# Query Methods
# ---------------------------------------------------------------------------

class TestQueryMethods:
    @pytest.mark.asyncio
    async def test_get_pending_requests(self, sig, user1):
        await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        pending = sig.get_pending_requests(user1.username)
        assert len(pending) >= 1
        assert all(not r.is_complete for r in pending)

    @pytest.mark.asyncio
    async def test_get_pending_requests_excludes_signed(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="approver")
        pending = sig.get_pending_requests(user1.username)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_get_pending_requests_excludes_expired(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
        )
        request = sig.get_request(request_id)
        request.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        pending = sig.get_pending_requests(user1.username)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_get_document_history(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(recipe_id="recipe-001"),
            signatories=[user1.username, user2.username],
            requested_by="admin",
        )
        sig_token1 = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token1, meaning="author")
        history = sig.get_document_history("recipe", "recipe-001")
        assert len(history.requests) >= 1
        assert len(history.signatures) >= 1
        assert history.latest_request is not None

    @pytest.mark.asyncio
    async def test_check_signing_status(self, sig, user1, user2):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username, user2.username],
            requested_by="admin",
            min_signatures=2,
        )
        sig_token = _valid_signature_token(user1.username)
        await sig.sign(request_id, user1, sig_token, meaning="author")
        status = sig.check_signing_status(request_id)
        assert status["status"] == "partially_signed"
        assert status["signed_count"] == 1
        assert user2.username in status["pending"]
        assert status["is_complete"] is False


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class TestManifest:
    def test_create_manifest(self):
        manifest = ElectronicSignature.create_manifest(
            document_type="recipe",
            document_id="recipe-001",
            signer_full_name="John Doe",
            meaning="approver",
        )
        assert "John Doe" in manifest
        assert "recipe" in manifest
        assert "recipe-001" in manifest
        assert "approver" in manifest
        assert "21 CFR Part 11" in manifest
        assert "ELECTRONIC SIGNATURE MANIFEST" in manifest


# ---------------------------------------------------------------------------
# Maintenance / Cleanup
# ---------------------------------------------------------------------------

class TestMaintenance:
    @pytest.mark.asyncio
    async def test_expire_stale_requests(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
            expires_in_hours=1,
        )
        request = sig.get_request(request_id)
        request.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        count = sig.expire_stale_requests()
        assert count >= 1
        assert request.status == SignatureStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_expire_non_expired_requests(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
            expires_in_hours=24,
        )
        count = sig.expire_stale_requests()
        assert count == 0

    @pytest.mark.asyncio
    async def test_expire_complete_requests_ignored(self, sig, user1):
        request_id = await sig.request_signature(
            document=_dummy_doc(),
            signatories=[user1.username],
            requested_by="admin",
            expires_in_hours=1,
        )
        request = sig.get_request(request_id)
        request.status = SignatureStatus.FULLY_SIGNED
        request.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        count = sig.expire_stale_requests()
        assert count == 0
