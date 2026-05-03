# 项目文件结构完整说明

**项目根目录**: experience-extraction-ai/
**技术栈**: FastAPI (后端) + React 18 + TypeScript + Vite (前端)

---

## 一、根目录文件 (Root Level Files)

```text
.gitignore                -- Git版本控制忽略规则文件，定义哪些文件/目录不被Git跟踪
README.md                 -- 项目总览说明文档，包含快速开始指南、API接口说明
manage.cmd                -- Windows批处理入口，调用PowerShell脚本管理项目进程
manage.ps1                -- 项目进程管理PowerShell脚本：一键启动/停止/重启/查看状态前后端服务
```

```text
【根目录 -- 临时/日志/测试文件（运行生成，非版本控制核心）】
backend_err.log           -- 后端错误输出日志
backend_out.log           -- 后端标准输出日志
frontend_err.log          -- 前端错误输出日志
frontend_out.log          -- 前端标准输出日志
test_api_flow.log         -- API流程测试日志
```

---

## 二、后端目录 (backend/)

```text
backend/
│
├── main.py               -- FastAPI应用主入口。注册路由、中间件（CORS/限流/请求日志）、
│                           全局异常处理器、数据库表自动创建、健康检查端点
│
├── requirements.txt      -- Python依赖清单。包含FastAPI、SQLAlchemy、Alembic、
│                           OpenAI/Anthropic SDK、Pydantic、JWT认证、jieba分词等
│
├── pytest.ini            -- pytest测试框架配置（异步测试支持等）
│
├── .env                  -- 环境变量配置文件（本地开发用，含数据库URL、API Key等敏感信息）
├── .env.example          -- .env模板文件，展示需要配置的环境变量示例
│
├── experience_extraction.db  -- SQLite开发数据库文件（本地开发/测试用）
│
【日志目录】
├── logs/
│   ├── app.log           -- 应用运行日志（按日期轮转）
│   └── error.log         -- 错误级别日志（按日期轮转）
│
【数据库迁移】
├── alembic/
│   ├── alembic.ini       -- Alembic迁移工具配置文件
│   ├── env.py            -- Alembic迁移环境脚本，定义数据库连接和迁移上下文
│   ├── script.py.mako    -- 迁移脚本模板（生成新迁移时以此为模板）
│   └── versions/         -- 数据库迁移版本脚本目录（存放每次schema变更的迁移文件）
│
【后端测试】
├── tests/
│   ├── test_interviews.py                    -- 访谈API基础CRUD测试
│   ├── test_resume_interview.py              -- 访谈恢复功能测试
│   ├── test_content_analyzer_topic_drift.py  -- 内容分析器-主题偏离检测测试
│   ├── test_interview_service_three_layer.py -- 访谈服务三层推进规则测试
│   ├── test_interview_service_topic_drift.py -- 访谈服务主题偏离检测测试
│   └── test_interview_service_topic_drift_integration.py
│                                               -- 主题偏离检测集成测试
│
【核心业务代码 -- app/】
└── app/
    ├── __init__.py       -- Python包初始化文件
    │
    ├── api/              -- API路由层
    │   ├── __init__.py   -- API路由聚合入口，注册v1路由到主应用
    │   └── v1/           -- API v1版本路由
    │       ├── __init__.py       -- v1路由注册中心
    │       ├── auth.py           -- 认证相关路由：注册、登录、密码重置、JWT令牌刷新、
    │       │                         管理员用户管理（RBAC）
    │       ├── interviews.py     -- 访谈核心路由：创建/列表/详情/更新访谈、
    │       │                         蓝图生成与确认、消息发送与流式对话、
    │       │                         结构化内容获取、访谈完成、成果输出、
    │       │                         内容分析、专家画像
    │       ├── text_analysis.py  -- 文本分析路由：上传文本、分析状态查询、
    │       │                         结构化提取、成果导出（Word/PDF/JSON）
    │       └── config.py         -- 系统配置路由：获取当前LLM提供商和模型信息
    │
    ├── core/             -- 核心基础设施
    │   ├── __init__.py
    │   ├── config.py     -- Pydantic Settings配置中心。读取.env，管理数据库URL、
    │   │                     LLM配置、JWT密钥、CORS、日志级别等所有应用配置
    │   ├── database.py   -- SQLAlchemy 2.0异步数据库引擎和会话管理。
    │   │                     自动转换PostgreSQL/SQLite连接URL，创建异步会话工厂
    │   ├── security.py   -- 安全工具：密码哈希（bcrypt）、JWT令牌生成与验证、
    │   │                     可选认证依赖（token-present=强制认证，no-token=开放访问）
    │   ├── cache.py      -- Redis缓存封装。LLM确定性调用缓存、访谈元数据缓存
    │   ├── middleware.py -- 自定义中间件：请求日志记录（带request_id追踪）、
    │   │                     请求耗时统计
    │   ├── rate_limit.py -- 限流中间件。每IP每分钟200请求，触发后封禁30秒，
    │   │                     轮询端点排除不计入限流
    │   └── logging.py    -- 结构化日志系统配置。文件+控制台双输出、日志轮转、
    │                         请求ID关联、JSON格式extra字段支持
    │
    ├── models/           -- SQLAlchemy数据库模型（ORM层）
    │   ├── __init__.py   -- 模型统一导出
    │   ├── user.py       -- 用户模型：id、用户名、邮箱、密码哈希、is_superuser、
    │   │                     创建/更新时间
    │   ├── interview.py  -- 访谈模型：主题、背景、角色、状态机（6步+completed）、
    │   │                     蓝图JSON、结构化内容JSON、专家画像JSON、消息历史JSON、
    │   │                     内容分析结果、当前轮次、字数统计、完成时间、用户关联
    │   └── text_analysis.py  -- 文本分析模型：原始文本、清洗后文本、分析状态、
    │                             结构化提取结果（主题/步骤/要点/工具/案例）、
    │                             关联访谈ID
    │
    ├── schemas/          -- Pydantic数据验证模型（DTO/Schema层）
    │   ├── __init__.py
    │   ├── auth.py       -- 认证相关Schema：用户注册/登录请求、Token响应、
    │   │                     密码重置请求、用户列表响应
    │   ├── interview.py  -- 访谈相关Schema：创建/更新请求、详情响应、蓝图结构、
    │   │                     消息请求/响应、结构化内容、内容分析结果、专家画像、
    │   │                     输出成果格式
    │   └── text_analysis.py  -- 文本分析Schema：上传请求、分析状态响应、
    │                             结构化提取响应、导出配置
    │
    ├── services/         -- 业务逻辑服务层（核心实现）
    │   ├── __init__.py
    │   ├── interview_service.py      -- 访谈核心服务。六步状态机管理、
    │   │                                 三层推进守卫（LLM建议/字数时间预算/轮次限制）、
    │   │                                 消息历史管理、状态流转、完成处理
    │   ├── llm_service.py            -- LLM统一服务。封装OpenAI/Anthropic/DeepSeek调用，
    │   │                                 支持流式响应和JSON模式，Mock模式（无API Key时
    │   │                                 返回确定性假数据）
    │   ├── prompt_manager.py         -- 提示词管理器。Jinja2模板渲染，动态注入：
    │   │                                 专家画像适配、蓝图指导、实时内容分析、时间预算控制
    │   ├── content_analyzer.py       -- 纯规则内容分析引擎（零LLM调用，O(n)复杂度）。
    │   │                                 深度分析、主题偏离检测（jieba+Jaccard+cosine+跨轮升级）、
    │   │                                 灰区仲裁（0.15~0.35触发LLM语义判断）、信息缺口识别
    │   ├── expert_profiler.py        -- 纯规则专家画像引擎（零LLM调用，亚毫秒级）。
    │   │                                 从回答文本特征推断沟通风格：健谈/寡言/谨慎/平衡
    │   ├── auth_service.py           -- 认证服务：用户注册、登录验证、密码重置邮件发送、
    │   │                                 管理员权限校验
    │   ├── email_service.py          -- SMTP邮件服务封装，用于发送密码重置邮件
    │   ├── export_service.py         -- 成果导出服务：生成Word/PDF/JSON/Markdown格式的
    │   │                                 经验萃取成果文档
    │   ├── report_service.py         -- 报告生成服务：生成完整经验分析报告（含目录导航）
    │   ├── template_service.py       -- 文档模板服务：话术卡、检查表、流程图、学习卡等
    │   │                                 多种成果模板渲染
    │   ├── text_analysis_service.py  -- 文本分析服务：上传文本的完整分析流程协调
    │   ├── text_cleanup_service.py   -- 文本清洗服务：口语化文本的规范化处理
    │   ├── risk_marker.py            -- 风险标记服务：访谈内容质量风险评估
    │   ├── voice_transcription_service.py  -- 语音转写服务：音频转文本，支持Baidu Speech API
    │   ├── baidu_speech_service.py   -- 百度语音识别API封装（非实时长音频）
    │   └── baidu_realtime_asr_service.py   -- 百度实时语音识别WebSocket服务
    │
    └── prompts/          -- Jinja2提示词模板目录
        ├── system/
        │   └── role_definition.md    -- 系统级角色定义提示词。
        │                                   定义AI访谈助手的人格、六步流程规则、
        │                                   五维价值评估框架、提问策略
        ├── tasks/            -- 任务级提示词模板
        │   ├── blueprint_generation.md           -- 访谈蓝图生成提示词
        │   ├── opening_generation.md             -- 开场白生成提示词
        │   ├── question_generation.md            -- 问题生成提示词
        │   ├── content_extraction.md             -- 内容萃取提示词
        │   ├── text_structured_extraction.md     -- 文本结构化提取提示词
        │   ├── text_cleanup.md                   -- 文本清洗提示词
        │   ├── output_packaging.md               -- 成果包装提示词
        │   ├── expert_adaptation.md              -- 专家画像适配策略提示词
        │   ├── topic_drift_arbitration_system.md -- 主题偏离灰区仲裁-系统提示词
        │   └── topic_drift_arbitration_user.md   -- 主题偏离灰区仲裁-用户提示词
        └── quality/          -- 质量保障提示词（预留目录）
```

