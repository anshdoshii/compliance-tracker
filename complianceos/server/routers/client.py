"""SMB (client) facing endpoints: profile setup and CA invite acceptance.

Rules enforced (CLAUDE.md §Non-negotiable):
  - All handlers are gated by require_smb (role check).
  - Profile queries always filter by SMBProfile.user_id == current_user.id.
  - Invite acceptance verifies the link belongs to the authenticated client.
  - Health score recalculation on profile update is noted as TODO (Phase 2).
"""
import uuid as uuid_module
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.database import get_db
from core.dependencies import require_smb
from models.ca_client_link import CAClientLink
from models.ca_profile import CAProfile
from models.smb_profile import SMBProfile
from models.user import User

router = APIRouter(prefix="/client", tags=["client"])


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

async def _get_smb_profile(user: User, db: AsyncSession) -> SMBProfile | None:
    result = await db.execute(select(SMBProfile).where(SMBProfile.user_id == user.id))
    return result.scalar_one_or_none()


def _serialize_smb_profile(smb: SMBProfile) -> dict:
    return {
        "id": str(smb.id),
        "company_name": smb.company_name,
        "company_type": smb.company_type,
        "gstin": smb.gstin,
        "pan": smb.pan,
        "turnover_range": smb.turnover_range,
        "employee_count_range": smb.employee_count_range,
        "sectors": smb.sectors or [],
        "states": smb.states or [],
        "gst_registered": smb.gst_registered,
        "gst_composition": smb.gst_composition,
        "has_factory": smb.has_factory,
        "import_export": smb.import_export,
        "is_listed": smb.is_listed,
        "standalone_plan": smb.standalone_plan,
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SMBProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    company_name: str | None = None
    company_type: str | None = None
    gstin: str | None = None
    pan: str | None = None
    turnover_range: str | None = None
    employee_count_range: str | None = None
    sectors: list[str] | None = None
    states: list[str] | None = None
    gst_registered: bool | None = None
    gst_composition: bool | None = None
    has_factory: bool | None = None
    import_export: bool | None = None
    is_listed: bool | None = None


# ---------------------------------------------------------------------------
# GET /client/profile
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_client_profile(
    user: Annotated[User, Depends(require_smb)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the authenticated SMB's profile plus any active CA link."""
    smb = await _get_smb_profile(user, db)

    linked_ca = None
    if smb is not None:
        # Alias the User model so it doesn't conflict with the current user's row.
        CAUser = aliased(User, name="ca_user")
        result = await db.execute(
            select(CAClientLink, CAProfile, CAUser)
            .join(CAProfile, CAClientLink.ca_id == CAProfile.id)
            .join(CAUser, CAProfile.user_id == CAUser.id)
            .where(
                and_(
                    CAClientLink.client_id == smb.id,
                    CAClientLink.status == "active",
                )
            )
            .limit(1)
        )
        row = result.first()
        if row is not None:
            link, ca_profile, ca_user = row
            linked_ca = {
                "link_id": str(link.id),
                "ca_id": str(ca_profile.id),
                "firm_name": ca_profile.firm_name,
                "full_name": ca_user.full_name,
                "mobile": ca_user.mobile,
                "plan": ca_profile.plan,
            }

    return _success(
        {
            "user": {
                "id": str(user.id),
                "mobile": user.mobile,
                "full_name": user.full_name,
                "email": user.email,
            },
            "profile": _serialize_smb_profile(smb)
            if smb is not None
            else {
                "id": None,
                "company_name": None,
                "company_type": None,
                "gstin": None,
                "pan": None,
                "turnover_range": None,
                "employee_count_range": None,
                "sectors": [],
                "states": [],
                "gst_registered": False,
                "gst_composition": False,
                "has_factory": False,
                "import_export": False,
                "is_listed": False,
                "standalone_plan": "free",
            },
            "linked_ca": linked_ca,
        }
    )


# ---------------------------------------------------------------------------
# PUT /client/profile
# ---------------------------------------------------------------------------

@router.put("/profile")
async def update_client_profile(
    body: SMBProfileUpdateRequest,
    user: Annotated[User, Depends(require_smb)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Upsert the SMB's company profile.

    Creating for the first time requires company_name (it is NOT NULL in the schema).
    Updating an existing profile allows partial edits.

    TODO (Phase 2): trigger async health score recalculation after every update.
    """
    smb = await _get_smb_profile(user, db)

    if smb is None:
        # First-time creation — company_name is required.
        if not body.company_name or not body.company_name.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=_error(
                    "COMPANY_NAME_REQUIRED",
                    "company_name is required when creating a profile for the first time",
                ),
            )
        smb = SMBProfile(
            user_id=user.id,
            company_name=body.company_name.strip(),
            # Python-side defaults so values are readable immediately after flush.
            standalone_plan="free",
            gst_registered=False,
            gst_composition=False,
            has_factory=False,
            import_export=False,
            is_listed=False,
        )
        db.add(smb)
    else:
        if body.company_name is not None:
            if not body.company_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=_error("INVALID_COMPANY_NAME", "company_name cannot be blank"),
                )
            smb.company_name = body.company_name.strip()

    # Apply partial updates.
    if body.company_type is not None:
        smb.company_type = body.company_type
    if body.gstin is not None:
        smb.gstin = body.gstin or None
    if body.pan is not None:
        smb.pan = body.pan or None
    if body.turnover_range is not None:
        smb.turnover_range = body.turnover_range
    if body.employee_count_range is not None:
        smb.employee_count_range = body.employee_count_range
    if body.sectors is not None:
        smb.sectors = body.sectors
    if body.states is not None:
        smb.states = body.states
    if body.gst_registered is not None:
        smb.gst_registered = body.gst_registered
    if body.gst_composition is not None:
        smb.gst_composition = body.gst_composition
    if body.has_factory is not None:
        smb.has_factory = body.has_factory
    if body.import_export is not None:
        smb.import_export = body.import_export
    if body.is_listed is not None:
        smb.is_listed = body.is_listed

    # User-level field.
    if body.full_name is not None:
        user.full_name = body.full_name

    await db.flush()

    return _success(_serialize_smb_profile(smb))


# ---------------------------------------------------------------------------
# POST /client/invite/accept/{invite_id}
# ---------------------------------------------------------------------------

@router.post("/invite/accept/{invite_id}")
async def accept_invite(
    invite_id: str,
    user: Annotated[User, Depends(require_smb)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Accept a CA's invitation. Verifies the invite belongs to the authenticated client."""
    try:
        invite_uuid = uuid_module.UUID(invite_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error("INVALID_ID", "invite_id must be a valid UUID"),
        ) from exc

    result = await db.execute(
        select(CAClientLink).where(CAClientLink.id == invite_uuid)
    )
    link = result.scalar_one_or_none()

    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error("NOT_FOUND", "Invite not found"),
        )

    # Ownership check — the invite must belong to the current SMB user (rule 2).
    smb = await _get_smb_profile(user, db)
    if smb is None or link.client_id != smb.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error("FORBIDDEN", "This invite does not belong to your account"),
        )

    if link.status == "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error("ALREADY_ACCEPTED", "This invite has already been accepted"),
        )
    if link.status == "removed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error("INVITE_REMOVED", "This invite has been removed by the CA"),
        )

    link.status = "active"
    link.accepted_at = _utc_now()
    await db.flush()

    return _success({"link_id": str(link.id), "status": "active", "accepted_at": link.accepted_at.isoformat()})
