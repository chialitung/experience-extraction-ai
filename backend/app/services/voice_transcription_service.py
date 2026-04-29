import base64
from typing import List, Optional
from app.services.baidu_speech_service import baidu_speech_service
from app.services.llm_service import llm_service
from app.core.logging import get_logger

logger = get_logger("app.voice.transcription")


class VoiceTranscriptionService:
    """语音转录协调服务：接收音频 → 调百度识别 → LLM 过滤 AI 提问 → 返回纯专家回答"""

    async def transcribe_segment(
        self,
        interview_id: str,
        audio_base64: str,
        segment_index: int,
        recent_questions: List[str],
    ) -> Optional[str]:
        """
        转录单段音频，返回过滤后的专家回答文字

        Args:
            interview_id: 访谈ID
            audio_base64: Base64 编码的 WAV 音频
            segment_index: 片段序号（用于日志追踪）
            recent_questions: 最近几条 AI 提问内容，用于过滤

        Returns:
            过滤后的专家回答文字，若识别为空或失败则返回 None
        """
        try:
            # 1. Base64 解码获取原始字节长度
            audio_bytes = base64.b64decode(audio_base64)
            audio_len = len(audio_bytes)

            logger.info(
                f"Recognizing audio segment {segment_index} for interview {interview_id}",
                extra={
                    "interview_id": interview_id,
                    "segment_index": segment_index,
                    "audio_len": audio_len,
                    "event": "voice_recognize_start",
                },
            )

            # 2. 调用百度语音识别
            results = await baidu_speech_service.recognize(
                audio_base64=audio_base64,
                audio_len=audio_len,
                cuid=str(interview_id),
            )
            raw_text = "".join(results)

            if not raw_text.strip():
                logger.info(
                    f"Empty transcription for segment {segment_index}",
                    extra={
                        "interview_id": interview_id,
                        "segment_index": segment_index,
                        "event": "voice_recognize_empty",
                    },
                )
                return None

            # 3. LLM 过滤 AI 提问内容
            filtered_text = await self._filter_ai_questions(raw_text, recent_questions)

            # 如果过滤后为空，说明整段都是 AI 提问的回音
            if not filtered_text or not filtered_text.strip():
                logger.info(
                    f"Segment {segment_index} filtered to empty (all AI echo)",
                    extra={
                        "interview_id": interview_id,
                        "segment_index": segment_index,
                        "event": "voice_filter_all_echo",
                    },
                )
                return None

            logger.info(
                f"Transcription complete for segment {segment_index}",
                extra={
                    "interview_id": interview_id,
                    "segment_index": segment_index,
                    "raw_length": len(raw_text),
                    "filtered_length": len(filtered_text),
                    "event": "voice_recognize_complete",
                },
            )

            return filtered_text.strip()

        except Exception as e:
            logger.error(
                f"Transcription failed for segment {segment_index}: {e}",
                extra={
                    "interview_id": interview_id,
                    "segment_index": segment_index,
                    "event": "voice_recognize_error",
                },
                exc_info=True,
            )
            # 降级：若原始转录已获取，返回原始文字（不过滤）
            try:
                if "raw_text" in locals() and raw_text:
                    return raw_text.strip()
            except Exception:
                pass
            return None

    async def _filter_ai_questions(self, transcription: str, recent_questions: List[str]) -> str:
        """
        使用 LLM 从转录文字中过滤掉专家复述的 AI 提问内容

        若最近没有 AI 提问，或 LLM 调用失败，直接返回原始文字
        """
        if not recent_questions:
            return transcription

        questions_text = "\n".join([f"{i + 1}. {q}" for i, q in enumerate(recent_questions)])

        system_prompt = (
            "你是一个语音转录文本清洗助手。你的任务是从语音识别的结果中，"
            "剔除专家复述 AI 提问的内容，只保留专家自己的原创回答。\n\n"
            "规则：\n"
            "1. 如果转录文字中包含与\"最近AI提问\"高度相似或逐字复述的句子，请删除这些部分\n"
            "2. 专家有时会在回答前重复 AI 的问题，这部分需要剔除\n"
            "3. 如果整段文字都是 AI 提问的回音或复述，返回空字符串\n"
            "4. 只返回过滤后的专家回答文字，不要有任何解释、分析或总结\n"
            "5. 保持专家回答的原始措辞和语气"
        )

        messages = [
            {
                "role": "user",
                "content": (
                    f"【最近 AI 提出的问题】\n{questions_text}\n\n"
                    f"【语音识别转录的整段文字】\n{transcription}\n\n"
                    "请从转录文字中剔除 AI 提问的内容，只保留专家自己的回答。"
                    "直接返回过滤后的文字，不要添加任何说明。"
                ),
            }
        ]

        try:
            result = await llm_service.generate_json(
                system_prompt, messages, temperature=0.1, max_tokens=2000
            )
            # 兼容多种可能的返回字段
            filtered = (
                result.get("filtered_text")
                or result.get("answer")
                or result.get("content")
                or result.get("result")
                or transcription
            )
            return filtered.strip()
        except Exception as e:
            logger.warning(
                f"LLM filter failed, returning raw transcription: {e}",
                extra={"event": "voice_filter_fallback"},
            )
            # 降级：返回原始文字
            return transcription


# 全局服务实例
voice_transcription_service = VoiceTranscriptionService()
