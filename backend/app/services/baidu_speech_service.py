import base64
import time
from typing import List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.voice.baidu")


class BaiduSpeechService:
    """百度语音识别服务：access_token 缓存管理 + server_api 调用封装"""

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    API_URL = "https://vop.baidu.com/server_api"

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    async def _get_access_token(self) -> str:
        """获取 access_token，带内存缓存与过期前刷新"""
        # 提前 1 小时刷新，避免边界过期
        if self._access_token and time.time() < self._token_expires_at - 3600:
            return self._access_token

        if not settings.BAIDU_SPEECH_API_KEY or not settings.BAIDU_SPEECH_SECRET_KEY:
            raise ValueError("百度语音 API 密钥未配置，请在 .env 中设置 BAIDU_SPEECH_API_KEY 和 BAIDU_SPEECH_SECRET_KEY")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.TOKEN_URL,
                params={
                    "grant_type": "client_credentials",
                    "client_id": settings.BAIDU_SPEECH_API_KEY,
                    "client_secret": settings.BAIDU_SPEECH_SECRET_KEY,
                },
            )
            data = resp.json()

        if "access_token" not in data:
            err_msg = data.get("error_description") or data.get("error") or str(data)
            raise ValueError(f"获取百度 access_token 失败: {err_msg}")

        self._access_token = data["access_token"]
        # expires_in 默认 30 天，取回的值通常以秒为单位
        expires_in = data.get("expires_in", 2592000)
        self._token_expires_at = time.time() + expires_in

        logger.info(
            "Baidu access_token refreshed",
            extra={"expires_in": expires_in, "event": "baidu_token_refresh"},
        )
        return self._access_token

    async def recognize(self, audio_base64: str, audio_len: int, cuid: str) -> List[str]:
        """
        调用百度短语音识别标准版 API

        Args:
            audio_base64: Base64 编码的音频数据（WAV 格式）
            audio_len: 原始音频字节长度
            cuid: 用户唯一标识（这里用 interview_id）

        Returns:
            识别结果文本列表（通常只有一条）
        """
        token = await self._get_access_token()

        payload = {
            "format": "wav",
            "rate": 16000,
            "channel": 1,
            "cuid": cuid,
            "token": token,
            "speech": audio_base64,
            "len": audio_len,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.API_URL, json=payload)
            data = resp.json()

        err_no = data.get("err_no")
        if err_no != 0:
            err_msg = data.get("err_msg", "未知错误")
            logger.error(
                "百度语音识别失败",
                extra={
                    "err_no": err_no,
                    "err_msg": err_msg,
                    "cuid": cuid,
                    "sn": data.get("sn"),
                    "event": "baidu_recognize_error",
                },
            )
            raise ValueError(f"百度识别失败 [err_no={err_no}]: {err_msg}")

        results = data.get("result", [])
        logger.info(
            "百度语音识别成功",
            extra={
                "cuid": cuid,
                "result_count": len(results),
                "sn": data.get("sn"),
                "event": "baidu_recognize_success",
            },
        )
        return results


# 全局服务实例
baidu_speech_service = BaiduSpeechService()
