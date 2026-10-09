
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.core.security import verify_password, create_access_token, get_current_user
from app.models.models import User, RoleEnum
from pydantic import BaseModel
from datetime import timedelta
from app.core.config import settings

router = APIRouter()


class LoginData(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(
    response: Response,
    data: LoginData,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.email == data.email)
    )

    user = result.scalars().first()

    if not user or not verify_password(
        data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    access_token = create_access_token(
        data={"sub": str(user.id)}
    )

    refresh_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True, samesite="none", secure=True
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True, samesite="none", secure=True,
        path="/"
    )

    response.set_cookie(
        key="csrf_token",
        value="dummy_csrf_for_now",
        httponly=False, samesite="none", secure=True
    )

    return {
        "message": "Login successful"
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("csrf_token")

    return {
        "message": "Logged out"
    }


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role
    }


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    from jose import jwt, JWTError

    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Missing refresh token"
        )

    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    access_token = create_access_token(
        data={"sub": str(user.id)}
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True, samesite="none", secure=True
    )

    return {
        "message": "Token refreshed"
    }


def get_admin_or_pl_user(
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [
        RoleEnum.ADMIN,
        RoleEnum.PROGRAM_LEADER
    ]:
        raise HTTPException(
            status_code=403,
            detail="Not enough privileges"
        )

    return current_user


def get_superadmin_user(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(
            status_code=403,
            detail="Superadmin access required"
        )

    return current_user