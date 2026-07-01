from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import UserRepository
from app.schemas.user import UserCreate, UserOut, UserUpdate

# Every route here is admin-only — enforced once at the router level rather than per-route.
router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_roles(UserRole.ADMIN))])


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    return await UserRepository(db).list()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    repo = UserRepository(db)
    if await repo.get_by_username(payload.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")
    return await repo.create(
        User(username=payload.username, hashed_password=hash_password(payload.password), role=payload.role)
    )


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db)) -> User:
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        user.hashed_password = hash_password(updates.pop("password"))
    for field_name, value in updates.items():
        setattr(user, field_name, value)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)) -> None:
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    await repo.delete(user)
