import asyncio
import json
import uuid
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.voice.baidu_realtime")

# ===== E2E 演示用：预定义访谈对话文本 =====
# 主题：保险公司营业区组训如何运作一场成功的保险产品说明会（产说会）
# 共 8 轮，覆盖 6 个访谈阶段（部分阶段多轮深挖）
# 第 5 轮包含主题偏离，用于验证系统纠偏功能
MOCK_DIALOGUE = [
    # 第 1 轮：复盘事件（event_review）
    "去年三季度我在营业区组织了一场大型年金保险产品说明会，这场活动从筹备到落地历时整整三周，最终到场客户一百二十位，现场成交率达到了百分之三十二，签单金额超过八百万元，创造了我们营业区当季度的最高纪录。这场产说会的成功不是偶然的，我们在活动前做了大量的准备工作，包括客户画像分析、需求调研、以及多轮内部彩排，确保每一个环节都万无一失。活动当天，我们改变了传统的硬推销模式，采用了教育加体验相结合的方式。首先邀请了一位知名财经专家做宏观经济形势分析，帮助客户建立长期理财的意识；然后由公司精算师详细讲解年金保险的收益模型和风险管理功能；最后安排了一位已经投保三年的真实客户上台分享他的亲身经历和收益情况。这种层层递进的安排让客户从认知到认同再到认购，整个过程非常自然，几乎没有感受到被推销的压力。会后我们还建立了专门的跟进小组，在四十八小时内对每一位到场客户进行了回访，最终把现场成交率从百分之三十二提升到了百分之四十一。这场活动的经验让我深刻认识到，产说会的本质不是推销产品，而是为客户提供一次有价值的学习和体验机会，只有当客户真正感受到价值时，成交才会水到渠成。这一理念后来也成为我们团队组织所有营销活动的核心指导思想。",

    # 第 2 轮：建构框架（framework_build）
    "通过这些年组织产说会的实践，我总结出了一套可复制的五步法框架，每一步都有明确的操作要点和验收标准，新手组训按照这个框架执行，基本可以保证活动效果达到合格线以上。第一步是精准定位，核心是回答三个问题：谁是目标客户、他们有什么痛点、为什么要来参加这场活动。我们要求团队在会前两周完成客户资产分层，筛选出A类客户重点关注，同时为B类和C类客户设计差异化的参与价值。第二步是专业内容设计，遵循七三开原则，百分之七十的时间讲理念、案例和市场分析，只有百分之三十的时间介绍具体产品。内容必须由营业区经理和培训部双重审核，确保专业性和合规性。第三步是氛围营造，从邀请函设计到会场布置，从音乐选择到茶歇安排，每一个细节都要传递专业、信任、温暖的感觉。我们甚至会为每一场活动设计专属的视觉主题色。第四步是互动体验，设置问答环节、小组讨论、现场测算等互动形式，让客户从被动听讲转为主动参与。互动环节的时间占比不低于百分之二十。第五步是跟进转化，建立会后二十四小时和四十八小时双节点跟进机制，由专职顾问负责，确保每一个潜在客户都不遗漏。跟进结果要录入系统，便于后续追踪和复盘。这五步法经过三年多的打磨，已经在我们整个分公司推广使用。",

    # 第 3 轮：挖掘细节-1（detail_mining）
    "在精准定位这个环节，我们有一套非常细致的操作流程，我称之为客户分层预热三步法。首先，设计了一份财富健康问卷，包含十二个问题，涵盖客户的家庭结构、收入来源、资产配置、风险偏好、养老规划等方面，每个问题都有明确的评分标准。这份问卷由顾问在会前一周亲自拜访客户时填写，不是让客户自己填，而是顾问通过面对面沟通引导客户表达真实想法。我们要求顾问在填写过程中做好笔记，记录客户的情绪反应和关注点。然后，我们根据问卷结果把客户分成三个层级：A类客户资产在五百万以上，有明确的财富传承或养老规划需求，是我们的核心目标；B类客户资产在一百万到五百万之间，对稳健理财有兴趣但还在观望，需要持续培育；C类客户资产在一百万以下，主要目的是来学习和建立信任，是未来的潜力客户。不同层级的客户，我们安排的座位区域不同，配备的顾问级别也不同，甚至茶歇时的交流话题都会有所侧重。比如A类客户安排在靠近讲台的前排圆桌，每桌六人，配备资深总监级顾问，茶歇时主动聊家族信托和税务规划；B类客户安排在中排，每桌七人，配备骨干顾问，重点展示专业度；C类客户安排在后排，每桌八人，配备热情积极的新人顾问，重点建立好感。这种精细化的客户分层管理显著提升了我们的邀约成功率和现场转化率。",

    # 第 4 轮：挖掘细节-2（detail_mining）
    "内容设计方面，我们对PPT的结构有非常严格的要求，甚至形成了一套内容设计模板。整个演讲时长控制在六十分钟，分为五个板块：开场破冰五分钟，由主持人用一个真实的理赔案例引发共鸣；市场分析十五分钟，用权威数据说明利率下行趋势和养老缺口；产品理念十五分钟，不直接讲产品，而是讲为什么需要长期稳健的金融工具；客户分享十分钟，邀请真实客户上台讲故事；促成环节十五分钟，由顾问一对一沟通。讲师搭配也很讲究。我们通常安排三个人：一位外部财经专家负责讲市场分析，增强权威性；一位公司内部高级讲师负责讲产品理念，确保专业准确；一位已投保客户负责分享，提供真实感。三位讲师的出场顺序和内容衔接必须提前彩排至少两次。案例选择有三个标准：真实性，必须是真实客户真实数据；贴近性，案例主角的背景要和在场大多数客户相似；启发性，案例要能让客户看到自己未来的可能性。我们建立了一个案例库，目前收录了三十七个经过授权的真实案例，并且每个季度都会更新补充。互动环节我们设计了现场测算工具，顾问用平板电脑帮客户输入年龄、收入、目标，实时生成个性化的养老缺口报告，这个环节客户的参与度非常高，平均有百分之八十的客户会主动要求测算。很多客户现场看到测算结果后，才意识到自己的养老储备存在巨大缺口。",

    # 第 5 轮：偏离轮（先谈障碍然后突然偏离）
    "在组织产说会的过程中，我们确实遇到了不少困难和挑战。最大的障碍是客户的防备心理，很多客户一听是保险说明会就本能地抗拒，觉得去了就是被推销。为了解决这个问题，我们改了活动的名称，不再叫产品说明会，而是叫财富规划沙龙或者养老安全论坛。邀请函的设计也避免使用任何保险相关的视觉元素，而是采用商务论坛的风格。另外一个障碍是现场答疑环节容易失控，有些客户会提出很尖锐的问题，如果处理不好会影响全场氛围。说到这里，我突然想起另外一件事。昨天是周末，天气特别好，阳光明媚，我就去城郊的一个水库钓鱼了。那个水库环境特别优美，周围都是青山绿水，空气非常清新。我早上六点就到了，选了一个背风向阳的位置，用了我自己调配的饵料。结果运气出奇地好，不到两个小时就钓了三条大鱼，最大的一条草鱼足足有八斤重。旁边几位钓友都羡慕得不得了，纷纷来问我用的是什么饵料。钓鱼这件事其实和做保险有异曲同工之妙，都需要耐心、需要技巧、需要抓住时机。你看钓鱼的时候不能急，要等到鱼完全咬钩才能提竿，做保险也是一样的道理，不能急着推销，要等客户真正有需求的时候再促成。反正昨天那场钓鱼真是让我心情愉悦，满载而归。晚上回家让老婆做了一条红烧鱼，另外两条送给了邻居。",

    # 第 6 轮：识别障碍（obstacle_identify）
    "除了刚才提到的客户防备心理和现场答疑失控，还有几个常见的障碍需要重点防范，这些障碍如果处理不好，会严重影响产说会的整体效果。第三个障碍是会后跟进不及时。很多团队把精力都放在活动现场，活动一结束就松懈了，没有及时跟进客户，导致现场有兴趣的客户冷却了。我们的做法是活动结束当晚就整理出客户意向分级表，把客户分成立即促成、持续培育、暂时观望三类，每一类都有对应的跟进策略和时间节点。第四个障碍是顾问专业度参差不齐。有些顾问对产品理解不深，面对客户的深度提问就卡壳了，这会严重影响客户信任。我们要求所有参与产说会的顾问必须通过产品知识考核，并且提前进行话术演练，确保每个人都能流利回答常见问题和异议。第五个障碍是讲师和顾问之间的配合不默契。有时候讲师在台上讲的重点，和顾问在台下跟客户沟通的内容不一致，客户会感到困惑。我们要求每次产说会前必须召开跨部门协调会，统一话术口径和促成策略。还有一个容易被忽视的障碍是现场设备问题，比如投影设备故障、音响效果差、网络不稳定等。这些问题看似小事，但会严重影响活动的专业形象。我们建立了现场设备检查清单，要求提前两小时到场进行全部设备的测试。另外，我们也会准备备用设备和应急预案，确保任何突发状况都能快速处理。",

    # 第 7 轮：提炼工具（tool_extract）
    "这些年我们把产说会的经验沉淀成了几套非常实用的工具，新手组训拿过去可以直接套用，大大缩短了培养周期。第一个工具是产说会筹备检查表，按照会前七天、三天、一天、当天四个时间节点，列出了总共四十八项任务，每项任务都有责任人、验收标准和完成时限。比如会前七天必须完成客户名单筛选和邀约话术培训；会前三天必须完成讲师PPT审核和彩排；会前一天必须完成场地布置和设备测试；当天必须提前两小时到场做最终检查。第二个工具是客户邀约话术模板，分为初次邀约、会前提醒、会后跟进三个版本。每个版本都提供了标准话术和常见异议处理方案。比如客户说没时间，我们教顾问用价值锚定法回应：王总，这次活动我们特意邀请了财经专家分析明年的投资趋势，很多客户听完都说是今年最有价值的一场活动。第三个工具也是最重要的工具，是成交信号识别卡。我们总结了客户产生购买意向时的十二个肢体语言信号，比如频繁点头、主动询问细节、拿出计算器计算、翻阅产品资料超过三次、询问付款方式等。顾问只要观察到客户出现三个以上的信号，就可以进入促成环节，使用标准促成话术。这个工具让我们的顾问促成成功率提升了将近百分之二十，是非常实用的实战工具。目前这套工具包已经成为新人组训上岗培训的必修内容。",

    # 第 8 轮：复述确认（confirmation）
    "总结下来，运作一场成功的保险产品说明会，核心在于四个环节的紧密配合，这四个环节就像四个齿轮，必须咬合在一起才能驱动整个机器运转。第一个环节是精准客户筛选和预热，这是整个活动的基础。没有精准的客户定位，再好的内容和讲师都是白搭。我们强调会前一周的面对面沟通，通过财富健康问卷建立信任、挖掘需求，让客户感受到我们的专业和用心。第二个环节是专业内容设计和讲师搭配，这是活动的核心。七三开的内容比例、真实客户案例、权威外部专家，三者结合才能既有说服力又有可信度。内容必须经过双重审核，讲师必须提前彩排。第三个环节是轻松信任的会场氛围，这是活动的催化剂。从邀请函到会场布置，从音乐到茶歇，每一个细节都要让客户感到被尊重、被重视，而不是被推销。氛围营造的本质是让客户放松警惕，敞开心扉。第四个环节是系统化的会后跟进，这是活动效果的放大器。四十八小时跟进机制、客户意向分级、专职顾问负责，确保每一个潜在客户都能得到及时、专业的服务。跟进不及时，前面的所有努力都可能付诸东流。这四个环节环环相扣，缺一不可。最核心的理念是以客户为中心，把客户的利益放在第一位。当你真正站在客户的角度思考问题，帮助客户解决他们的养老焦虑和财富规划需求时，销售就是一个自然的结果。从邀请函的措辞到茶歇的音乐，从PPT的配色到顾问的着装，每一个触点都要传递一致的专业形象，让客户在每一个细节中感受到我们的用心和专业。",
]


