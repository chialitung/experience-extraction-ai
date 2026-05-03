# 经验萃取AI系统

AI驱动的经验萃取访谈辅助系统，帮助组织将业务专家的隐性经验转化为可复制的显性知识。

## 项目结构

```
experience-extraction-ai/
├── backend/                 # FastAPI后端
│   ├── app/
│   │   ├── api/v1/         # API路由
│   │   ├── core/           # 配置、数据库
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic模型
│   │   ├── services/       # 业务逻辑
│   │   │   ├── llm_service.py      # LLM调用封装
│   │   │   ├── prompt_manager.py   # 提示词管理
│   │   │   └── interview_service.py # 访谈核心服务
│   │   └── prompts/        # 提示词模板
│   │       ├── system/     # 系统级提示词
│   │       ├── tasks/      # 任务级提示词
│   │       └── quality/    # 质量保障提示词
│   ├── alembic/            # 数据库迁移
│   ├── tests/              # 测试
│   ├── main.py             # 应用入口
│   └── requirements.txt    # 依赖
│
└── frontend/               # React前端
    ├── src/
    │   ├── components/     # 组件
    │   ├── pages/          # 页面
    │   │   ├── HomePage.tsx
    │   │   ├── InterviewListPage.tsx
    │   │   ├── InterviewCreatePage.tsx
    │   │   ├── BlueprintPage.tsx
    │   │   ├── InterviewChatPage.tsx
    │   │   └── OutputPage.tsx
    │   ├── hooks/          # 自定义Hooks
    │   ├── services/       # API服务
    │   ├── store/          # 状态管理
    │   └── types/          # TypeScript类型
    ├── package.json
    └── vite.config.ts
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (或 SQLite用于开发)
- Redis (可选，用于缓存)

### 2. 后端启动

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

后端服务将在 http://localhost:8000 运行
API文档：http://localhost:8000/docs

### 3. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:5173 运行

## 核心功能

### 1. 访谈蓝图生成
- 输入萃取主题、业务背景、专家角色
- AI自动生成结构化访谈蓝图
- 包含六步流程规划、五维价值评估

### 2. 智能访谈对话
- AI根据蓝图引导访谈流程
- 五类问题动态调度（事实性/探索性/要因性/假设性/确认性）
- 实时结构化内容萃取

### 3. 成果输出
- 访谈结束后自动生成成果文档
- 支持话术卡、检查表、流程图等多种格式
- 可导出JSON

## 技术栈

### 后端
- **FastAPI**: 异步Web框架
- **SQLAlchemy**: ORM
- **Alembic**: 数据库迁移
- **OpenAI/Anthropic**: LLM服务
- **Jinja2**: 提示词模板

### 前端
- **React 18**: UI框架
- **TypeScript**: 类型安全
- **TailwindCSS**: 样式
- **Zustand**: 状态管理
- **Axios**: HTTP客户端

## 六步萃取流程

1. **复盘事件**: 获取成功案例背景
2. **建构框架**: 识别核心步骤框架
3. **挖掘细节**: 深挖每个步骤的具体动作
4. **识别障碍**: 识别易错点、困难点
5. **提炼工具**: 提炼可操作的工具/话术
6. **复述确认**: 总结确认，专家审核

## API接口

### 访谈管理
- `POST /api/v1/interviews` - 创建访谈
- `GET /api/v1/interviews` - 列表
- `GET /api/v1/interviews/{id}` - 详情
- `PATCH /api/v1/interviews/{id}` - 更新

### 蓝图
- `POST /api/v1/interviews/{id}/blueprint/generate` - 生成蓝图
- `POST /api/v1/interviews/{id}/blueprint/confirm` - 确认蓝图

### 对话
- `POST /api/v1/interviews/{id}/messages` - 发送消息
- `GET /api/v1/interviews/{id}/messages` - 消息历史
- `POST /api/v1/interviews/{id}/messages/stream` - 流式对话

### 成果
- `GET /api/v1/interviews/{id}/structured-content` - 结构化内容
- `POST /api/v1/interviews/{id}/complete` - 完成访谈
- `GET /api/v1/interviews/{id}/output` - 获取成果

## 配置说明

### 环境变量

```env
# 数据库
DATABASE_URL=postgresql://user:password@localhost:5432/experience_extraction

# LLM (至少配置一个)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# 应用
SECRET_KEY=your-secret-key
```

## 开发计划

### MVP (已完成)
- [x] 后端基础框架
- [x] 数据库模型
- [x] LLM服务封装
- [x] 提示词管理
- [x] 访谈核心API
- [x] 前端基础框架
- [x] 核心页面实现

### 后续迭代
- [ ] 专家画像自动识别
- [ ] 主题偏离检测
- [ ] 流式响应优化
- [ ] 用户认证
- [ ] 更多成果模板
- [ ] 数据分析仪表盘

## 贡献

欢迎提交Issue和PR！

## 许可证

MIT
