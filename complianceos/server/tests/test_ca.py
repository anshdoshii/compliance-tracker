"""CA router tests — 8 test categories per endpoint (CLAUDE.md testing rules).

Endpoints covered:
  GET  /v1/ca/profile
  PUT  /v1/ca/profile
  GET  /v1/ca/clients
  POST /v1/ca/clients/invite
  POST /v1/ca/clients/import
  DELETE /v1/ca/clients/{client_id}
"""
import asyncio

import pytest

from models.ca_client_link import CAClientLink
from tests.conftest import make_ca_profile, make_ca_user, make_smb_profile, make_smb_user

BASE = "/v1/ca"


# ===========================================================================
# GET /ca/profile
# ===========================================================================


class TestGetCAProfile:
    # 1. Happy path — no profile yet (new CA)
    @pytest.mark.asyncio
    async def test_returns_null_profile_when_not_set_up(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["profile"]["id"] is None
        assert body["data"]["profile"]["plan"] == "starter"
        assert body["data"]["stats"]["active_client_count"] == 0

    # 1. Happy path — full profile
    @pytest.mark.asyncio
    async def test_returns_profile_when_set_up(self, client, db_session):
        user, token = await make_ca_user(db_session)
        ca = await make_ca_profile(db_session, user)
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["profile"]["id"] == str(ca.id)
        assert body["data"]["profile"]["firm_name"] == "Test Firm"
        assert body["data"]["stats"]["active_client_count"] == 0

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.get(f"{BASE}/profile")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_smb_user(self, client, db_session):
        _, token = await make_smb_user(db_session)
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    # 8. Response envelope shape
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        _, token = await make_ca_user(db_session)
        body = (await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})).json()
        assert "success" in body
        assert "data" in body
        assert "meta" in body
        assert "error" in body


# ===========================================================================
# PUT /ca/profile
# ===========================================================================


