from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_active_user, get_current_active_user_optional
from app.services.auth_service import AuthService
from app.schemas.auth import (
    UserCreate, UserLogin, UserUpdate, UserResponse,
    TokenResponse,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    service: AuthService = Depends(get_auth_service),
):
    """用户注册"""
    user = await service.create_user(data)
    access_token = service.create_access_token_for_user(user)
    return TokenResponse(
        access_token=access_token,
        expires_in=60,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    service: AuthService = Depends(get_auth_service),
):
    """用户登录"""
    user = await service.authenticate(data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = service.create_access_token_for_user(user)
    return TokenResponse(
        access_token=access_token,
        expires_in=60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """获取当前登录用户信息"""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    service: AuthService = Depends(get_auth_service),
):
    """更新当前用户信息"""
    updated = await service.update_user(current_user, data)
    return UserResponse.model_validate(updated)
