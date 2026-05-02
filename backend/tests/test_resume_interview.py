"""
测试访谈 /resume 端点 + completed 状态守卫。

覆盖：
1. service.resume_interview: completed → confirmation, status active, 写入 state_history
2. POST /interviews/{id}/resume 端点
3. POST /interviews/{id}/messages 在 completed 状态返回 409
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.core.database import Base, get_db
from app.models.interview import Interview, InterviewState, InterviewStatus
from app.services.interview_service import InterviewService


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture(scope="function")
async def setup_database():
    """每个测试都重新建表 + 注入 override，结束后恢复，避免与其它测试模块冲突。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original_override
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


client = TestClient(app)


def _create_interview() -> str:
    """创建一个访谈并返回其 id"""
    response = client.post(
        "/api/v1/interviews",
        json={
            "theme": "测试 resume 接口的访谈主题",
            "expected_duration": 30,
            "target_output_format": ["script_card"],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _force_complete_interview(interview_id: str) -> None:
    """直接在数据库里把访谈置为 completed 状态（绕过 LLM）"""
    from sqlalchemy import update as sa_update

    async with TestingSessionLocal() as session:
        await session.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(
                current_state=InterviewState.COMPLETED,
                status=InterviewStatus.COMPLETED,
            )
        )
        await session.commit()


# ==================== Service-level tests ====================

class TestResumeInterviewService:
    @pytest.mark.asyncio
    async def test_resume_interview_resets_state_to_confirmation(self, setup_database):
        """service.resume_interview 应把 completed → confirmation"""
        interview_id = _create_interview()
        await _force_complete_interview(interview_id)

        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            updated = await service.resume_interview(interview_id)
            await session.commit()

        assert updated is not None
        assert updated.current_state == InterviewState.CONFIRMATION

    @pytest.mark.asyncio
    async def test_resume_interview_resets_status_to_active(self, setup_database):
        """service.resume_interview 应把 status completed → active"""
        interview_id = _create_interview()
        await _force_complete_interview(interview_id)

        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            updated = await service.resume_interview(interview_id)
            await session.commit()

        assert updated.status == InterviewStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_resume_interview_appends_state_history(self, setup_database):
        """service.resume_interview 应往 state_history 追加 action="resumed" 条目"""
        interview_id = _create_interview()
        await _force_complete_interview(interview_id)

        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            updated = await service.resume_interview(interview_id)
            await session.commit()

        history = updated.state_history or []
        assert len(history) >= 1
        last_entry = history[-1]
        assert last_entry.get("action") == "resumed"
        assert last_entry.get("from") == "completed"
        assert "transitioned_at" in last_entry

    @pytest.mark.asyncio
    async def test_resume_interview_not_found_raises(self, setup_database):
        """不存在的访谈应抛 ValueError"""
        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            with pytest.raises(ValueError):
                await service.resume_interview("00000000-0000-0000-0000-000000000000")


# ==================== API endpoint tests ====================

class TestResumeInterviewEndpoint:
    def test_resume_endpoint_returns_200_with_updated_state(self, setup_database):
        """POST /interviews/{id}/resume 返回 200 且 current_state=confirmation"""
        import asyncio

        interview_id = _create_interview()
        asyncio.get_event_loop().run_until_complete(
            _force_complete_interview(interview_id)
        )

        response = client.post(f"/api/v1/interviews/{interview_id}/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["current_state"] == "confirmation"
        assert data["status"] == "active"

    def test_resume_endpoint_404_when_not_found(self, setup_database):
        """访谈不存在时返回 404"""
        response = client.post(
            "/api/v1/interviews/00000000-0000-0000-0000-000000000000/resume"
        )
        assert response.status_code == 404


# ==================== send_message guard ====================

class TestSendMessageCompletedGuard:
    def test_send_message_returns_409_when_completed(self, setup_database):
        """已完成的访谈不允许再发消息，应返回 409"""
        import asyncio

        interview_id = _create_interview()
        asyncio.get_event_loop().run_until_complete(
            _force_complete_interview(interview_id)
        )

        response = client.post(
            f"/api/v1/interviews/{interview_id}/messages",
            json={"content": "继续聊一下"},
        )
        assert response.status_code == 409



client = TestClient(app)


def _create_interview() -> str:
    """创建一个访谈并返回其 id"""
    response = client.post(
        "/api/v1/interviews",
        json={
            "theme": "测试 resume 接口的访谈主题",
            "expected_duration": 30,
            "target_output_format": ["script_card"],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _force_complete_interview(interview_id: str) -> None:
    """直接在数据库里把访谈置为 completed 状态（绕过 LLM）"""
    from sqlalchemy import update as sa_update

    async with TestingSessionLocal() as session:
        await session.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(
                current_state=InterviewState.COMPLETED,
                status=InterviewStatus.COMPLETED,
            )
        )
        await session.commit()


# ==================== Service-level tests ====================

class TestResumeInterviewService:
    @pytest.mark.asyncio
    async def test_resume_interview_resets_state_to_confirmation(self, setup_database):
        """service.resume_interview 应把 completed → confirmation"""
        interview_id = _create_interview()
        await _force_complete_interview(interview_id)

        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            updated = await service.resume_interview(interview_id)
            await session.commit()

        assert updated is not None
        assert updated.current_state == InterviewState.CONFIRMATION

    @pytest.mark.asyncio
    async def test_resume_interview_resets_status_to_active(self, setup_database):
        """service.resume_interview 应把 status completed → active"""
        interview_id = _create_interview()
        await _force_complete_interview(interview_id)

        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            updated = await service.resume_interview(interview_id)
            await session.commit()

        assert updated.status == InterviewStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_resume_interview_appends_state_history(self, setup_database):
        """service.resume_interview 应往 state_history 追加 action="resumed" 条目"""
        interview_id = _create_interview()
        await _force_complete_interview(interview_id)

        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            updated = await service.resume_interview(interview_id)
            await session.commit()

        history = updated.state_history or []
        assert len(history) >= 1
        last_entry = history[-1]
        assert last_entry.get("action") == "resumed"
        assert last_entry.get("from") == "completed"
        assert "transitioned_at" in last_entry

    @pytest.mark.asyncio
    async def test_resume_interview_not_found_raises(self, setup_database):
        """不存在的访谈应抛 ValueError"""
        async with TestingSessionLocal() as session:
            service = InterviewService(session)
            with pytest.raises(ValueError):
                await service.resume_interview("00000000-0000-0000-0000-000000000000")


# ==================== API endpoint tests ====================

class TestResumeInterviewEndpoint:
    def test_resume_endpoint_returns_200_with_updated_state(self, setup_database):
        """POST /interviews/{id}/resume 返回 200 且 current_state=confirmation"""
        import asyncio

        interview_id = _create_interview()
        asyncio.get_event_loop().run_until_complete(
            _force_complete_interview(interview_id)
        )

        response = client.post(f"/api/v1/interviews/{interview_id}/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["current_state"] == "confirmation"
        assert data["status"] == "active"

    def test_resume_endpoint_404_when_not_found(self, setup_database):
        """访谈不存在时返回 404"""
        response = client.post(
            "/api/v1/interviews/00000000-0000-0000-0000-000000000000/resume"
        )
        assert response.status_code == 404


# ==================== send_message guard ====================

class TestSendMessageCompletedGuard:
    def test_send_message_returns_409_when_completed(self, setup_database):
        """已完成的访谈不允许再发消息，应返回 409"""
        import asyncio

        interview_id = _create_interview()
        asyncio.get_event_loop().run_until_complete(
            _force_complete_interview(interview_id)
        )

        response = client.post(
            f"/api/v1/interviews/{interview_id}/messages",
            json={"content": "继续聊一下"},
        )
        assert response.status_code == 409
