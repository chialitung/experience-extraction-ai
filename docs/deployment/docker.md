# Docker Compose 部署指南

## 快速启动

```bash
cp .env.docker.example .env
# 编辑 .env 填入必填项

docker compose up -d --build
```

访问 http://localhost:8080。

## 环境变量说明

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `POSTGRES_PASSWORD` | 是 | - | PostgreSQL 数据库密码 |
| `SECRET_KEY` | 是 | - | JWT 签名密钥，建议 `openssl rand -hex 32` 生成 |
| `OPENAI_API_KEY` | 是* | - | OpenAI API Key（至少填一个 LLM） |
| `DEEPSEEK_API_KEY` | 是* | - | DeepSeek API Key（与上二选一或都填） |
| `ANTHROPIC_API_KEY` | 否 | - | Anthropic API Key（可选） |
| `DEFAULT_LLM_PROVIDER` | 否 | `openai` | 默认 LLM 提供商 |
| `BAIDU_SPEECH_*` | 否 | - | 百度语音识别（语音输入功能） |
| `SMTP_*` | 否 | - | SMTP 邮件（密码找回功能） |
| `FRONTEND_PORT` | 否 | `8080` | 前端暴露端口 |

\* 至少填一个 LLM Key，否则后端启动会报错（生产环境 SECRET_KEY 校验）。

## 服务架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   nginx     │────▶│   backend   │────▶│  postgres   │     │    redis    │
│  (frontend) │     │  (FastAPI)  │     │ (PostgreSQL)│     │   (Redis)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       └───────────────────┘
            /api/* 反代
```

## 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f backend

# 重启服务
docker compose restart backend

# 停止并删除
docker compose down

# 停止并删除卷（清空数据库）
docker compose down -v
```

## 常见排障

**backend 无法连接 postgres**
- 检查 `POSTGRES_PASSWORD` 是否已填
- 检查 postgres healthcheck 是否通过：`docker compose logs postgres`

**前端页面空白**
- 检查 nginx 是否正常启动：`docker compose logs frontend`
- 确认 `dist/` 已正确构建

**LLM 调用失败**
- 检查 `.env` 中是否至少填了一个 LLM API Key
- 检查 `DEFAULT_LLM_PROVIDER` 与所填 Key 是否匹配
