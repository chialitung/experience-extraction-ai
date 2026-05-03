# 开发环境设置

## 后端开发

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate

# 热重载启动
uvicorn main:app --reload

# 代码格式化
black .
isort .

# 运行测试
python -m pytest -x        # 遇到第一个失败停止
python -m pytest -k test_name  # 运行单个测试
```

## 前端开发

```bash
cd frontend

# 热更新开发服务器
npm run dev

# 代码检查
npm run lint

# 类型检查
npx tsc --noEmit

# 生产构建
npm run build
```

## E2E 测试

```bash
cd frontend

# 安装 Playwright 浏览器
npx playwright install chromium

# 运行 E2E 测试
npx playwright test

# 查看测试报告
npx playwright show-report
```

## 数据库迁移

```bash
cd backend

# 创建迁移
alembic revision --autogenerate -m "description"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

## 环境变量速查

开发时复制 `backend/.env.example` 为 `backend/.env`，至少填写：

- `SECRET_KEY`（任意字符串，开发环境不强校验）
- `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`（至少一个 LLM）

其余变量保持默认即可。
