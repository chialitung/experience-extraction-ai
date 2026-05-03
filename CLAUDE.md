# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-driven experience extraction interview system. Backend guides experts through a 6-step structured interview, extracting implicit expertise into reusable knowledge assets (scripts, checklists, flowcharts, etc.).

## Architecture

### Backend (`backend/`)

- **FastAPI** + **SQLAlchemy 2.0 async** + **Pydantic Settings**
- **Database**: PostgreSQL (production), SQLite+aiosqlite (dev/tests). Auto-converts URL in `app/core/database.py`
- **Auth**: JWT with optional-auth fallback. `token-present = enforce ownership` — no token = open access (demo mode); token present = users see only their own interviews, admins see all
- **LLM**: Unified `llm_service.py` wrapping OpenAI / Anthropic / DeepSeek. Configured via `.env`
- **Tests**: `pytest` + `pytest-asyncio`. Test env auto-uses in-memory SQLite (`NullPool`). Run from `backend/`
- **Migrations**: Alembic (`alembic/`)
- **Cache**: Redis for LLM response cache and interview metadata cache

### Frontend (`frontend/`)

- **React 18** + **TypeScript** + **Vite** + **TailwindCSS** + **Zustand**
- Dev server proxies `/api` → `localhost:8000`
- **E2E**: Playwright, single-worker serial execution, video recording enabled, 45min timeout per test (full interview flows)
- **State**: Single Zustand store (`store/interviewStore.ts`) manages current interview, messages, structured content, blueprint, expert profile, content analysis, loading/streaming flags, timer, and recording state
- **Pages**: Home, InterviewList, InterviewCreate, Blueprint, InterviewChat, Output, Report, Auth (Login/Register/ForgotPassword/Reset), AdminUsers, Settings

## Key Services & Concepts

### Interview State Machine
Six-step flow managed by `InterviewService`:
```
event_review → framework_build → detail_mining → obstacle_identify → tool_extract → confirmation → completed
```

Three-tier advancement guardrails (in priority order):
1. **LLM suggestion** (`state_assessment.should_advance`)
2. **Word/time budget** (`STATE_WORD_DURATION_RATIOS` per stage, `stage_word_limit`)
3. **Turn limit** (`MAX_TURNS_PER_STATE = 3`)

### ContentAnalyzer (`app/services/content_analyzer.py`)
Pure rule-based analysis engine, **zero LLM calls**, O(n) complexity:
- **Depth analysis**: detail markers, vague markers, quantity patterns, sentence/structure counts
- **Topic drift detection**: jieba tokenization + Jaccard (theme matching) + cosine similarity (step relevance) + explicit phrase detection. Cross-turn escalation: +0.15 for 2 consecutive drifts, +0.30 for 3+
- **Gray-zone arbitration** (0.15, 0.35): LLM semantic judgment triggered when rule confidence falls in gray zone
- **Gap identification**: per-step structured content gap detection

### ExpertProfiler (`app/services/expert_profiler.py`)
Pure rule-based engine, **zero LLM calls**, sub-millisecond. Infers expert communication style from answer text features (certainty words, hesitation markers, self-deprecating phrases). Detects four types: talkative / quiet / cautious / balanced. Adapts interviewer strategy accordingly.

### Prompt Management
Jinja2 templates in `app/prompts/`. `PromptManager` renders `system/role_definition.md` plus four dynamically injected sections:
1. **Expert profile adaptation** — communication style and strategy
2. **Blueprint guidance** — current step focus, key questions, 五维价值评估
3. **Real-time content analysis** — depth score, topic drift, information gaps
4. **Time budget control** — turn limit and word limit per stage

### LLMService (`app/services/llm_service.py`)
Supports OpenAI / Anthropic / DeepSeek with streaming and JSON mode.
**Mock mode**: Automatically activates when API keys are missing or placeholder values. Returns deterministic JSON responses for blueprint/question/extraction/output prompts. Critical for development without real API keys.
**Cache**: Deterministic calls (temperature=0) are cached via Redis.

### Voice Transcription
`VoiceTranscriptionService` supports Baidu Speech API for real-time voice input. Set `MOCK_TRANSCRIPTION=true` in `.env` for E2E testing or demo mode without real ASR.

### RBAC
- `frontend/src/config/auth.ts`: `SKIP_AUTH` toggle (default `false`)
- Admin endpoints under `/auth/admin/` guarded by `get_current_admin`
- `resolve_user_filter()` in `interviews.py`: filters interviews by ownership unless admin or no-token
- **Optional auth model**: No token = open access (demo mode); token present = JWT enforced, users see only their own; `is_superuser = true` sees all

## Common Commands

```bash
# Backend tests
cd backend && python -m pytest -x              # stop on first failure
cd backend && python -m pytest -k test_name    # single test

# Backend dev
cd backend && uvicorn main:app --reload        # http://localhost:8000

# Backend formatting
cd backend && black .
cd backend && isort .

# Database migrations
cd backend && alembic revision --autogenerate -m "description"   # create
cd backend && alembic upgrade head                                  # apply
cd backend && alembic downgrade -1                                  # rollback

# Frontend dev
cd frontend && npm run dev                     # http://localhost:5173

# Frontend build & lint
cd frontend && npm run build
cd frontend && npm run lint

# Frontend type check
cd frontend && npx tsc --noEmit

# Frontend E2E
cd frontend && npx playwright test
```

## File Patterns

- API routes: `backend/app/api/v1/*.py`
- Business logic: `backend/app/services/*.py`
- DB models: `backend/app/models/*.py`
- Pydantic schemas: `backend/app/schemas/*.py`
- Prompt templates: `backend/app/prompts/**/*.md`
- Frontend pages: `frontend/src/pages/*.tsx`
- Frontend API: `frontend/src/services/api.ts`
- State: `frontend/src/store/*.ts`

## Environment

Backend reads `.env` in `backend/` (Pydantic BaseSettings). Key variables:
- `DATABASE_URL`, `SECRET_KEY`
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com/v1`)
- `DEFAULT_LLM_PROVIDER` (openai / anthropic / deepseek)
- `REDIS_URL` (default `redis://localhost:6379/0`)
- `TOPIC_DRIFT_THRESHOLD` (default 0.35), `TOPIC_DRIFT_GRAY_LOWER` (0.15)
- `TOPIC_DRIFT_PROMPT_INJECT` (0.20) — threshold for injecting drift warnings into prompts
- `TOPIC_DRIFT_MAX_HISTORY` (10) — history window for cross-turn escalation
- `BAIDU_SPEECH_*` for voice transcription
- `MOCK_TRANSCRIPTION=true` for E2E/demo without real ASR
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_SSL` for email
- `FRONTEND_BASE_URL` (default `http://localhost:5173`)
- `CORS_ORIGINS` (comma-separated, default `http://localhost:5173`)
- `LOG_LEVEL` (default INFO), `LOG_DIR`, `LOG_RETENTION_DAYS`
