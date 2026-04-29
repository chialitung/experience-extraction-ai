from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, UserUpdate
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
from datetime import timedelta


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: UserCreate) -> User:
        """注册新用户"""
        # 检查邮箱是否已存在
        result = await self.db.execute(select(User).where(User.email == data.email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        user = User(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, data: UserLogin) -> Optional[User]:
        """验证用户登录凭据"""
        result = await self.db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()
        if not user:
            return None
        if not verify_password(data.password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_user(self, user: User, data: UserUpdate) -> User:
        """更新用户信息"""
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.password is not None:
            user.hashed_password = get_password_hash(data.password)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    def create_access_token_for_user(self, user: User) -> str:
        """为用户生成访问令牌"""
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return create_access_token(
            data={"sub": str(user.id), "email": user.email},
            expires_delta=expires_delta,
        )
