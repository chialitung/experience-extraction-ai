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

### Frontend (`frontend/`)

- **React 18** + **TypeScript** + **Vite** + **TailwindCSS** + **Zustand**
- Dev server proxies `/api` → `localhost:8000`
- **E2E**: Playwright, single-worker serial execution, video recording enabled, 20min timeout per test

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

### Prompt Management
Jinja2 templates in `app/prompts/`. `PromptManager` renders `system/role_definition.md` plus injected sections (expert profile, blueprint guidance, real-time analysis, time budget).

### RBAC
- `frontend/src/config/auth.ts`: `SKIP_AUTH` toggle (default `false`)
- Admin endpoints under `/auth/admin/` guarded by `get_current_admin`
- `resolve_user_filter()` in `interviews.py`: filters interviews by ownership unless admin or no-token

## Common Commands

```bash
# Backend tests
cd backend && python -m pytest -x              # stop on first failure
cd backend && python -m pytest -k test_name    # single test

# Backend dev
cd backend && uvicorn main:app --reload        # http://localhost:8000

# Frontend dev
cd frontend && npm run dev                     # http://localhost:5173

# Frontend build & lint
cd frontend && npm run build
cd frontend && npm run lint

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
- `TOPIC_DRIFT_THRESHOLD` (default 0.35), `TOPIC_DRIFT_GRAY_LOWER` (0.15)
- `BAIDU_SPEECH_*` for voice transcription
- `MOCK_TRANSCRIPTION=true` for E2E/demo without real ASR