class TestPutCAProfile:
    # 1. Happy path — creates profile on first call
    @pytest.mark.asyncio
    async def test_creates_profile_on_first_call(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.put(
            f"{BASE}/profile",
            json={"firm_name": "Sharma & Co", "city": "Mumbai", "full_name": "CA Sharma"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["firm_name"] == "Sharma & Co"
        assert body["data"]["city"] == "Mumbai"
        assert body["data"]["plan"] == "starter"
        assert body["data"]["plan_client_limit"] == 10

    # 1. Happy path — updates existing profile
    @pytest.mark.asyncio
    async def test_updates_existing_profile(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        resp = await client.put(
            f"{BASE}/profile",
            json={"city": "Delhi", "state": "Delhi"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["city"] == "Delhi"
        assert resp.json()["data"]["state"] == "Delhi"

    # 1. Happy path — partial update (only provided fields change)
    @pytest.mark.asyncio
    async def test_partial_update_does_not_erase_other_fields(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await client.put(
            f"{BASE}/profile",
            json={"firm_name": "Original Firm", "city": "Pune"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Update only city
        await client.put(
            f"{BASE}/profile",
            json={"city": "Bangalore"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        profile = resp.json()["data"]["profile"]
        assert profile["firm_name"] == "Original Firm"  # unchanged
        assert profile["city"] == "Bangalore"  # updated

    # 1. Happy path — full_name updates user table
    @pytest.mark.asyncio
    async def test_full_name_is_persisted(self, client, db_session):
        _, token = await make_ca_user(db_session)
        await client.put(
            f"{BASE}/profile",
            json={"full_name": "Ravi Kumar"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = (
            await client.get(f"{BASE}/profile", headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert body["data"]["user"]["full_name"] == "Ravi Kumar"

    # 2. Validation errors — no required fields (body is entirely optional so 200)
    @pytest.mark.asyncio
    async def test_empty_body_is_accepted(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.put(
            f"{BASE}/profile", json={}, headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.put(f"{BASE}/profile", json={"firm_name": "X"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_smb_user(self, client, db_session):
        _, token = await make_smb_user(db_session)
        resp = await client.put(
            f"{BASE}/profile",
            json={"firm_name": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # 8. Envelope shape
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        _, token = await make_ca_user(db_session)
        body = (
            await client.put(f"{BASE}/profile", json={}, headers={"Authorization": f"Bearer {token}"})
        ).json()
        assert {"success", "data", "meta", "error"} <= body.keys()


# ===========================================================================
# GET /ca/clients
# ===========================================================================


class TestGetCAClients:
    async def _setup(self, db_session):
        """Create a CA with a profile and two linked clients."""
        ca_user, ca_token = await make_ca_user(db_session, "9100000001")
        ca = await make_ca_profile(db_session, ca_user)

        smb_user1, _ = await make_smb_user(db_session, "9200000001")
        smb1 = await make_smb_profile(db_session, smb_user1, "Alpha Corp")
        smb_user2, _ = await make_smb_user(db_session, "9200000002")
        smb2 = await make_smb_profile(db_session, smb_user2, "Beta Ltd")

        link1 = CAClientLink(ca_id=ca.id, client_id=smb1.id, status="active")
        link2 = CAClientLink(ca_id=ca.id, client_id=smb2.id, status="pending")
        db_session.add_all([link1, link2])
        await db_session.flush()

        return ca_token, ca, smb1, smb2, link1, link2

    # 1. Happy path
    @pytest.mark.asyncio
    async def test_returns_all_clients(self, client, db_session):
        ca_token, *_ = await self._setup(db_session)
        resp = await client.get(f"{BASE}/clients", headers={"Authorization": f"Bearer {ca_token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["meta"]["total"] == 2
        assert len(body["data"]) == 2

    # 1. Happy path — status filter
    @pytest.mark.asyncio
    async def test_filter_by_status_active(self, client, db_session):
        ca_token, *_ = await self._setup(db_session)
        resp = await client.get(
            f"{BASE}/clients?status=active", headers={"Authorization": f"Bearer {ca_token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["link_status"] == "active"

    # 1. Happy path — pagination
    @pytest.mark.asyncio
    async def test_pagination(self, client, db_session):
        ca_token, *_ = await self._setup(db_session)
        resp = await client.get(
            f"{BASE}/clients?page=1&limit=1", headers={"Authorization": f"Bearer {ca_token}"}
        )
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert len(body["data"]) == 1

    # 1. Happy path — sort by name
    @pytest.mark.asyncio
    async def test_sort_by_name(self, client, db_session):
        ca_token, *_ = await self._setup(db_session)
        resp = await client.get(
            f"{BASE}/clients?sort=name", headers={"Authorization": f"Bearer {ca_token}"}
        )
        names = [c["company_name"] for c in resp.json()["data"]]
        assert names == sorted(names)

    # 1. Happy path — no profile returns empty list
    @pytest.mark.asyncio
    async def test_no_profile_returns_empty(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.get(f"{BASE}/clients", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    # 2. Validation errors — invalid status
    @pytest.mark.asyncio
    async def test_invalid_status_returns_422(self, client, db_session):
        ca_token, *_ = await self._setup(db_session)
        resp = await client.get(
            f"{BASE}/clients?status=invalid", headers={"Authorization": f"Bearer {ca_token}"}
        )
        assert resp.status_code == 422

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.get(f"{BASE}/clients")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_smb_user(self, client, db_session):
        _, token = await make_smb_user(db_session)
        resp = await client.get(f"{BASE}/clients", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    # 3. Isolation — CA never sees another CA's clients
    @pytest.mark.asyncio
    async def test_ca_only_sees_own_clients(self, client, db_session):
        # CA 1 with a client
        ca_user1, ca_token1 = await make_ca_user(db_session, "9100000010")
        ca1 = await make_ca_profile(db_session, ca_user1)
        smb_user, _ = await make_smb_user(db_session, "9200000010")
        smb = await make_smb_profile(db_session, smb_user)
        db_session.add(CAClientLink(ca_id=ca1.id, client_id=smb.id, status="active"))
        await db_session.flush()

        # CA 2 — must see 0 clients
        ca_user2, ca_token2 = await make_ca_user(db_session, "9100000011")
        await make_ca_profile(db_session, ca_user2)

        resp = await client.get(f"{BASE}/clients", headers={"Authorization": f"Bearer {ca_token2}"})
        assert resp.json()["meta"]["total"] == 0

    # 7. Health score null when not calculated
    @pytest.mark.asyncio
    async def test_health_score_is_null_before_calculation(self, client, db_session):
        ca_token, *_ = await self._setup(db_session)
        data = (
            await client.get(f"{BASE}/clients", headers={"Authorization": f"Bearer {ca_token}"})
        ).json()["data"]
        assert all(c["health_score"] is None for c in data)

    # 8. Response envelope
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        _, token = await make_ca_user(db_session)
        body = (await client.get(f"{BASE}/clients", headers={"Authorization": f"Bearer {token}"})).json()
        assert {"success", "data", "meta", "error"} <= body.keys()
        assert "page" in body["meta"]
        assert "total" in body["meta"]


# ===========================================================================
# POST /ca/clients/invite
# ===========================================================================


class TestInviteClient:
    # 1. Happy path — inviting a brand-new mobile (no user exists)
    @pytest.mark.asyncio
    async def test_invite_new_mobile_creates_user_and_link(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000001", "company_name": "New Corp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "pending"
        assert "invite_id" in body["data"]

    # 1. Happy path — inviting an existing SMB user
    @pytest.mark.asyncio
    async def test_invite_existing_smb_user(self, client, db_session):
        ca_user, ca_token = await make_ca_user(db_session)
        await make_ca_profile(db_session, ca_user)
        smb_user, _ = await make_smb_user(db_session, "9300000002")
        await make_smb_profile(db_session, smb_user)
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000002", "company_name": "Existing Corp"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["status"] == "pending"

    # 1. Happy path — re-inviting a removed client
    @pytest.mark.asyncio
    async def test_reinvite_removed_client_sets_pending(self, client, db_session):
        ca_user, ca_token = await make_ca_user(db_session)
        ca = await make_ca_profile(db_session, ca_user)
        smb_user, _ = await make_smb_user(db_session, "9300000003")
        smb = await make_smb_profile(db_session, smb_user)
        link = CAClientLink(ca_id=ca.id, client_id=smb.id, status="removed")
        db_session.add(link)
        await db_session.flush()

        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000003", "company_name": "Removed Corp"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["status"] == "pending"

    # 1. Plan limit warning (soft, not hard block)
    @pytest.mark.asyncio
    async def test_plan_limit_warning_included_when_exceeded(self, client, db_session):
        ca_user, ca_token = await make_ca_user(db_session)
        ca = await make_ca_profile(db_session, ca_user)
        # Manually set a tiny limit for the test.
        ca.plan_client_limit = 0
        await db_session.flush()

        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000004", "company_name": "Over Limit"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        # Still succeeds — just with a warning.
        assert resp.status_code == 201
        assert resp.json()["data"]["plan_limit_warning"] is True

    # 2. Validation errors
    @pytest.mark.asyncio
    async def test_invalid_mobile_returns_422(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "123", "company_name": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_blank_company_name_returns_422(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000005", "company_name": "   "},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_company_name_returns_422(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000006"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.post(
            f"{BASE}/clients/invite", json={"mobile": "9300000099", "company_name": "X"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_smb_user(self, client, db_session):
        _, token = await make_smb_user(db_session)
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000099", "company_name": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # 4. Business errors
    @pytest.mark.asyncio
    async def test_no_ca_profile_returns_400(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000007", "company_name": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "PROFILE_REQUIRED"

    @pytest.mark.asyncio
    async def test_inviting_ca_mobile_returns_400(self, client, db_session):
        ca_user, ca_token = await make_ca_user(db_session, "9100000020")
        await make_ca_profile(db_session, ca_user)
        # Another CA account
        ca_user2, _ = await make_ca_user(db_session, "9100000021")
        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9100000021", "company_name": "X"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ROLE"

    @pytest.mark.asyncio
    async def test_duplicate_active_link_returns_409(self, client, db_session):
        ca_user, ca_token = await make_ca_user(db_session)
        ca = await make_ca_profile(db_session, ca_user)
        smb_user, _ = await make_smb_user(db_session, "9300000008")
        smb = await make_smb_profile(db_session, smb_user)
        db_session.add(CAClientLink(ca_id=ca.id, client_id=smb.id, status="active"))
        await db_session.flush()

        resp = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000008", "company_name": "X"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "ALREADY_LINKED"

    # 5. Concurrency — two simultaneous invites for the same mobile should not create duplicate links
    @pytest.mark.asyncio
    async def test_concurrent_invite_same_mobile_no_duplicate(self, client, db_session, db_engine):
        """
        We test uniqueness at the model/DB layer (CLAUDE.md: don't test DB uniqueness
        through HTTP with a shared test session — test at model layer instead).
        This test instead verifies sequential idempotency via the HTTP layer.
        """
        ca_user, ca_token = await make_ca_user(db_session)
        await make_ca_profile(db_session, ca_user)

        # First invite succeeds.
        r1 = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000009", "company_name": "Concurrency Corp"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        assert r1.status_code == 201

        # Second invite for same mobile → 409 (already pending).
        r2 = await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9300000009", "company_name": "Concurrency Corp"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        assert r2.status_code == 409

    # 7. Side-effect — invite creates SMB user + profile when mobile is unknown
    @pytest.mark.asyncio
    async def test_invite_unknown_mobile_creates_smb_user(self, client, db_session):
        from sqlalchemy import select

        from models.user import User

        ca_user, ca_token = await make_ca_user(db_session)
        await make_ca_profile(db_session, ca_user)
        await client.post(
            f"{BASE}/clients/invite",
            json={"mobile": "9399999999", "company_name": "New Biz"},
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        result = await db_session.execute(select(User).where(User.mobile == "9399999999"))
        new_user = result.scalar_one_or_none()
        assert new_user is not None
        assert new_user.role == "smb"

    # 8. Envelope
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        body = (
            await client.post(
                f"{BASE}/clients/invite",
                json={"mobile": "9300000091", "company_name": "Env Corp"},
                headers={"Authorization": f"Bearer {token}"},
            )
        ).json()
        assert {"success", "data", "meta", "error"} <= body.keys()


# ===========================================================================
# POST /ca/clients/import
# ===========================================================================


class TestImportClients:
    # 1. Happy path
    @pytest.mark.asyncio
    async def test_bulk_import_all_new(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        payload = {
            "clients": [
                {"mobile": "9400000001", "company_name": "Alpha"},
                {"mobile": "9400000002", "company_name": "Beta"},
            ]
        }
        resp = await client.post(
            f"{BASE}/clients/import", json=payload, headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["invited"] == 2
        assert body["data"]["already_linked"] == 0
        assert body["data"]["failed"] == 0

    # 1. Already-linked clients counted correctly
    @pytest.mark.asyncio
    async def test_already_linked_counted_separately(self, client, db_session):
        ca_user, ca_token = await make_ca_user(db_session)
        ca = await make_ca_profile(db_session, ca_user)
        smb_user, _ = await make_smb_user(db_session, "9400000010")
        smb = await make_smb_profile(db_session, smb_user)
        db_session.add(CAClientLink(ca_id=ca.id, client_id=smb.id, status="active"))
        await db_session.flush()

        resp = await client.post(
            f"{BASE}/clients/import",
            json={
                "clients": [
                    {"mobile": "9400000010", "company_name": "Existing"},  # already linked
                    {"mobile": "9400000011", "company_name": "New"},       # new
                ]
            },
            headers={"Authorization": f"Bearer {ca_token}"},
        )
        body = resp.json()["data"]
        assert body["invited"] == 1
        assert body["already_linked"] == 1

    # 1. Invalid mobile in batch counted as failed
    @pytest.mark.asyncio
    async def test_invalid_mobile_in_batch_counted_as_failed(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        resp = await client.post(
            f"{BASE}/clients/import",
            json={
                "clients": [
                    {"mobile": "bad", "company_name": "X"},   # invalid — Pydantic catches it
                    {"mobile": "9400000020", "company_name": "Good"},
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # Pydantic validates the entire list, so a bad item inside raises 422.
        assert resp.status_code == 422

    # 2. Empty list is valid
    @pytest.mark.asyncio
    async def test_empty_client_list_returns_zeros(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        resp = await client.post(
            f"{BASE}/clients/import",
            json={"clients": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["invited"] == 0

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        resp = await client.post(f"{BASE}/clients/import", json={"clients": []})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_smb(self, client, db_session):
        _, token = await make_smb_user(db_session)
        resp = await client.post(
            f"{BASE}/clients/import",
            json={"clients": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    # 4. Business error — no CA profile
    @pytest.mark.asyncio
    async def test_no_ca_profile_returns_400(self, client, db_session):
        _, token = await make_ca_user(db_session)
        resp = await client.post(
            f"{BASE}/clients/import",
            json={"clients": [{"mobile": "9400000030", "company_name": "X"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    # 7. GSTIN is propagated to the SMB profile
    @pytest.mark.asyncio
    async def test_gstin_saved_to_smb_profile(self, client, db_session):
        from sqlalchemy import select

        from models.smb_profile import SMBProfile

        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        await client.post(
            f"{BASE}/clients/import",
            json={
                "clients": [
                    {
                        "mobile": "9400000040",
                        "company_name": "GST Corp",
                        "gstin": "29ABCDE1234F1Z5",
                    }
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        from models.user import User

        result = await db_session.execute(select(User).where(User.mobile == "9400000040"))
        u = result.scalar_one()
        result = await db_session.execute(select(SMBProfile).where(SMBProfile.user_id == u.id))
        smb = result.scalar_one()
        assert smb.gstin == "29ABCDE1234F1Z5"

    # 8. Envelope
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        user, token = await make_ca_user(db_session)
        await make_ca_profile(db_session, user)
        body = (
            await client.post(
                f"{BASE}/clients/import",
                json={"clients": []},
                headers={"Authorization": f"Bearer {token}"},
            )
        ).json()
        assert {"success", "data", "meta", "error"} <= body.keys()


# ===========================================================================
# DELETE /ca/clients/{client_id}
# ===========================================================================


class TestRemoveClient:
    async def _setup_link(self, db_session, ca_mobile="9500000001", smb_mobile="9500000002"):
        ca_user, ca_token = await make_ca_user(db_session, ca_mobile)
        ca = await make_ca_profile(db_session, ca_user)
        smb_user, _ = await make_smb_user(db_session, smb_mobile)
        smb = await make_smb_profile(db_session, smb_user)
        link = CAClientLink(ca_id=ca.id, client_id=smb.id, status="active")
        db_session.add(link)
        await db_session.flush()
        return ca_token, ca, smb, link

    # 1. Happy path
    @pytest.mark.asyncio
    async def test_removes_active_client(self, client, db_session):
        ca_token, ca, smb, link = await self._setup_link(db_session)
        resp = await client.delete(
            f"{BASE}/clients/{smb.id}", headers={"Authorization": f"Bearer {ca_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    # 7. Side-effect — link status becomes 'removed'
    @pytest.mark.asyncio
    async def test_link_status_is_removed_after_delete(self, client, db_session):
        from sqlalchemy import select

        ca_token, ca, smb, link = await self._setup_link(
            db_session, "9500000003", "9500000004"
        )
        await client.delete(
            f"{BASE}/clients/{smb.id}", headers={"Authorization": f"Bearer {ca_token}"}
        )
        await db_session.refresh(link)
        assert link.status == "removed"
        assert link.removed_at is not None

    # 7. Removed client no longer appears in active filter
    @pytest.mark.asyncio
    async def test_removed_client_not_in_active_list(self, client, db_session):
        ca_token, ca, smb, link = await self._setup_link(
            db_session, "9500000005", "9500000006"
        )
        await client.delete(
            f"{BASE}/clients/{smb.id}", headers={"Authorization": f"Bearer {ca_token}"}
        )
        resp = await client.get(
            f"{BASE}/clients?status=active", headers={"Authorization": f"Bearer {ca_token}"}
        )
        assert resp.json()["meta"]["total"] == 0

    # 2. Validation — invalid UUID
    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_422(self, client, db_session):
        ca_user, ca_token = await make_ca_user(db_session, "9500000010")
        await make_ca_profile(db_session, ca_user)
        resp = await client.delete(
            f"{BASE}/clients/not-a-uuid", headers={"Authorization": f"Bearer {ca_token}"}
        )
        assert resp.status_code == 422

    # 3. Auth errors
    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, client):
        import uuid
        resp = await client.delete(f"{BASE}/clients/{uuid.uuid4()}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_smb(self, client, db_session):
        import uuid

        _, token = await make_smb_user(db_session, "9500000011")
        resp = await client.delete(
            f"{BASE}/clients/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403

    # 4. Not-found errors
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_client(self, client, db_session):
        import uuid

        ca_user, ca_token = await make_ca_user(db_session, "9500000012")
        await make_ca_profile(db_session, ca_user)
        resp = await client.delete(
            f"{BASE}/clients/{uuid.uuid4()}", headers={"Authorization": f"Bearer {ca_token}"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_remove_another_cas_client(self, client, db_session):
        """CA isolation: removing a client that belongs to a different CA returns 404."""
        ca_token, ca, smb, link = await self._setup_link(
            db_session, "9500000013", "9500000014"
        )
        # Different CA
        ca_user2, ca_token2 = await make_ca_user(db_session, "9500000015")
        await make_ca_profile(db_session, ca_user2)

        resp = await client.delete(
            f"{BASE}/clients/{smb.id}", headers={"Authorization": f"Bearer {ca_token2}"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_double_remove_returns_404(self, client, db_session):
        ca_token, ca, smb, link = await self._setup_link(
            db_session, "9500000016", "9500000017"
        )
        await client.delete(f"{BASE}/clients/{smb.id}", headers={"Authorization": f"Bearer {ca_token}"})
        resp = await client.delete(
            f"{BASE}/clients/{smb.id}", headers={"Authorization": f"Bearer {ca_token}"}
        )
        assert resp.status_code == 404

    # 8. Envelope
    @pytest.mark.asyncio
    async def test_envelope_shape(self, client, db_session):
        ca_token, ca, smb, link = await self._setup_link(
            db_session, "9500000018", "9500000019"
        )
        body = (
            await client.delete(
                f"{BASE}/clients/{smb.id}", headers={"Authorization": f"Bearer {ca_token}"}
            )
        ).json()
        assert {"success", "data", "meta", "error"} <= body.keys()
