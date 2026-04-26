"""SMB (client) router tests — 8 test categories per endpoint (CLAUDE.md testing rules).

Endpoints covered:
  GET  /v1/client/profile
  PUT  /v1/client/profile
  POST /v1/client/invite/accept/{invite_id}
"""
import uuid

import pytest

from models.ca_client_link import CAClientLink
from tests.conftest import make_ca_profile, make_ca_user, make_smb_profile, make_smb_user

BASE = "/v1/client"


# ===========================================================================
# GET /client/profile
# ===========================================================================


class TestGetClientProfile:
    # 1. Happy path — no profile yet
    @pytest.mark.asyncio
    async def test_returns_null_profile_when_not_set_up(self, client, db_session):
        _, token = await make_smb_user(db_session)
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["profile"]["id"] is None
        assert body["data"]["linked_ca"] is None

    # 1. Happy path — full profile, no CA link
    @pytest.mark.asyncio
    async def test_returns_profile_when_set_up(self, client, db_session):
        user, token = await make_smb_user(db_session)
        smb = await make_smb_profile(db_session, user, "Acme Ltd")
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
        assert body["data"]["profile"]["id"] == str(smb.id)
        assert body["data"]["profile"]["company_name"] == "Acme Ltd"
        assert body["data"]["linked_ca"] is None

    # 1. Happy path — active CA link is returned
    @pytest.mark.asyncio
    async def test_linked_ca_returned_when_active(self, client, db_session):
        ca_user, _ = await make_ca_user(db_session, "9600000001")
        ca = await make_ca_profile(db_session, ca_user)
        smb_user, smb_token = await make_smb_user(db_session, "9600000002")
        smb = await make_smb_profile(db_session, smb_user)

        link = CAClientLink(ca_id=ca.id, client_id=smb.id, status="active")
        db_session.add(link)
        await db_session.flush()

        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {smb_token}"})
        body = resp.json()
        assert body["data"]["linked_ca"] is not None
        assert body["data"]["linked_ca"]["ca_id"] == str(ca.id)
        assert body["data"]["linked_ca"]["firm_name"] == "Test Firm"

    # 1. Pending CA link is NOT returned as linked_ca
    @pytest.mark.asyncio
    async def test_pending_link_not_returned_as_linked_ca(self, client, db_session):
        ca_user, _ = await make_ca_user(db_session, "9600000003")
        ca = await make_ca_profile(db_session, ca_user)
        smb_user, smb_token = await make_smb_user(db_session, "9600000004")
        smb = await make_smb_profile(db_session, smb_user)

        db_session.add(CAClientLink(ca_id=ca.id, client_id=smb.id, status="pending"))
        await db_session.flush()

        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {smb_token}"})
        assert resp.json()["data"]["linked_ca"] is None

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.get(f"{BASE}/profile")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_ca_user(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    # 3. Isolation — SMB sees only their own profile
    @pytest.mark.asyncio
    async def test_smb_sees_own_profile_not_others(self, client, db_session):
        user1, token1 = await make_smb_user(db_session, "9600000005")
        await make_smb_profile(db_session, user1, "Company A")
        user2, token2 = await make_smb_user(db_session, "9600000006")
        await make_smb_profile(db_session, user2, "Company B")

        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token1}"})
        assert resp.json()["data"]["profile"]["company_name"] == "Company A"

    # 8. Envelope shape
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        _, token = await make_smb_user(db_session, "9600000007")
        body = (await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})).json()
        assert {"success", "data", "meta", "error"} <= body.keys()


# ===========================================================================
# PUT /client/profile
# ===========================================================================