class BaiduRealtimeASRClient:
    """百度实时语音识别 WebSocket 客户端封装

    负责与百度 `wss://vop.baidu.com/realtime_asr` 建立连接、发送 START/FINISH
    控制帧、转发 PCM 音频二进制数据、接收并回调 MID_TEXT / FIN_TEXT 识别结果。

    每个访谈实例应独立创建一个 client（cuid 隔离），避免串音。

    ===== Mock 模式 =====
    当 settings.MOCK_TRANSCRIPTION 为 True 时，不连接百度 ASR，而是按轮次
    从 MOCK_DIALOGUE 中返回预定义的转写文本。用于 E2E 测试和演示录屏。
    """

    BAIDU_WS_URL = "wss://vop.baidu.com/realtime_asr"

    # 类级别：每个 interview_id 的轮次计数器
    _mock_counters: dict[str, int] = {}
    _mock_lock = asyncio.Lock()

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

        # Mock 模式状态
        self._mock_mode = settings.MOCK_TRANSCRIPTION
        self._mock_task: Optional[asyncio.Task] = None

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

        Mock 模式下直接返回 True，不连接百度。

        Returns:
            True 表示连接成功且鉴权通过，False 表示失败
        """
        if self._mock_mode:
            logger.info(
                "实时语音识别进入 Mock 模式，不连接百度 ASR",
                extra={"cuid": self.cuid, "event": "baidu_realtime_mock_mode"},
            )
            self._running = True
            return True

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

        Mock 模式下忽略音频数据，当没有正在运行的 mock 任务时自动触发
        下一条模拟转写结果。支持同一连接内多轮对话。

        Args:
            pcm_data: 16kHz、16bit、单声道 PCM 数据
        """
        if self._mock_mode:
            if self._running and (self._mock_task is None or self._mock_task.done()):
                self._mock_task = asyncio.create_task(self._send_mock_text())
            return

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

    async def _get_next_mock_text(self) -> str:
        """获取当前 interview 的下一轮 mock 转写文本。"""
        async with BaiduRealtimeASRClient._mock_lock:
            idx = BaiduRealtimeASRClient._mock_counters.get(self.cuid, 0)
            if idx < len(MOCK_DIALOGUE):
                text = MOCK_DIALOGUE[idx]
                BaiduRealtimeASRClient._mock_counters[self.cuid] = idx + 1
                return text
            return ""

    async def _send_mock_text(self) -> None:
        """Mock 模式下逐字模拟发送 MID_TEXT / FIN_TEXT 识别结果。

        以 60ms/字的速率逐字递增发送 MID_TEXT，模拟真实实时转写的打字机效果。
        全部文字显示后发送 FIN_TEXT 确认。
        """
        text = await self._get_next_mock_text()
        if not text:
            logger.warning(
                "Mock 转写文本已耗尽",
                extra={"cuid": self.cuid, "event": "baidu_realtime_mock_exhausted"},
            )
            return

        logger.info(
            "Mock 模式开始逐字发送转写结果",
            extra={"cuid": self.cuid, "text_preview": text[:40], "event": "baidu_realtime_mock_start", "char_count": len(text)},
        )

        # 初始延迟 5 秒，模拟用户听到问题后的反应时间
        # 避免在 AI 问题显示前就开始发送转写文本
        await asyncio.sleep(5.0)

        # 逐字发送 MID_TEXT，模拟实时识别效果
        # 语速 500 字/分钟 = 8.33 字/秒 = 120ms/字
        char_delay = 0.12
        for i in range(1, len(text) + 1):
            if not self._running:
                return
            partial = text[:i]
            self._invoke_callback("MID_TEXT", partial)
            if i % 10 == 0:
                logger.debug(
                    "Mock MID_TEXT 逐字更新",
                    extra={"cuid": self.cuid, "progress": f"{i}/{len(text)}", "event": "baidu_realtime_mock_typing"},
                )
            await asyncio.sleep(char_delay)

        # 全部文字显示后，等待 0.3 秒发送 FIN_TEXT 确认
        if not self._running:
            return
        await asyncio.sleep(0.3)
        self._invoke_callback("FIN_TEXT", text)
        logger.info(
            "Mock FIN_TEXT 已发送",
            extra={"cuid": self.cuid, "text_preview": text[:40], "event": "baidu_realtime_mock_fin"},
        )

        # 冷却 2 秒，给前端完成轮次切换（completeRound 清空 currentRound）的时间，
        # 避免下一条 mock 文本在旧轮次被清理前涌入。
        await asyncio.sleep(2.0)

    async def close(self) -> None:
        """发送 FINISH 帧并优雅关闭连接。

        Mock 模式下取消未完成的 mock 任务。
        """
        self._running = False

        if self._mock_task:
            self._mock_task.cancel()
            try:
                await self._mock_task
            except asyncio.CancelledError:
                pass
            self._mock_task = None

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