---

## 三、前端目录 (frontend/)

```text
frontend/
│
├── index.html            -- Vite应用HTML入口模板
├── package.json          -- Node.js依赖和脚本配置。React 18、TypeScript、TailwindCSS、
│                           Zustand、React Router、Axios、Playwright等
├── package-lock.json     -- npm依赖锁定文件，确保环境一致性
├── tsconfig.json         -- TypeScript主配置（应用代码编译选项）
├── tsconfig.node.json    -- TypeScript配置（Vite配置等Node环境代码编译选项）
├── vite.config.ts        -- Vite构建工具配置。React插件、路径别名@/src、
│                           开发服务器代理/api -> localhost:8000、WebSocket支持
├── tailwind.config.js    -- TailwindCSS配置。自定义主题、颜色、断点、内容扫描路径
├── postcss.config.js     -- PostCSS配置。集成TailwindCSS和autoprefixer
├── eslint.config.js      -- ESLint代码质量检查配置
│
├── playwright.config.ts  -- Playwright E2E测试配置。串行执行、单worker、
│                           45分钟超时、1920x1080分辨率、自动录制视频和麦克风权限
│
├── build.log             -- 前端构建日志
├── frontend*.log         -- 前端各类运行日志（开发/E2E/错误/输出等）
│
【构建产物】
├── dist/                 -- Vite生产构建输出目录
│   ├── index.html        -- 构建后的入口HTML
│   └── assets/           -- 构建后的静态资源（JS/CSS，含hash文件名）
│       ├── index-xxx.js  -- 打包后的JavaScript主文件
│       └── index-xxx.css -- 打包后的CSS样式文件
│
【E2E测试】
├── e2e/                  -- Playwright端到端测试
│   ├── interview-fallback.spec.ts          -- 兜底规则E2E测试（8轮对话完整流程）
│   ├── interview-voice-simulation.spec.ts  -- 语音输入模拟E2E测试（完整访谈+语音+录屏）
│   └── screenshots/      -- E2E测试过程中自动截取的屏幕截图（调试用）
│
【源代码 -- src/】
└── src/
    ├── main.tsx          -- React应用入口。渲染App组件、挂载到DOM
    ├── App.tsx           -- 根组件。定义全局路由配置（React Router）、
    │                       布局结构、受保护路由（认证守卫）
    ├── index.css         -- 全局CSS样式。Tailwind指令导入、自定义滚动条、
    │                       全局字体和基础样式覆盖
    ├── vite-env.d.ts     -- Vite环境类型声明
    │
    ├── types/
    │   └── index.ts      -- TypeScript全局类型定义。访谈、消息、蓝图、
    │                         结构化内容、专家画像、内容分析等共享类型
    │
    ├── config/
    │   └── auth.ts       -- 认证配置。SKIP_AUTH开关、角色权限常量定义
    │
    ├── services/
    │   └── api.ts        -- Axios API服务封装。基础HTTP客户端配置、
    │                         请求/响应拦截器（JWT自动附加、错误统一处理）、
    │                         所有后端API端点的类型化调用函数
    │
    ├── store/
    │   └── interviewStore.ts   -- Zustand全局状态存储。管理当前访谈、消息列表、
    │                             结构化内容、蓝图、专家画像、内容分析、加载/流式标志、
    │                             计时器、录音状态等所有访谈相关全局状态
    │
    ├── contexts/
    │   └── AuthContext.tsx     -- React认证上下文。提供登录状态、用户信息、
    │                             登录/登出/注册方法，全局共享认证状态
    │
    ├── hooks/              -- 自定义React Hooks
    │   ├── useInterview.ts           -- 访谈业务逻辑Hook。封装访谈创建、消息发送、
    │   │                                 流式响应处理、状态同步等操作
    │   ├── useVoiceRecorder.ts       -- 语音录制Hook。管理麦克风权限、录音开始/停止、
    │   │                                 音频Blob生成
    │   ├── useRealtimeTranscription.ts   -- 实时语音转写Hook。WebSocket连接管理、
    │   │                                     实时语音识别结果流处理
    │   └── useReportScrollSpy.ts   -- 报告页面滚动监听Hook。章节滚动高亮、
    │                                   目录导航联动
    │
    ├── components/         -- 可复用React组件
    │   ├── Layout.tsx              -- 全局布局组件。导航栏、侧边栏、页面容器、
    │   │                               响应式结构
    │   ├── ProtectedRoute.tsx      -- 受保护路由组件。未登录用户重定向到登录页
    │   ├── ErrorBoundary.tsx       -- 错误边界组件。捕获子组件渲染错误，
    │   │                               显示友好错误页面
    │   ├── Skeleton.tsx            -- 骨架屏加载组件。数据加载时的占位动画
    │   ├── AudioWaveform.tsx       -- 音频波形可视化组件。录音时的实时波形动画
    │   ├── ReportToc.tsx           -- 报告目录导航组件。悬浮章节导航、点击跳转、
    │   │                               当前章节高亮
    │   └── RecordSettingsModal.tsx -- 录音设置弹窗组件。麦克风选择、录音参数配置
    │
    ├── pages/              -- 页面级React组件（按路由划分）
    │   ├── HomePage.tsx            -- 首页/仪表盘。系统介绍、快捷操作入口、
    │   │                               最近访谈列表
    │   ├── InterviewListPage.tsx   -- 访谈列表页。所有访谈的卡片/表格展示、
    │   │                               搜索筛选、分页
    │   ├── InterviewCreatePage.tsx -- 创建访谈页。填写萃取主题、业务背景、
    │   │                               专家角色等表单，提交创建
    │   ├── BlueprintPage.tsx       -- 蓝图预览页。展示AI生成的六步访谈蓝图、
    │   │                               五维价值评估，确认或重新生成
    │   ├── InterviewChatPage.tsx   -- 访谈对话页。核心交互页面：消息气泡展示、
    │   │                               文本输入/语音输入切换、流式AI响应、
    │   │                               实时内容分析面板、阶段进度指示
    │   ├── OutputPage.tsx          -- 成果输出页。访谈完成后展示结构化成果：
    │   │                               话术卡、检查表、流程图、学习卡等，支持导出
    │   ├── ReportPage.tsx          -- 分析报告页。完整经验分析报告阅读，
    │   │                               含悬浮目录导航(TOC)、章节切换
    │   ├── TextAnalysisPage.tsx    -- 文本分析页。上传业务文档/历史文本、
    │   │                               触发AI分析、查看结构化提取结果
    │   ├── TextAnalysisListPage.tsx-- 文本分析列表页。历史文本分析任务管理
    │   ├── AuthPage.tsx            -- 认证页面（登录/注册）
    │   ├── ForgotPasswordPage.tsx  -- 忘记密码页。邮箱验证、重置链接发送
    │   ├── ResetPasswordPage.tsx   -- 重置密码页。新密码设置
    │   ├── AdminUsersPage.tsx      -- 管理员用户管理页。用户列表、权限管理、
    │   │                               账户操作
    │   └── SettingsPage.tsx        -- 系统设置页。个人资料、偏好设置、
    │                                   LLM提供商选择等
    │
    └── utils/              -- 工具函数
        ├── audioConverter.ts   -- 音频格式转换工具。WebM/PCM等格式互转，
        │                         满足百度语音识别API格式要求
        └── logger.ts           -- 前端日志工具。开发环境控制台日志、
                                  日志级别控制、结构化日志输出
```

