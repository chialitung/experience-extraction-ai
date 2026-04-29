from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_active_user, get_current_active_user_optional, get_current_admin
from app.services.auth_service import AuthService
from app.schemas.auth import (
    UserCreate, UserLogin, UserUpdate, UserResponse,
    TokenResponse, UserListResponse, UserAdminUpdate,
    PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse,
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


# ==================== Password Reset ====================

@router.post("/password-reset-request", response_model=PasswordResetResponse)
async def password_reset_request(
    data: PasswordResetRequest,
    service: AuthService = Depends(get_auth_service),
):
    """请求密码重置：发送包含重置链接的邮件"""
    from app.services.email_service import EmailService

    raw_token = await service.create_password_reset(data.email)

    if raw_token:
        reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={raw_token}"
        EmailService.send_password_reset_email(data.email, reset_url)

    # 无论用户是否存在，都返回相同消息（防止枚举攻击）
    return PasswordResetResponse(
        message="如果该邮箱已注册，重置链接已发送至您的邮箱，请查收"
    )


@router.post("/password-reset-confirm", response_model=PasswordResetResponse)
async def password_reset_confirm(
    data: PasswordResetConfirm,
    service: AuthService = Depends(get_auth_service),
):
    """确认密码重置：验证令牌并更新密码"""
    success = await service.reset_password(data.token, data.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置链接无效或已过期，请重新申请",
        )
    return PasswordResetResponse(message="密码重置成功，请使用新密码登录")


# ==================== Admin Endpoints ====================

@router.get("/admin/users", response_model=UserListResponse)
async def admin_list_users(
    skip: int = 0,
    limit: int = 100,
    admin: User = Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
):
    """管理员获取用户列表"""
    users, total = await service.list_users(skip=skip, limit=limit)
    return {"items": users, "total": total}


@router.get("/admin/users/{user_id}", response_model=UserResponse)
async def admin_get_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
):
    """管理员获取指定用户信息"""
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: str,
    data: UserAdminUpdate,
    admin: User = Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
):
    """管理员更新指定用户信息"""
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated = await service.update_user_admin(user, data, current_admin_id=str(admin.id))
    return UserResponse.model_validate(updated)


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
):
    """管理员删除指定用户"""
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await service.delete_user_admin(user, current_admin_id=str(admin.id))
    return None
