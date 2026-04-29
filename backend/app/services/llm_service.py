import hashlib
import json
import os
import time
from typing import AsyncIterator, Optional, Dict, Any, Literal
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from app.core.config import settings
from app.core.cache import llm_response_cache
from app.core.logging import get_logger

logger = get_logger("app.llm")


class LLMService:
    """LLM服务封装：支持多供应商、流式输出、JSON模式"""
    
    def __init__(self, provider: Optional[Literal["openai", "anthropic", "deepseek"]] = None):
        self.provider = provider or settings.DEFAULT_LLM_PROVIDER
        self.openai_client: Optional[AsyncOpenAI] = None
        self.anthropic_client: Optional[AsyncAnthropic] = None
        self.mock_mode = False
        
        if self.provider == "openai" and settings.OPENAI_API_KEY:
            # 检测是否为占位符/API Key无效，启用模拟模式
            if settings.OPENAI_API_KEY in ("your-moonshot-api-key-here", "sk-your-openai-key", "", None):
                self.mock_mode = True
            else:
                client_kwargs = {"api_key": settings.OPENAI_API_KEY}
                if settings.OPENAI_BASE_URL:
                    client_kwargs["base_url"] = settings.OPENAI_BASE_URL
                self.openai_client = AsyncOpenAI(**client_kwargs)
        elif self.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            if settings.ANTHROPIC_API_KEY in ("sk-ant-your-anthropic-key", "", None):
                self.mock_mode = True
            else:
                self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        elif self.provider == "deepseek" and settings.DEEPSEEK_API_KEY:
            if settings.DEEPSEEK_API_KEY in ("sk-your-deepseek-key", "", None):
                self.mock_mode = True
            else:
                client_kwargs = {"api_key": settings.DEEPSEEK_API_KEY}
                if settings.DEEPSEEK_BASE_URL:
                    client_kwargs["base_url"] = settings.DEEPSEEK_BASE_URL
                self.openai_client = AsyncOpenAI(**client_kwargs)
        else:
            self.mock_mode = True
    
    def _get_mock_json_response(self, system_prompt: str) -> Dict[str, Any]:
        """根据系统提示词类型返回模拟JSON响应"""
        prompt_lower = system_prompt.lower()
        if "blueprint" in prompt_lower or "蓝图" in system_prompt:
            return {
                "blueprint": {
                    "objective": "萃取资深销售在客户异议处理方面的核心经验，形成标准化打法",
                    "event_definition": "客户提出价格异议或竞品对比时的应对场景",
                    "key_questions": [
                        {"question": "请回忆一次您成功化解客户价格异议的具体案例", "objective": "获取标杆案例", "strategy": "事实性问题+情绪接纳"},
                        {"question": "当时客户提出了哪些具体的异议点？", "objective": "还原客户真实诉求", "strategy": "事实性问题"},
                        {"question": "您当时的第一反应和应对思路是什么？", "objective": "挖掘决策逻辑", "strategy": "探索性问题"},
                    ],
                    "expected_value": [
                        {"dimension": "金", "indicator": "提高新人销售成交率15%以上"},
                        {"dimension": "木", "indicator": "形成标准化异议处理SOP"},
                    ],
                    "structure_plan": [
                        {"step": "复盘事件", "duration": "10min", "focus": "还原具体案例"},
                        {"step": "建构框架", "duration": "10min", "focus": "归纳应对策略"},
                        {"step": "挖掘细节", "duration": "15min", "focus": "细化关键动作"},
                        {"step": "识别障碍", "duration": "5min", "focus": "常见误区预警"},
                        {"step": "提炼工具", "duration": "3min", "focus": "输出话术模板"},
                        {"step": "复述确认", "duration": "2min", "focus": "验证理解一致性"},
                    ],
                    "risk_notes": ["避免空泛理论，聚焦具体案例", "关注客户心理变化过程"],
                }
            }
        elif "question" in prompt_lower or "问题" in system_prompt or "提问" in system_prompt:
            return {
                "question": {
                    "type": "探索性",
                    "content": "您提到当时客户对价格有异议，能否详细描述一下客户当时具体说了什么？您的第一反应是什么？",
                    "purpose": "深入挖掘专家面对异议时的真实思考过程和关键动作",
                    "value_dimension": "木（有难度）",
                },
                "structured_update": {
                    "event_description": "客户因价格高于竞品而犹豫",
                    "key_actions": ["倾听客户诉求", "不急于反驳"],
                },
                "thinking": "专家已初步描述场景，需要进一步追问具体细节",
                "state_assessment": {
                    "current_step": "复盘事件",
                    "step_progress": "30%",
                    "should_advance": True,
                    "information_gaps": ["客户具体异议内容", "专家的第一反应细节"],
                },
            }
        elif "extract" in prompt_lower or "萃取" in system_prompt or "结构化" in system_prompt:
            return {
                "extracted_data": {
                    "event_description": "客户提出价格异议，认为产品价格高于竞品20%",
                    "key_actions": [
                        "先认同客户感受：我理解您的考虑",
                        "转移焦点到价值：让我们看看您实际获得的是什么",
                        "用ROI计算化解：按使用周期摊薄，实际每天成本仅X元",
                        "提供替代方案：如果预算紧张，可以先从基础版开始",
                    ],
                    "decision_logic": "不直接反驳价格，而是重塑价值认知，让客户自己得出'值得'的结论",
                    "obstacles": ["急于解释/反驳", "直接降价", "忽视客户真实需求"],
                    "tools": ["价值对比表", "ROI计算器话术", "三段式回应模板"],
                    "value_assessment": {"金": 0.9, "木": 0.8, "水": 0.7, "火": 0.6, "土": 0.5},
                }
            }
        elif "output" in prompt_lower or "封装" in system_prompt or "成果" in system_prompt:
            return {
                "script_card": {
                    "title": "客户价格异议处理：从对抗到共赢的四步法",
                    "scenario": "客户明确提及价格高于竞品，表现出犹豫或要求降价",
                    "steps": [
                        {"step": 1, "action": "情绪接纳", "script": "我理解您的考虑，很多客户初期也有类似想法", "key_points": ["先认同再引导", "避免对抗性语言"], "pitfalls": ["急于解释或反驳"]},
                        {"step": 2, "action": "价值重塑", "script": "让我们看看您实际获得的是什么", "key_points": ["转移焦点到价值", "对比总拥有成本"], "pitfalls": ["空谈价值没有数据支撑"]},
                        {"step": 3, "action": "量化论证", "script": "按使用周期摊薄，实际每天成本仅X元", "key_points": ["用ROI计算", "提供具体数字"], "pitfalls": ["计算复杂让客户失去耐心"]},
                        {"step": 4, "action": "灵活方案", "script": "如果预算紧张，可以先从基础版开始", "key_points": ["保留成交空间", "分层推荐"], "pitfalls": ["直接降价损害利润"]}
                    ],
                    "summary": "核心要点：先接纳情绪，再重塑价值认知，用数据量化论证，最后提供灵活方案。"
                },
                "checklist": {
                    "title": "客户价格异议处理检查表",
                    "checklist": [
                        {"category": "事前准备", "items": [
                            {"item": "了解客户预算范围和决策流程", "importance": "高"},
                            {"item": "准备竞品对比资料和价值计算器", "importance": "高"},
                            {"item": "预设至少2个替代方案", "importance": "中"}
                        ]},
                        {"category": "现场应对", "items": [
                            {"item": "先认同客户感受，不直接反驳", "importance": "高"},
                            {"item": "用数据支撑价值论点", "importance": "高"},
                            {"item": "观察客户反应，判断真实顾虑", "importance": "中"}
                        ]},
                        {"category": "事后跟进", "items": [
                            {"item": "24小时内发送价值对比总结邮件", "importance": "中"},
                            {"item": "记录客户异议类型和应对效果", "importance": "低"}
                        ]}
                    ]
                },
                "flowchart": {
                    "title": "客户价格异议处理流程",
                    "nodes": [
                        {"id": "1", "label": "客户提出价格异议", "type": "start"},
                        {"id": "2", "label": "先认同感受", "type": "process"},
                        {"id": "3", "label": "判断真实顾虑", "type": "decision"},
                        {"id": "4", "label": "价值重塑+量化论证", "type": "process"},
                        {"id": "5", "label": "提供灵活方案", "type": "process"},
                        {"id": "6", "label": "达成意向", "type": "end"}
                    ],
                    "edges": [
                        {"from": "1", "to": "2", "label": ""},
                        {"from": "2", "to": "3", "label": ""},
                        {"from": "3", "to": "4", "label": "预算真实紧张"},
                        {"from": "3", "to": "5", "label": "认知偏差"},
                        {"from": "4", "to": "5", "label": ""},
                        {"from": "5", "to": "6", "label": ""}
                    ]
                },
                "learning_card": {
                    "title": "客户异议处理核心知识",
                    "principles": [
                        {"title": "先接纳再引导", "description": "客户情绪未被接纳前，任何道理都是对抗", "scenario": "客户情绪激动时"},
                        {"title": "价值先于价格", "description": "当客户感受到足够价值时，价格敏感度自然降低", "scenario": "客户单纯比价时"}
                    ],
                    "tools": [
                        {"name": "ROI计算器话术", "description": "将年度价格分解为日成本，并与客户收益对比", "usage": "客户说贵的时候，打开计算器现场算"},
                        {"name": "三层开场话术", "description": "对高管用TCO对比、对技术用架构请教、对执行用场景演示", "usage": "根据客户角色选择对应话术版本"}
                    ],
                    "key_concepts": [
                        {"concept": "价格异议", "explanation": "客户对产品定价表达不满或犹豫，通常分为真实预算限制和认知偏差两类"},
                        {"concept": "价值重塑", "explanation": "将客户关注点从价格转移到产品能带来的实际价值和ROI上"}
                    ]
                },
                "case_study": {
                    "title": "SaaS客户价格异议成功化解案例",
                    "background": "某制造业客户正在评估SaaS产品，已接触3家竞品，认为我方报价比最低竞品高20%",
                    "challenge": "客户采购总监明确说：你们比XX贵20%，除非降价否则不考虑",
                    "process": [
                        {"phase": "情绪接纳", "description": "没有急于解释价格差异，而是说理解采购预算的压力", "key_decision": "先处理情绪，再处理事情"},
                        {"phase": "真实顾虑挖掘", "description": "通过提问发现客户真正担心的是ROI不确定，而非绝对价格", "key_decision": "用问题代替陈述"},
                        {"phase": "价值量化", "description": "现场计算：虽然年费高20%，但实施周期短2个月，人工节省相当于半年费用", "key_decision": "用客户自己的数据说话"},
                        {"phase": "灵活方案", "description": "提供分阶段上线方案，首年仅采购核心模块，降低决策门槛", "key_decision": "保留成交空间不降价"}
                    ],
                    "result": "客户最终选择分阶段方案，首年签约后第二年全面扩展，总合同金额比原计划还高15%",
                    "lessons": ["价格异议背后通常是价值认知不足", "现场计算比事后发资料更有效", "不降价也能成交，关键是创造替代价值"]
                }
            }
        else:
            return {"message": "模拟响应", "content": "这是一个模拟的AI响应，用于系统功能测试。"}
    
    async def _mock_stream(self) -> AsyncIterator[str]:
        """模拟流式输出"""
        chunks = ["这是一个", "模拟的", "AI流式", "响应。", "用于", "系统功能", "测试。"]
        for chunk in chunks:
            yield chunk
    
    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """流式生成文本"""
        start_time = time.time()
        if self.mock_mode:
            logger.info(
                "LLM stream in mock mode",
                extra={
                    "provider": self.provider,
                    "model": self._get_model(),
                    "mock_mode": True,
                    "event": "llm_stream_mock",
                },
            )
            async for chunk in self._mock_stream():
                yield chunk
            return
        try:
            if self.provider in ("openai", "deepseek"):
                async for chunk in self._openai_stream(system_prompt, messages, temperature, max_tokens):
                    yield chunk
            elif self.provider == "anthropic":
                async for chunk in self._anthropic_stream(system_prompt, messages, temperature, max_tokens):
                    yield chunk
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            duration_ms = (time.time() - start_time) * 1000
            prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            logger.info(
                "LLM stream call completed",
                extra={
                    "provider": self.provider,
                    "model": self._get_model(),
                    "duration_ms": round(duration_ms, 2),
                    "prompt_tokens": prompt_tokens,
                    "event": "llm_stream_success",
                },
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Stream API call failed, falling back to mock mode: {e}",
                extra={
                    "provider": self.provider,
                    "model": self._get_model(),
                    "duration_ms": round(duration_ms, 2),
                    "event": "llm_stream_error",
                },
                exc_info=True,
            )
            async for chunk in self._mock_stream():
                yield chunk
    
    def _get_model(self) -> str:
        """获取当前provider对应的模型名称"""
        if self.provider == "deepseek":
            return settings.DEEPSEEK_MODEL
        return settings.OPENAI_MODEL

    def _generate_cache_key(self, system_prompt: str, messages: list[dict], temperature: float) -> str:
        """为确定性LLM调用生成缓存key"""
        content = json.dumps({
            "provider": self.provider,
            "model": self._get_model(),
            "system": system_prompt,
            "messages": messages,
            "temperature": temperature,
        }, sort_keys=True, ensure_ascii=False)
        return f"llm:{hashlib.sha256(content.encode()).hexdigest()[:32]}"

    async def generate_json(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """生成结构化JSON输出（支持确定性调用缓存）"""
        start_time = time.time()
        cache_key = None

        # 仅对 temperature == 0 的确定性调用启用缓存
        if temperature == 0:
            cache_key = self._generate_cache_key(system_prompt, messages, temperature)
            cached = await llm_response_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "LLM JSON cache hit",
                    extra={
                        "provider": self.provider,
                        "model": self._get_model(),
                        "event": "llm_json_cache_hit",
                    },
                )
                return cached

        if self.mock_mode:
            logger.info(
                "LLM JSON in mock mode",
                extra={
                    "provider": self.provider,
                    "model": self._get_model(),
                    "mock_mode": True,
                    "event": "llm_json_mock",
                },
            )
            return self._get_mock_json_response(system_prompt)
        try:
            if self.provider in ("openai", "deepseek"):
                result = await self._openai_json(system_prompt, messages, temperature, max_tokens)
            elif self.provider == "anthropic":
                result = await self._anthropic_json(system_prompt, messages, temperature, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            duration_ms = (time.time() - start_time) * 1000
            prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            logger.info(
                "LLM JSON call completed",
                extra={
                    "provider": self.provider,
                    "model": self._get_model(),
                    "duration_ms": round(duration_ms, 2),
                    "prompt_tokens": prompt_tokens,
                    "event": "llm_json_success",
                },
            )
            # 缓存确定性调用结果
            if cache_key is not None and result is not None:
                await llm_response_cache.set(cache_key, result)
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"API call failed, falling back to mock mode: {e}",
                extra={
                    "provider": self.provider,
                    "model": self._get_model(),
                    "duration_ms": round(duration_ms, 2),
                    "event": "llm_json_error",
                },
                exc_info=True,
            )
            return self._get_mock_json_response(system_prompt)
    
    async def _openai_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """OpenAI流式生成"""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")
        
        all_messages = [{"role": "system", "content": system_prompt}]
        all_messages.extend(messages)
        
        stream = await self.openai_client.chat.completions.create(
            model=self._get_model(),
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def _openai_json(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """OpenAI JSON模式生成"""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")
        
        all_messages = [{"role": "system", "content": system_prompt}]
        all_messages.extend(messages)
        
        response = await self.openai_client.chat.completions.create(
            model=self._get_model(),
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    
    async def _anthropic_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Anthropic流式生成"""
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not initialized")
        
        stream = await self.anthropic_client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
            stream=True,
        )
        
        async for event in stream:
            if event.type == "content_block_delta":
                yield event.delta.text
    
    async def _anthropic_json(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Anthropic JSON生成"""
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not initialized")
        
        # 在system prompt中要求JSON输出
        json_system = system_prompt + "\n\n你必须以JSON格式输出，不要包含任何其他文本。"
        
        response = await self.anthropic_client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=json_system,
            messages=messages,
        )
        
        content = response.content[0].text
        # 尝试提取JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试从文本中提取JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise


# 全局LLM服务实例
llm_service = LLMService()