---

## 四、E2E测试目录 (e2e/) -- 根级Python E2E测试

```text
e2e/
├── test_fallback_rules.py            -- Python编写的E2E兜底规则测试。
│                                       直接调用后端API验证8轮对话完整流程、
│                                       各阶段状态转换、内容提取准确性
│
└── screenshots/                        -- E2E测试截图
    ├── Snipaste_2026-05-02_22-02-23.png
    ├── ab_01_form_filled.png ~ ab_06_turn3.png    -- 兜底规则测试各阶段截图
    └── py_01_homepage.png ~ py_error_60min.png    -- Python E2E测试各阶段截图
```

---

## 五、文档/AI配置目录 (docs/)

```text
docs/
├── deployment/
│   ├── docker.md           -- Docker Compose 部署详细指南
│   ├── manual.md           -- 手动部署指南（不通过 Docker）
│   └── smtp.md             -- SMTP 邮件发送配置指南
├── development/
│   └── setup.md            -- 开发环境设置（热更新、测试运行）
├── PROJECT_STRUCTURE.md    -- 本文档：项目文件结构完整说明
├── test_plan_topic_drift_llm.md  -- LLM语义版主题偏离检测测试计划
└── superpowers/            -- Claude Code Superpowers技能配置
    ├── plans/              -- 计划模板目录（预留）
    └── specs/              -- 规格说明目录（预留）
```

