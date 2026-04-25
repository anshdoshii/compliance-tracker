# ComplianceOS — Claude Code Instructions

## READ THIS FIRST. ALWAYS.

This file governs how you build ComplianceOS. Every session starts here.
Do not make architectural decisions not covered in PRODUCT_SPEC.md without asking.
Do not skip ahead in the MVP phases without explicit user instruction.

---

## What you are building

A two-sided compliance platform for India:
- **CA users** (Chartered Accountants) manage their clients' compliance
- **SMB users** (businesses) track their own compliance and connect with their CA

Both personas live in ONE app. Role is detected at login. Same backend, different UI skin and AI persona.

Full details: `docs/PRODUCT_SPEC.md`

---

## Current phase: PHASE 1 MVP

Build ONLY what is listed in Section 13 (Phase 1) of the spec.
Do not build AI features, WhatsApp, or regulation scraping yet.
Get the core loop right first.

### Phase 1 checklist (build in this order):
- [ ] Auth: OTP login, JWT, role detection
- [ ] CA onboarding: profile, plan selection, client CSV import
- [ ] SMB onboarding: invite flow, profile setup
- [ ] Compliance calendar: manual items, due dates, status
- [ ] Task system: CA creates → client sees and responds
- [ ] Document upload: request → upload → view
- [ ] Basic chat: CA-client messaging (polling, not WebSocket yet)
- [ ] Health score: calculation and display
- [ ] Billing: Razorpay subscription, plan enforcement

---

## Non-negotiable rules (enforce these on every file you touch)

1. **Every endpoint has role validation** — check user role before returning any data
2. **A client NEVER sees another client's data** — always filter by `ca_client_link`
3. **A CA NEVER sees another CA's clients** — always filter by `ca_id`
4. **Payment status comes only from Razorpay webhooks** — never trust client-side
5. **All dates stored in UTC, displayed in IST** — use `pytz` on backend, `intl` on Flutter
6. **File uploads: validate magic bytes, not extension** — max 20MB per file
7. **Every background job must be idempotent** — safe to run twice
8. **Never drop DB columns without a prior backup migration**
9. **AI responses are always sanitised before display** — never raw injection
10. **If RAG returns nothing, AI says so** — no hallucinated regulation details

---

## Tech stack (do not deviate)

| Layer | Technology |
|---|---|
| Frontend | Flutter + Riverpod + Dio + GoRouter |
| Backend | Python FastAPI (async) |
| Database | PostgreSQL + SQLAlchemy async + Alembic |
| Cache | Redis |
| Queue | Celery + Redis |
| File storage | Cloudflare R2 |
| AI | OpenRouter API |
| Payments | Razorpay |
| OTP/SMS | MSG91 |
| Notifications | Meta WhatsApp Cloud API |

---

## Project structure

```
complianceos/
├── CLAUDE.md               ← you are here
├── docs/
│   ├── PRODUCT_SPEC.md     ← full product spec
│   ├── API_REFERENCE.md    ← all endpoints
│   └── DATABASE_SCHEMA.md  ← full DB schema
├── server/                 ← FastAPI backend
└── flutter_app/            ← Flutter frontend
```

---

## Before writing any code, ask yourself:

1. Is this feature in the current phase scope?
2. Does this endpoint have role validation?
3. Will this work offline (for Flutter)?
4. Is there a test for this?
5. Am I storing dates in UTC?

If any answer is no — fix it before moving on.

---

## How to run locally

```bash
# Backend
cd server
cp ../.env.example .env   # fill in your keys
docker-compose up -d       # starts Postgres + Redis
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload

# Flutter
cd flutter_app
flutter pub get
flutter run -d chrome      # web first for fast iteration
```

---

## When you are stuck or unsure

Do not guess. Do not improvise. Ask the user:
> "The spec doesn't cover [X]. Should I [option A] or [option B]?"

The spec is the source of truth. If it's not in the spec, it doesn't exist yet.
