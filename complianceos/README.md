# ComplianceOS

India's two-sided compliance platform for CAs and businesses.

## Quick start (development)

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Backend
cd server
cp ../.env.example .env      # Fill in your API keys
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload    # Runs on http://localhost:8000

# 3. Flutter (in a new terminal)
cd flutter_app
flutter pub get
flutter run -d chrome        # Web — fastest for development
```

## Key files

| File | Purpose |
|---|---|
| `CLAUDE.md` | Instructions for Claude Code — read every session |
| `docs/PRODUCT_SPEC.md` | Full product specification (source of truth) |
| `docs/DATABASE_SCHEMA.md` | All table definitions |
| `docs/API_REFERENCE.md` | All API endpoints |
| `.env.example` | All required environment variables |

## Current build phase: Phase 1 MVP

See `CLAUDE.md` for the phase 1 checklist.
Do not skip ahead without completing phase 1.

## Architecture

- **Flutter** — single codebase for iOS, Android, Web, Desktop
- **Python FastAPI** — single async backend
- **PostgreSQL** — primary database
- **Redis** — cache + Celery task queue
- **OpenRouter** — AI (Claude + Gemini via one API)
- **Cloudflare R2** — file storage
- **Razorpay** — payments
- **Meta WhatsApp Cloud API** — notifications