class TestPutClientProfile:
    # 1. Happy path — first-time creation
    @pytest.mark.asyncio
    async def test_creates_profile_on_first_call(self, client, db_session):
        _, token = await make_smb_user(db_session)
        resp = await client.put(
            f"{BASE}/profile",
            json={"company_name": "New Ventures", "full_name": "Rajesh Kumar"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["company_name"] == "New Ventures"
        assert body["data"]["standalone_plan"] == "free"

    # 1. Happy path — update existing profile
    @pytest.mark.asyncio
    async def test_updates_existing_profile(self, client, db_session):
        user, token = await make_smb_user(db_session)
        await make_smb_profile(db_session, user)
        resp = await client.put(
            f"{BASE}/profile",
            json={"gstin": "29ABCDE1234F1Z5", "gst_registered": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["gstin"] == "29ABCDE1234F1Z5"
        assert body["gst_registered"] is True

    # 1. Happy path — sectors and states round-trip as arrays
    @pytest.mark.asyncio
    async def test_array_fields_round_trip(self, client, db_session):
        _, token = await make_smb_user(db_session, "9700000001")
        await client.put(
            f"{BASE}/profile",
            json={"company_name": "Array Corp", "sectors": ["IT", "Manufacturing"], "states": ["MH", "KA"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        profile = resp.json()["data"]["profile"]
        assert "IT" in profile["sectors"]
        assert "MH" in profile["states"]

    # 1. Happy path — partial update preserves other fields
    @pytest.mark.asyncio
    async def test_partial_update_preserves_other_fields(self, client, db_session):
        user, token = await make_smb_user(db_session, "9700000002")
        await make_smb_profile(db_session, user, "Persistent Corp")
        await client.put(
            f"{BASE}/profile",
            json={"gstin": "29ABCDE1234F1Z5"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        profile = resp.json()["data"]["profile"]
        assert profile["company_name"] == "Persistent Corp"  # unchanged
        assert profile["gstin"] == "29ABCDE1234F1Z5"  # updated

    # 1. full_name updates user table
    @pytest.mark.asyncio
    async def test_full_name_is_persisted_to_user(self, client, db_session):
        _, token = await make_smb_user(db_session, "9700000003")
        await client.put(
            f"{BASE}/profile",
            json={"company_name": "Test Co", "full_name": "Priya Mehta"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = (await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})).json()
        assert body["data"]["user"]["full_name"] == "Priya Mehta"

    # 2. Validation errors — no company_name on first creation
    @pytest.mark.asyncio
    async def test_first_creation_without_company_name_returns_422(self, client, db_session):
        _, token = await make_smb_user(db_session, "9700000004")
        resp = await client.put(
            f"{BASE}/profile",
            json={"gstin": "29ABCDE1234F1Z5"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "COMPANY_NAME_REQUIRED"

    @pytest.mark.asyncio
    async def test_blank_company_name_on_update_returns_422(self, client, db_session):
        user, token = await make_smb_user(db_session, "9700000005")
        await make_smb_profile(db_session, user)
        resp = await client.put(
            f"{BASE}/profile",
            json={"company_name": "   "},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.put(f"{BASE}/profile", json={"company_name": "X"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_ca_user(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.put(
            f"{BASE}/profile",
            json={"company_name": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # 8. Envelope
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        _, token = await make_smb_user(db_session, "9700000009")
        body = (
            await client.put(
                f"{BASE}/profile",
                json={"company_name": "Env Co"},
                headers={"Authorization": f"Bearer {token}"},
            )
        ).json()
        assert {"success", "data", "meta", "error"} <= body.keys()


# ===========================================================================
# POST /client/invite/accept/{invite_id}
# ===========================================================================


class TestAcceptInvite:
    async def _setup_invite(
        self,
        db_session,
        ca_mobile="9800000001",
        smb_mobile="9800000002",
        status="pending",
    ):
        ca_user, _ = await make_ca_user(db_session, ca_mobile)
        ca = await make_ca_profile(db_session, ca_user)
        smb_user, smb_token = await make_smb_user(db_session, smb_mobile)
        smb = await make_smb_profile(db_session, smb_user)
        link = CAClientLink(ca_id=ca.id, client_id=smb.id, status=status)
        db_session.add(link)
        await db_session.flush()
        return smb_token, smb, link

    # 1. Happy path
    @pytest.mark.asyncio
    async def test_accept_pending_invite(self, client, db_session):
        smb_token, smb, link = await self._setup_invite(db_session)
        resp = await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "active"
        assert body["data"]["link_id"] == str(link.id)

    # 7. Side-effect — link status changes + accepted_at is set
    @pytest.mark.asyncio
    async def test_link_becomes_active_after_accept(self, client, db_session):
        smb_token, smb, link = await self._setup_invite(
            db_session, "9800000003", "9800000004"
        )
        await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        await db_session.refresh(link)
        assert link.status == "active"
        assert link.accepted_at is not None

    # 7. Accepted invite is now returned in GET /client/profile as linked_ca
    @pytest.mark.asyncio
    async def test_profile_shows_linked_ca_after_accept(self, client, db_session):
        smb_token, smb, link = await self._setup_invite(
            db_session, "9800000005", "9800000006"
        )
        await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {smb_token}"})
        assert resp.json()["data"]["linked_ca"] is not None

    # 2. Validation errors — invalid UUID
    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_422(self, client, db_session):
        _, token = await make_smb_user(db_session, "9800000010")
        resp = await client.post(
            f"{BASE}/invite/accept/not-a-uuid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.post(f"{BASE}/invite/accept/{uuid.uuid4()}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_ca_user(self, client, db_session):
        _, token = await make_ca_user(db_session, "9800000011")
        resp = await client.post(
            f"{BASE}/invite/accept/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # 3. Ownership check — cannot accept another client's invite
    @pytest.mark.asyncio
    async def test_cannot_accept_other_clients_invite(self, client, db_session):
        # Link belongs to smb_user1 (set up via _setup_invite)
        _, smb1, link = await self._setup_invite(db_session, "9800000012", "9800000013")

        # smb_user2 is a completely different SMB account
        smb_user2, smb_token2 = await make_smb_user(db_session, "9800000014")
        await make_smb_profile(db_session, smb_user2, "Other Corp")

        # smb_user2 should not be able to accept smb_user1's invite
        resp = await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token2}"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    # 4. Business errors
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_invite(self, client, db_session):
        smb_user, smb_token = await make_smb_user(db_session, "9800000016")
        await make_smb_profile(db_session, smb_user, "Orphan Corp")
        resp = await client.post(
            f"{BASE}/invite/accept/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_accept_already_active_invite_returns_400(self, client, db_session):
        smb_token, smb, link = await self._setup_invite(
            db_session, "9800000017", "9800000018", status="active"
        )
        resp = await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "ALREADY_ACCEPTED"

    @pytest.mark.asyncio
    async def test_accept_removed_invite_returns_400(self, client, db_session):
        smb_token, smb, link = await self._setup_invite(
            db_session, "9800000019", "9800000020", status="removed"
        )
        resp = await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVITE_REMOVED"

    # 5. Concurrency — two concurrent accept requests (sequential idempotency check)
    @pytest.mark.asyncio
    async def test_double_accept_second_returns_400(self, client, db_session):
        smb_token, smb, link = await self._setup_invite(
            db_session, "9800000021", "9800000022"
        )
        r1 = await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            f"{BASE}/invite/accept/{link.id}",
            headers={"Authorization": f"Bearer {smb_token}"},
        )
        assert r2.status_code == 400
        assert r2.json()["error"]["code"] == "ALREADY_ACCEPTED"

    # 8. Envelope
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        smb_token, smb, link = await self._setup_invite(
            db_session, "9800000023", "9800000024"
        )
        body = (
            await client.post(
                f"{BASE}/invite/accept/{link.id}",
                headers={"Authorization": f"Bearer {smb_token}"},
            )
        ).json()
        assert {"success", "data", "meta", "error"} <= body.keys()
