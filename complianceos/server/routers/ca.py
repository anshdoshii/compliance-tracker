"""CA-facing endpoints: profile management and client onboarding.

Rules enforced (CLAUDE.md §Non-negotiable):
  - All handlers are gated by require_ca (role check).
  - Every query filters by CAProfile.id so a CA never sees another CA's data.
  - Pending invites are NOT counted toward the plan client limit.
  - Exceeding the plan limit triggers a soft warning — not a hard block (spec §5.1.1).
"""
import re
import uuid as uuid_module
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, func, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.database import get_db
from core.dependencies import require_ca
from models.ca_client_link import CAClientLink
from models.ca_profile import CAProfile
from models.health_score import HealthScore
from models.smb_profile import SMBProfile
from models.user import User

router = APIRouter(prefix="/ca", tags=["ca"])

_MOBILE_RE = re.compile(r"^\d{10}$")


# ---------------------------------------------------------------------------
# Response envelope helpers
# ---------------------------------------------------------------------------

def _success(data, *, meta=None) -> dict:
    return {"success": True, "data": data, "meta": meta, "error": None}


def _error(code: str, message: str) -> dict:
    return {"success": False, "data": None, "meta": None, "error": {"code": code, "message": message}}


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_ca_profile(user: User, db: AsyncSession) -> CAProfile | None:
    result = await db.execute(select(CAProfile).where(CAProfile.user_id == user.id))
    return result.scalar_one_or_none()


async def _active_client_count(ca: CAProfile, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(CAClientLink)
        .where(and_(CAClientLink.ca_id == ca.id, CAClientLink.status == "active"))
    )
    return result.scalar_one()


