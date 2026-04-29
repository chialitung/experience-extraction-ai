import asyncio
import json
import uuid
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.voice.baidu_realtime")


class BaiduRealtimeASRClient:
    """百度实时语音识别 WebSocket 客户端封装

    负责与百度 `wss://vop.baidu.com/realtime_asr` 建立连接、发送 START/FINISH
    控制帧、转发 PCM 音频二进制数据、接收并回调 MID_TEXT / FIN_TEXT 识别结果。

    每个访谈实例应独立创建一个 client（cuid 隔离），避免串音。
    """

    BAIDU_WS_URL = "wss://vop.baidu.com/realtime_asr"

    def __init__(self, cuid: str, dev_pid: int = 15372):
        """
        Args:
            cuid: 用户/会话唯一标识（这里使用 interview_id）
            dev_pid: 百度模型 ID，默认 15372（中文普通话，加强标点）
        """
        self.cuid = cuid
        self.dev_pid = dev_pid
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._on_result: Optional[Callable[[str, str], None]] = None
        self._receive_task: Optional[asyncio.Task] = None

    def _invoke_callback(self, result_type: str, text: str) -> None:
        """安全调用回调，支持同步和异步函数。"""
        if self._on_result is None:
            return
        try:
            result = self._on_result(result_type, text)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        except Exception as e:
            logger.error(
                "百度识别结果回调执行失败",
                extra={"error": str(e), "cuid": self.cuid},
            )

    def on_result(self, callback: Callable[[str, str], None]) -> None:
        """注册识别结果回调。

        callback(type: str, text: str)
            type 取值："MID_TEXT" | "FIN_TEXT" | "ERROR"
        """
        self._on_result = callback

    async def connect(self) -> bool:
        """建立与百度实时语音识别服务的 WebSocket 连接并发送 START 帧。

        发送 START 帧后会等待百度的首条响应，确认鉴权通过后才返回 True。

        Returns:
            True 表示连接成功且鉴权通过，False 表示失败
        """
        if not settings.BAIDU_SPEECH_APP_ID or not settings.BAIDU_SPEECH_API_KEY:
            logger.error(
                "百度语音配置不完整，无法连接实时语音识别",
                extra={
                    "has_app_id": bool(settings.BAIDU_SPEECH_APP_ID),
                    "has_api_key": bool(settings.BAIDU_SPEECH_API_KEY),
                    "event": "baidu_realtime_config_missing",
                },
            )
            return False

        try:
            sn = str(uuid.uuid4()).replace("-", "")
            url = f"{self.BAIDU_WS_URL}?sn={sn}"

            self._ws = await websockets.connect(url)

            start_msg = {
                "type": "START",
                "data": {
                    "appid": int(settings.BAIDU_SPEECH_APP_ID),
                    "appkey": settings.BAIDU_SPEECH_API_KEY,
                    "dev_pid": self.dev_pid,
                    "cuid": self.cuid,
                    "sample": 16000,
                    "format": "pcm",
                },
            }
            await self._ws.send(json.dumps(start_msg))
            logger.info(
                "START 帧已发送，等待百度鉴权响应",
                extra={
                    "cuid": self.cuid,
                    "dev_pid": self.dev_pid,
                    "sn": sn,
                    "event": "baidu_realtime_start_sent",
                },
            )

            # 百度实时语音识别不会在 START 后立即返回鉴权结果，
            # 而是在收到音频后通过识别结果中的 err_no 体现错误。
            # 因此不等待首条响应，直接启动接收循环。
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())

            logger.info(
                "百度实时语音识别连接成功",
                extra={
                    "cuid": self.cuid,
                    "dev_pid": self.dev_pid,
                    "sn": sn,
                    "event": "baidu_realtime_connected",
                },
            )
            return True

        except Exception as e:
            logger.error(
                f"百度实时语音识别连接失败: {e}",
                extra={"cuid": self.cuid, "event": "baidu_realtime_connect_error"},
                exc_info=True,
            )
            return False

    async def send_audio(self, pcm_data: bytes) -> None:
        """转发 PCM 音频二进制数据到百度。

        Args:
            pcm_data: 16kHz、16bit、单声道 PCM 数据
        """
        if not self._ws or not self._running:
            return
        try:
            await self._ws.send(pcm_data)
        except ConnectionClosed:
            # 连接已正常关闭，无需记录错误
            pass
        except Exception as e:
            logger.error(
                "发送音频数据失败",
                extra={"error": str(e), "event": "baidu_realtime_send_error"},
            )

    def _parse_result_text(self, data: dict) -> str:
        """解析百度返回的识别文本。

        百度文档定义返回格式为顶层字段，但旧版或不同场景可能使用嵌套 data 对象。
        兼容两种格式：{"result":"..."} 和 {"data":{"result":"..."}}
        """
        # 优先读取顶层 result（百度文档标准格式）
        text = data.get("result", "")
        if text:
            return text
        # 兼容旧版嵌套格式
        nested = data.get("data", {})
        if isinstance(nested, dict):
            return nested.get("result", "")
        return ""

    def _parse_error_desc(self, data: dict) -> str:
        """解析百度返回的错误描述。兼容顶层和嵌套格式。"""
        err_msg = data.get("err_msg", "")
        if err_msg:
            return err_msg
        nested = data.get("data", {})
        if isinstance(nested, dict):
            return nested.get("desc", "未知错误")
        return "未知错误"

    async def _receive_loop(self, first_msg: Optional[str] = None) -> None:
        """后台协程：持续接收百度返回的识别结果并触发回调。

        Args:
            first_msg: connect() 中已读取的首条消息（如有）
        """
        messages_to_process = []
        if first_msg is not None and isinstance(first_msg, str):
            messages_to_process.append(first_msg)

        while self._running and self._ws:
            try:
                if messages_to_process:
                    message = messages_to_process.pop(0)
                else:
                    message = await self._ws.recv()

                if isinstance(message, bytes):
                    logger.debug(
                        "收到百度二进制消息，忽略",
                        extra={"cuid": self.cuid},
                    )
                    continue

                # 记录原始消息用于调试（限制长度避免日志膨胀）
                raw_preview = message[:500] if len(message) > 500 else message
                logger.info(
                    "收到百度消息",
                    extra={"raw": raw_preview, "cuid": self.cuid},
                )

                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning(
                        "百度消息 JSON 解析失败",
                        extra={"raw": raw_preview, "cuid": self.cuid},
                    )
                    continue

                msg_type = data.get("type")

                # 优先检查错误码（百度错误可能以任意 type 返回，包括 FIN_TEXT）
                err_no = data.get("err_no")
                if err_no is not None and err_no != 0:
                    err_msg = self._parse_error_desc(data)
                    logger.error(
                        "百度实时识别服务端报错",
                        extra={
                            "err_no": err_no,
                            "err_msg": err_msg,
                            "msg_type": msg_type,
                            "cuid": self.cuid,
                            "event": "baidu_realtime_server_error",
                        },
                    )
                    self._invoke_callback("ERROR", f"[{err_no}] {err_msg}")
                    continue

                if msg_type == "MID_TEXT":
                    text = self._parse_result_text(data)
                    logger.info(
                        "百度 MID_TEXT",
                        extra={"text": text, "cuid": self.cuid, "event": "baidu_mid_text"},
                    )
                    if text:
                        self._invoke_callback("MID_TEXT", text)

                elif msg_type == "FIN_TEXT":
                    text = self._parse_result_text(data)
                    logger.info(
                        "百度 FIN_TEXT",
                        extra={"text": text, "cuid": self.cuid, "event": "baidu_fin_text"},
                    )
                    if text:
                        self._invoke_callback("FIN_TEXT", text)

                elif msg_type == "HEARTBEAT":
                    logger.debug(
                        "收到百度心跳",
                        extra={"cuid": self.cuid, "event": "baidu_heartbeat"},
                    )

                else:
                    logger.info(
                        "收到未知类型百度消息",
                        extra={"type": msg_type, "raw": raw_preview, "cuid": self.cuid, "event": "baidu_unknown_msg"},
                    )

            except ConnectionClosed:
                logger.info(
                    "百度实时识别连接已关闭",
                    extra={"event": "baidu_realtime_closed"},
                )
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"接收识别结果异常: {e}",
                    extra={"event": "baidu_realtime_receive_error"},
                    exc_info=True,
                )
                break

        self._running = False

    async def close(self) -> None:
        """发送 FINISH 帧并优雅关闭连接。"""
        self._running = False

        if self._ws:
            try:
                if self._ws.open:
                    await self._ws.send(json.dumps({"type": "FINISH"}))
                    await asyncio.sleep(0.3)
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        logger.info(
            "百度实时识别连接已清理",
            extra={"event": "baidu_realtime_cleanup"},
        )
