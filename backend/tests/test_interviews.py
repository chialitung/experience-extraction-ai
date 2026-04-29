import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.core.database import Base, get_db

# 使用内存数据库进行测试
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


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


client = TestClient(app)


class TestInterviews:
    
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_create_interview(self, setup_database):
        response = client.post("/api/v1/interviews", json={
            "theme": "新任销售代表的异议处理技巧",
            "background": "销售团队新员工培训",
            "expert_role": "资深销售经理",
            "expected_duration": 30,
            "target_output_format": ["script_card"]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["theme"] == "新任销售代表的异议处理技巧"
        assert "id" in data

    def test_list_interviews(self, setup_database):
        # 先创建一个
        client.post("/api/v1/interviews", json={
            "theme": "这是一个测试主题",
            "expected_duration": 30,
            "target_output_format": ["script_card"]
        })

        response = client.get("/api/v1/interviews")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_interview(self, setup_database):
        # 创建
        create_resp = client.post("/api/v1/interviews", json={
            "theme": "这是一个测试主题",
            "expected_duration": 30,
            "target_output_format": ["script_card"]
        })
        interview_id = create_resp.json()["id"]

        # 获取
        response = client.get(f"/api/v1/interviews/{interview_id}")
        assert response.status_code == 200
        assert response.json()["theme"] == "这是一个测试主题"
    
    def test_get_interview_not_found(self, setup_database):
        response = client.get("/api/v1/interviews/12345678-1234-1234-1234-123456789abc")
        assert response.status_code == 404
