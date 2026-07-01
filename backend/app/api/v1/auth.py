from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.core.time import utcnow
from app.repositories import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.username, user.role.value),
        refresh_token=create_refresh_token(user.username, user.role.value),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(payload.username)
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    user.last_login_at = utcnow()
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        claims = decode_token(payload.refresh_token)
    except JWTError as exc:
        raise invalid from exc

    if claims.get("type") != "refresh":
        raise invalid
    username = claims.get("sub")
    user = await UserRepository(db).get_by_username(username) if username else None
    if user is None or not user.is_active:
        raise invalid
    return _tokens_for(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    """Access/refresh tokens are stateless JWTs (ARCHITECTURE.md §3.6) — there is nothing to
    revoke server-side; the client discards its tokens. Kept as a real endpoint (rather than
    omitted) for API symmetry and so a future token-blacklist can slot in without a client
    contract change.
    """
    return None


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)
