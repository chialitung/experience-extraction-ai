# 手动部署指南

适用于不想使用 Docker，或需要在 Windows/macOS 本地直接运行源码的场景。

## 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+（可选，默认使用 SQLite）
- Redis（可选，默认跳过缓存）

## 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库URL和LLM API Key

# 启动服务
uvicorn main:app --reload
```

后端服务将在 http://localhost:8000 运行，API 文档：http://localhost:8000/docs

## 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:5173 运行。

## 数据库说明

项目默认使用 SQLite（`sqlite+aiosqlite:///./dev.db`），无需额外配置。

如需使用 PostgreSQL：
1. 安装 PostgreSQL 并创建数据库
2. 修改 `.env` 中 `DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/experience_extraction`
3. 启动后端时会自动建表（`Base.metadata.create_all`）

## Windows 一键管理

项目根目录提供 `manage.cmd` / `manage.ps1`，支持：

```powershell
.\manage.ps1 start   # 启动前后端
.\manage.ps1 stop    # 停止
.\manage.ps1 restart # 重启
.\manage.ps1 status  # 查看状态
.\manage.ps1 logs    # 查看日志
```