---

## 六、隐藏/配置目录

```text
.claude/                      -- Claude Code会话数据目录（AI助手持久化配置）
.git/                         -- Git版本控制仓库数据
.logs/                        -- manage.ps1统一管理的服务日志目录
```

---

## 七、被排除未列出的目录说明

```text
backend/venv/                 -- Python虚拟环境（第三方依赖，由pip安装生成）
frontend/node_modules/        -- Node.js依赖包（由npm install生成）
backend/app/**/__pycache__/   -- Python字节码缓存（运行时自动生成）
**/.pytest_cache/            -- pytest测试缓存
frontend/dist/                -- 前端生产构建产物（由vite build生成）
```

以上目录均为自动生成或第三方内容，不属于项目源代码，故不在本说明中展开。

---

## 八、核心数据流与文件协作关系

```text
1. 访谈创建流程:
   InterviewCreatePage.tsx -> api.ts -> interviews.py -> interview_service.py
   -> interview.py(模型) -> database.py -> SQLite/PostgreSQL

2. 蓝图生成流程:
   BlueprintPage.tsx -> api.ts -> interviews.py -> prompt_manager.py
   -> prompts/tasks/blueprint_generation.md -> llm_service.py -> OpenAI/Anthropic

3. 对话流程:
   InterviewChatPage.tsx -> api.ts -> interviews.py -> interview_service.py
   -> content_analyzer.py(实时分析) + expert_profiler.py(画像推断)
   -> prompt_manager.py(动态组装提示词) -> llm_service.py -> 流式响应

4. 文本分析流程:
   TextAnalysisPage.tsx -> api.ts -> text_analysis.py -> text_analysis_service.py
   -> text_cleanup_service.py(清洗) -> llm_service.py(结构化提取)
   -> text_analysis.py(模型存储结果)

5. 成果导出流程:
   OutputPage.tsx -> api.ts -> interviews.py -> export_service.py
   -> template_service.py(模板渲染) -> python-docx/weasyprint(文档生成)
```

---

**文档生成时间**: 2026-05-03
