import secrets
import hashlib
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, UserUpdate, UserAdminUpdate
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.auth")


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

    async def authenticate(self, data: UserLogin) -> tuple[Optional[User], Optional[str]]:
        """验证用户登录凭据，返回 (user, error_msg)"""
        result = await self.db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()
        if not user:
            return None, "账号不存在，请检查邮箱或注册新账号"
        if not verify_password(data.password, user.hashed_password):
            return None, "密码错误，请重新输入"
        if not user.is_active:
            return None, "账号已被禁用，请联系管理员"
        return user, None

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
            data={"sub": str(user.id), "email": user.email, "is_superuser": user.is_superuser},
            expires_delta=expires_delta,
        )

    # ==================== Admin Methods ====================

    async def list_users(self, skip: int = 0, limit: int = 100) -> Tuple[List[User], int]:
        """获取用户列表（管理员）"""
        stmt = select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.db.execute(stmt)
        users = list(result.scalars().all())

        count_stmt = select(func.count()).select_from(User)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()
        return users, total

    async def update_user_admin(self, target_user: User, data: UserAdminUpdate, current_admin_id: str) -> User:
        """管理员更新任意用户信息"""
        # 自保护：管理员不能取消自己的 superuser 或禁用自己
        if str(target_user.id) == current_admin_id:
            if data.is_superuser is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove your own admin privileges",
                )
            if data.is_active is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate yourself",
                )

        if data.full_name is not None:
            target_user.full_name = data.full_name
        if data.email is not None:
            # 检查邮箱是否已被其他用户使用
            existing = await self.get_user_by_email(data.email)
            if existing and str(existing.id) != str(target_user.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use by another user",
                )
            target_user.email = data.email
        if data.is_active is not None:
            target_user.is_active = data.is_active
        if data.is_superuser is not None:
            target_user.is_superuser = data.is_superuser
        if data.password is not None:
            target_user.hashed_password = get_password_hash(data.password)
        await self.db.commit()
        await self.db.refresh(target_user)
        return target_user

    async def delete_user_admin(self, target_user: User, current_admin_id: str) -> None:
        """管理员删除用户"""
        # 自保护：管理员不能删除自己
        if str(target_user.id) == current_admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself",
            )
        await self.db.delete(target_user)
        await self.db.commit()

    # ==================== Password Reset ====================

    @staticmethod
    def _generate_reset_token() -> str:
        """生成 32 字节 URL-safe 随机令牌"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_token(token: str) -> str:
        """对令牌做 SHA-256 哈希，用于数据库存储"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_password_reset(self, email: str) -> Optional[str]:
        """
        为指定邮箱创建密码重置令牌。
        返回原始令牌（用于邮件链接），若用户不存在则返回 None（静默处理）。
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            return None

        raw_token = self._generate_reset_token()
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        user.reset_token_hash = token_hash
        user.reset_token_expires_at = expires_at
        await self.db.commit()

        logger.info("密码重置令牌已创建", extra={"email": email, "expires_at": expires_at.isoformat()})
        return raw_token

    async def verify_reset_token(self, token: str) -> Optional[User]:
        """验证重置令牌是否有效，返回对应用户或 None"""
        token_hash = self._hash_token(token)
        result = await self.db.execute(
            select(User).where(
                User.reset_token_hash == token_hash,
                User.reset_token_expires_at > datetime.utcnow(),
            )
        )
        return result.scalar_one_or_none()

    async def reset_password(self, token: str, new_password: str) -> bool:
        """
        使用令牌重置密码。
        成功返回 True，令牌无效或过期返回 False。
        """
        user = await self.verify_reset_token(token)
        if not user:
            return False

        user.hashed_password = get_password_hash(new_password)
        user.reset_token_hash = None
        user.reset_token_expires_at = None
        await self.db.commit()

        logger.info("密码重置成功", extra={"user_id": str(user.id), "email": user.email})
        return True