def _serialize_ca_profile(ca: CAProfile) -> dict:
    return {
        "id": str(ca.id),
        "icai_number": ca.icai_number,
        "firm_name": ca.firm_name,
        "city": ca.city,
        "state": ca.state,
        "gstin": ca.gstin,
        "plan": ca.plan,
        "plan_client_limit": ca.plan_client_limit,
        "plan_expires_at": ca.plan_expires_at.isoformat() if ca.plan_expires_at else None,
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CAProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    icai_number: str | None = None
    firm_name: str | None = None
    city: str | None = None
    state: str | None = None
    gstin: str | None = None


class InviteClientRequest(BaseModel):
    mobile: str
    company_name: str

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not _MOBILE_RE.match(v):
            raise ValueError("mobile must be exactly 10 digits")
        return v

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("company_name cannot be blank")
        return v.strip()


class ImportClientItem(BaseModel):
    mobile: str
    company_name: str
    gstin: str | None = None
    email: str | None = None

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not _MOBILE_RE.match(v):
            raise ValueError("mobile must be exactly 10 digits")
        return v


class ImportClientsRequest(BaseModel):
    clients: list[ImportClientItem]


# ---------------------------------------------------------------------------
# GET /ca/profile
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_ca_profile(
    user: Annotated[User, Depends(require_ca)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the authenticated CA's profile, plan details, and active client count."""
    ca = await _get_ca_profile(user, db)
    active_count = 0
    if ca is not None:
        active_count = await _active_client_count(ca, db)

    return _success(
        {
            "user": {
                "id": str(user.id),
                "mobile": user.mobile,
                "full_name": user.full_name,
                "email": user.email,
            },
            "profile": _serialize_ca_profile(ca)
            if ca is not None
            else {
                "id": None,
                "icai_number": None,
                "firm_name": None,
                "city": None,
                "state": None,
                "gstin": None,
                "plan": "starter",
                "plan_client_limit": 10,
                "plan_expires_at": None,
            },
            "stats": {"active_client_count": active_count},
        }
    )


# ---------------------------------------------------------------------------
# PUT /ca/profile
# ---------------------------------------------------------------------------

@router.put("/profile")
async def update_ca_profile(
    body: CAProfileUpdateRequest,
    user: Annotated[User, Depends(require_ca)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Upsert the CA's profile. Creates it on first call, updates thereafter."""
    ca = await _get_ca_profile(user, db)

    if ca is None:
        # First-time profile creation — set Python defaults so values are accessible
        # immediately after flush without a round-trip to the DB (CLAUDE.md rule 6).
        ca = CAProfile(
            user_id=user.id,
            plan="starter",
            plan_client_limit=10,
        )
        db.add(ca)

    # Apply partial updates — only override fields that were explicitly provided.
    if body.icai_number is not None:
        ca.icai_number = body.icai_number or None  # empty string → NULL
    if body.firm_name is not None:
        ca.firm_name = body.firm_name
    if body.city is not None:
        ca.city = body.city
    if body.state is not None:
        ca.state = body.state
    if body.gstin is not None:
        ca.gstin = body.gstin or None  # empty string → NULL

    # User-level field (lives on the users table).
    if body.full_name is not None:
        user.full_name = body.full_name

    await db.flush()

    return _success(_serialize_ca_profile(ca))


# ---------------------------------------------------------------------------
# GET /ca/clients
# ---------------------------------------------------------------------------

@router.get("/clients")
async def list_ca_clients(
    user: Annotated[User, Depends(require_ca)],
    db: Annotated[AsyncSession, Depends(get_db)],
    filter_status: str | None = Query(None, alias="status"),
    sort: Literal["health_score", "name", "last_activity"] = Query("last_activity"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List all clients linked to the authenticated CA with optional filters and pagination."""
    ca = await _get_ca_profile(user, db)
    if ca is None:
        return _success([], meta={"page": page, "total": 0, "limit": limit})

    if filter_status is not None and filter_status not in ("active", "pending", "removed"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error("INVALID_STATUS", "status must be one of: active, pending, removed"),
        )

    # Alias for the SMB-side User row to avoid ambiguity with the CA's own User row.
    ClientUser = aliased(User, name="client_user")

    # Correlated scalar subquery — latest health score for each SMB profile.
    score_subq = (
        select(HealthScore.score)
        .where(HealthScore.client_id == SMBProfile.id)
        .order_by(HealthScore.calculated_at.desc())
        .limit(1)
        .correlate(SMBProfile)
        .scalar_subquery()
    )

    base_filter = [CAClientLink.ca_id == ca.id]
    if filter_status:
        base_filter.append(CAClientLink.status == filter_status)

    # Separate count query (avoids scalar subquery in COUNT).
    count_stmt = (
        select(func.count())
        .select_from(CAClientLink)
        .join(SMBProfile, CAClientLink.client_id == SMBProfile.id)
        .where(and_(*base_filter))
    )
    total = (await db.execute(count_stmt)).scalar_one()

    # Main data query.
    stmt = (
        select(CAClientLink, SMBProfile, ClientUser, score_subq.label("health_score"))
        .join(SMBProfile, CAClientLink.client_id == SMBProfile.id)
        .join(ClientUser, SMBProfile.user_id == ClientUser.id)
        .where(and_(*base_filter))
    )

    if sort == "health_score":
        stmt = stmt.order_by(nullslast(score_subq.desc()))
    elif sort == "name":
        stmt = stmt.order_by(SMBProfile.company_name.asc())
    else:  # last_activity (default)
        stmt = stmt.order_by(CAClientLink.invited_at.desc())

    stmt = stmt.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).all()

    clients = [
        {
            "link_id": str(link.id),
            "client_id": str(smb.id),
            "link_status": link.status,
            "invited_at": link.invited_at.isoformat() if link.invited_at else None,
            "accepted_at": link.accepted_at.isoformat() if link.accepted_at else None,
            "mobile": usr.mobile,
            "full_name": usr.full_name,
            "email": usr.email,
            "company_name": smb.company_name,
            "gstin": smb.gstin,
            "health_score": health_score,
        }
        for link, smb, usr, health_score in rows
    ]

    return _success(clients, meta={"page": page, "total": total, "limit": limit})


# ---------------------------------------------------------------------------
# POST /ca/clients/invite
# ---------------------------------------------------------------------------

async def _get_or_create_smb(mobile: str, company_name: str, db: AsyncSession) -> tuple[User, SMBProfile]:
    """Return (client_user, smb_profile), creating them if they don't exist yet."""
    result = await db.execute(select(User).where(User.mobile == mobile))
    client_user = result.scalar_one_or_none()

    if client_user is None:
        client_user = User(mobile=mobile, role="smb", full_name="")
        db.add(client_user)
        await db.flush()  # populate client_user.id
        smb_profile = SMBProfile(
            user_id=client_user.id,
            company_name=company_name,
            standalone_plan="free",
        )
        db.add(smb_profile)
        await db.flush()
    else:
        if client_user.role != "smb":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error("INVALID_ROLE", "The mobile number belongs to a CA account"),
            )
        result = await db.execute(select(SMBProfile).where(SMBProfile.user_id == client_user.id))
        smb_profile = result.scalar_one_or_none()
        if smb_profile is None:
            smb_profile = SMBProfile(
                user_id=client_user.id,
                company_name=company_name,
                standalone_plan="free",
            )
            db.add(smb_profile)
            await db.flush()

    return client_user, smb_profile


@router.post("/clients/invite", status_code=status.HTTP_201_CREATED)
async def invite_client(
    body: InviteClientRequest,
    user: Annotated[User, Depends(require_ca)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Invite a client by mobile number. Idempotent: re-activates a removed link."""
    ca = await _get_ca_profile(user, db)
    if ca is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error("PROFILE_REQUIRED", "Complete your CA profile before inviting clients"),
        )

    _, smb_profile = await _get_or_create_smb(body.mobile, body.company_name, db)

    # Existing link check.
    result = await db.execute(
        select(CAClientLink).where(
            and_(CAClientLink.ca_id == ca.id, CAClientLink.client_id == smb_profile.id)
        )
    )
    existing_link = result.scalar_one_or_none()

    plan_limit_warning = False

    if existing_link is not None:
        if existing_link.status in ("active", "pending"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_error("ALREADY_LINKED", "Client is already linked or has a pending invite"),
            )
        # Re-invite a previously removed client.
        existing_link.status = "pending"
        existing_link.invited_at = _utc_now()
        existing_link.accepted_at = None
        existing_link.removed_at = None
        await db.flush()
        link = existing_link
    else:
        # Check plan limit (active clients only — pending don't count, per spec §5.1.1).
        active_count = await _active_client_count(ca, db)
        if active_count >= ca.plan_client_limit:
            plan_limit_warning = True  # soft nudge, not a hard block

        link = CAClientLink(ca_id=ca.id, client_id=smb_profile.id, status="pending")
        db.add(link)
        await db.flush()

    return _success(
        {
            "invite_id": str(link.id),
            "status": link.status,
            "plan_limit_warning": plan_limit_warning,
        }
    )


# ---------------------------------------------------------------------------
# POST /ca/clients/import
# ---------------------------------------------------------------------------

@router.post("/clients/import")
async def import_clients(
    body: ImportClientsRequest,
    user: Annotated[User, Depends(require_ca)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Bulk-import clients from a JSON list. Skips failures without aborting the batch."""
    ca = await _get_ca_profile(user, db)
    if ca is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error("PROFILE_REQUIRED", "Complete your CA profile before importing clients"),
        )

    invited = 0
    already_linked = 0
    failed = 0

    for item in body.clients:
        try:
            _, smb_profile = await _get_or_create_smb(item.mobile, item.company_name, db)

            # Optionally persist GSTIN and email if CA supplied them.
            if item.gstin and not smb_profile.gstin:
                smb_profile.gstin = item.gstin

            result = await db.execute(
                select(CAClientLink).where(
                    and_(CAClientLink.ca_id == ca.id, CAClientLink.client_id == smb_profile.id)
                )
            )
            existing_link = result.scalar_one_or_none()

            if existing_link is not None and existing_link.status in ("active", "pending"):
                already_linked += 1
                continue

            if existing_link is not None:
                # Re-invite previously removed client.
                existing_link.status = "pending"
                existing_link.invited_at = _utc_now()
                existing_link.accepted_at = None
                existing_link.removed_at = None
            else:
                db.add(CAClientLink(ca_id=ca.id, client_id=smb_profile.id, status="pending"))

            await db.flush()
            invited += 1

        except HTTPException:
            failed += 1
        except Exception:  # noqa: BLE001
            failed += 1

    # Soft plan-limit warning in the response — not a hard block.
    active_count = await _active_client_count(ca, db)
    plan_limit_warning = active_count >= ca.plan_client_limit

    return _success(
        {
            "invited": invited,
            "already_linked": already_linked,
            "failed": failed,
            "plan_limit_warning": plan_limit_warning,
        }
    )


# ---------------------------------------------------------------------------
# DELETE /ca/clients/{client_id}
# ---------------------------------------------------------------------------

@router.delete("/clients/{client_id}")
async def remove_client(
    client_id: str,
    user: Annotated[User, Depends(require_ca)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Soft-remove a client: sets link status to 'removed', records removal timestamp."""
    ca = await _get_ca_profile(user, db)
    if ca is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error("NOT_FOUND", "CA profile not found"),
        )

    try:
        client_uuid = uuid_module.UUID(client_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error("INVALID_ID", "client_id must be a valid UUID"),
        ) from exc

    result = await db.execute(
        select(CAClientLink).where(
            and_(
                CAClientLink.ca_id == ca.id,
                CAClientLink.client_id == client_uuid,
                CAClientLink.status != "removed",
            )
        )
    )
    link = result.scalar_one_or_none()

    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error("NOT_FOUND", "Client not found or already removed"),
        )

    link.status = "removed"
    link.removed_at = _utc_now()
    await db.flush()

    return _success({"message": "Client removed successfully"})
