# Kimi K2.6 配置指南

## 兼容性说明

**完全兼容！** Kimi API 完全兼容 OpenAI 的 API 格式，可以直接使用 OpenAI Python SDK 调用。

## 配置步骤

### 1. 获取 Kimi API Key

1. 访问 [Kimi 开放平台](https://platform.moonshot.cn/)
2. 注册/登录账号
3. 在控制台创建 API Key

### 2. 配置环境变量

编辑 `backend/.env` 文件：

```env
# Kimi (Moonshot) 配置
OPENAI_API_KEY=your-moonshot-api-key-here
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_MODEL=kimi-k2.6

# 使用 openai 作为 provider（因为 Kimi 兼容 OpenAI 格式）
DEFAULT_LLM_PROVIDER=openai
```

### 3. 模型选择

| 模型名称 | 说明 | 上下文长度 |
|---------|------|-----------|
| `kimi-k2.6` | 最新多模态模型，推荐 | 256K |
| `kimi-k2.5` | 上一代模型 | 256K |
| `kimi-k2-thinking` | 思考模式 | 256K |

### 4. 注意事项

1. **temperature 固定**：Kimi K2.6 的 temperature 固定为 1.0（思考模式），系统会自动处理
2. **JSON 模式**：支持 `response_format={"type": "json_object"}`，与 OpenAI 一致
3. **流式输出**：支持 SSE 流式输出，与 OpenAI 一致
4. **思考模式**：默认启用，如需关闭可在请求中设置 `thinking: {"type": "disabled"}`

### 5. 验证配置

启动后端服务后，访问 http://localhost:8000/docs 测试 API。

创建访谈后，蓝图生成会调用 Kimi API，如果配置正确，将返回结构化的访谈蓝图。

## 快速测试

```bash
cd backend

# 确保虚拟环境已激活
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# 重启服务以加载新配置
uvicorn main:app --reload
```

然后在前端创建一个新访谈，观察蓝图是否正常生成。
