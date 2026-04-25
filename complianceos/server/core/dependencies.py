import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import decode_access_token
from core.database import get_db
from models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_redis(request: Request):
    return request.app.state.redis


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    raw_id: str | None = payload.get("sub")
    try:
        user_uuid = uuid.UUID(raw_id) if raw_id else None
        if user_uuid is None:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


async def require_ca(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "ca":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAs only",
        )
    return user


async def require_smb(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "smb":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SMB clients only",
        )
    return user
