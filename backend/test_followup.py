import asyncio
import json
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine, AsyncSessionLocal
from app.models.interview import Interview
from app.services.interview_service import InterviewService
from app.core.config import settings

async def test():
    print(f"LLM Provider: {settings.DEFAULT_LLM_PROVIDER}")
    key = settings.OPENAI_API_KEY
    print(f"OPENAI_KEY present: {bool(key and len(key) > 10)}")
    key2 = settings.DEEPSEEK_API_KEY
    print(f"DEEPSEEK_KEY present: {bool(key2 and len(key2) > 10)}")

    async with AsyncSessionLocal() as db:
        service = InterviewService(db)

        result = await db.execute(select(Interview).order_by(desc(Interview.created_at)).limit(1))
        interview = result.scalar_one_or_none()
        if not interview:
            print("无访谈")
            return

        print(f"\n测试访谈: {interview.id}")
        print(f"主题: {interview.theme}")

        msgs = await service.get_messages(interview.id, limit=10)
        print(f"当前消息数: {len(msgs)}")
        for m in msgs:
            print(f"  [{m.role}] {m.content[:80]}...")

        test_answer = "测试回答：我曾经遇到一个客户，对我们产品很感兴趣但一直不下单。后来我通过了解他的真实需求，成功促成了合作。"
        print(f"\n模拟发送用户回答...")
        try:
            response = await service.generate_ai_response(interview.id, test_answer)
            print(f"AI 回复已生成")
            q = response.get("question", {})
            print(f"Type: {q.get('type')}")
            print(f"Content: {q.get('content', '')[:300]}")
            print(f"Thinking: {response.get('thinking', '')[:200]}")
        except Exception as e:
            print(f"错误: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
