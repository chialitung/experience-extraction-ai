# Experience Extraction AI

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![Node](https://img.shields.io/badge/Node-18+-green)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](docker-compose.yml)

AI 驱动的经验萃取访谈辅助系统，帮助组织将业务专家的隐性经验转化为可复制的显性知识。

## ✨ 功能特性

- **六步结构化访谈**：复盘事件 → 建构框架 → 挖掘细节 → 识别障碍 → 提炼工具 → 复述确认
- **智能话题偏离检测**：jieba 分词 + Jaccard / 余弦相似度 + 跨轮升级，纯规则 O(n) 复杂度
- **专家画像分析**：从回答文本特征自动推断沟通风格（健谈 / 寡言 / 谨慎 / 平衡）
- **多格式成果输出**：访谈结束后自动生成话术卡、检查表、流程图、学习卡，支持 Word / Markdown / JSON 导出
- **语音输入支持**：集成百度语音识别 WebSocket 实时转写
- **可选 JWT 认证**：无 token 时开放访问（演示模式），有 token 时强制鉴权

![图片描述](screenshot&reportsample\Snipaste_2026-05-03_18-26-05.png)
![图片描述](screenshot&reportsample\Snipaste_2026-05-03_18-35-28.png)

## 🚀 Quick Start (Docker)

**前置要求**：Docker + Docker Compose

```bash
# 1. 克隆仓库
git clone https://github.com/chialitung/experience-extraction-ai.git
cd experience-extraction-ai

# 2. 复制并编辑环境变量
cp .env.docker.example .env
# 编辑 .env：填入 POSTGRES_PASSWORD、SECRET_KEY、至少一个 LLM API Key

# 3. 启动全部服务
docker compose up -d --build
```

访问 http://localhost:8080 即可使用。

详见 [docs/deployment/docker.md](docs/deployment/docker.md)。

## 🛠️ Manual Setup

如需在本地直接运行前后端源码（不通过 Docker），请参考 [docs/deployment/manual.md](docs/deployment/manual.md)。

## 📁 Project Structure

详见 [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)。

## 🔌 Tech Stack

| 后端 | 前端 |
|------|------|
| FastAPI + SQLAlchemy 2.0 async | React 18 + TypeScript |
| PostgreSQL / SQLite | Vite |
| Redis (缓存 / 限流) | TailwindCSS |
| Alembic (迁移) | Zustand (状态管理) |
| OpenAI / Anthropic / DeepSeek | Axios |
| jieba (NLP) | Playwright (E2E) |

## 📚 Documentation

- [Docker 部署指南](docs/deployment/docker.md) — 生产环境 Docker Compose 部署
- [手动部署指南](docs/deployment/manual.md) — 本地开发/生产手动部署
- [SMTP 邮件配置](docs/deployment/smtp.md) — QQ / 163 / Gmail / Outlook 配置
- [开发环境设置](docs/development/setup.md) — 热更新、测试运行
- [项目结构说明](docs/PROJECT_STRUCTURE.md) — 完整文件结构说明

## 📜 License

[MIT](LICENSE)
