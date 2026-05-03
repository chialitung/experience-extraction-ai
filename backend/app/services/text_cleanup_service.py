import json
from typing import List, Dict, Any
from app.services.llm_service import llm_service
from app.services.prompt_manager import prompt_manager
from app.core.logging import get_logger


logger = get_logger("app.text_cleanup")


class TextCleanupService:
    """访谈文本清理服务

    使用LLM从原始访谈记录中识别并去除无效内容（寒暄、口头禅、跑题等），
    提取有效的问答对。
    """

    # 每段最大字符数，超过则分段处理
    CHUNK_SIZE = 5000

    async def cleanup(self, raw_text: str) -> List[Dict[str, str]]:
        """清理原始访谈文本

        Args:
            raw_text: 原始访谈文字记录

        Returns:
            List[{"role": "interviewer|expert", "content": "..."}]
        """
        if not raw_text or len(raw_text.strip()) < 50:
            return []

        text = raw_text.strip()

        # 如果文本较短，直接一次性处理
        if len(text) <= self.CHUNK_SIZE:
            return await self._cleanup_chunk(text)

        # 长文本分段处理
        chunks = self._split_into_chunks(text)
        logger.info(f"Text cleanup: splitting into {len(chunks)} chunks, total {len(text)} chars")

        all_messages = []
        for i, chunk in enumerate(chunks):
            chunk_messages = await self._cleanup_chunk(chunk)
            all_messages.extend(chunk_messages)
            logger.info(f"Chunk {i+1}/{len(chunks)} cleaned: {len(chunk_messages)} messages")

        # 合并同一角色的连续消息
        merged = self._merge_consecutive_messages(all_messages)
        logger.info(f"Text cleanup completed: {len(merged)} messages after merge")
        return merged

    def _split_into_chunks(self, text: str) -> List[str]:
        """按段落边界将文本切分成段"""
        if len(text) <= self.CHUNK_SIZE:
            return [text]

        # 按段落分割（双换行符）
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前段落本身超过限制，直接作为一个段
            if len(para) > self.CHUNK_SIZE:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                chunks.append(para)
                continue

            # 尝试将段落加入当前段
            if len(current_chunk) + len(para) + 2 <= self.CHUNK_SIZE:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def _cleanup_chunk(self, chunk: str) -> List[Dict[str, str]]:
        """清理单个文本段"""
        try:
            prompt = prompt_manager.render(
                "tasks/text_cleanup.md",
                {"raw_text": chunk},
            )

            system_prompt = (
                "你是一位专业的访谈记录整理专家。"
                "你的任务是从原始访谈文字记录中识别并提取有效内容，去除无效信息。"
                "严格按JSON格式输出，不要输出任何额外文字。"
            )

            response = await llm_service.generate_json(
                system_prompt,
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=4000,
            )

            messages = response.get("messages", [])
            if not isinstance(messages, list):
                logger.warning(f"Unexpected cleanup response format: {type(messages)}")
                return []

            # 验证消息格式
            valid_messages = []
            for msg in messages:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    role = msg["role"]
                    content = msg["content"]
                    if role in ("interviewer", "expert") and content and len(content.strip()) > 5:
                        valid_messages.append({
                            "role": role,
                            "content": content.strip(),
                        })

            return valid_messages

        except Exception as e:
            logger.error(f"Text cleanup chunk failed: {e}", exc_info=True)
            return []

    def _merge_consecutive_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """合并同一角色的连续消息"""
        if not messages:
            return []

        merged = []
        current_role = None
        current_content = ""

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "").strip()

            if not content:
                continue

            if role == current_role:
                current_content += "\n" + content
            else:
                if current_role and current_content:
                    merged.append({"role": current_role, "content": current_content.strip()})
                current_role = role
                current_content = content

        # 添加最后一个
        if current_role and current_content:
            merged.append({"role": current_role, "content": current_content.strip()})

        return merged


# 全局实例
text_cleanup_service = TextCleanupService()
