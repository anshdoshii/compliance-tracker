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

## Testing rules (non-negotiable)

Tests are the only QA layer — there is no frontend, no manual tester, no staging environment.
Every change ships with tests. No exceptions.

### What to test for every new feature
1. **Happy path** — correct input, expected output
2. **Validation errors** — bad input returns 422 with standard envelope
3. **Auth errors** — missing/invalid/expired token returns 401; wrong role returns 403
4. **Not-found / business errors** — missing resources, invalid state return 400/404 with envelope
5. **Concurrency** — any endpoint that writes to Redis or DB must have a concurrent-request test
6. **Rate limiting** — any rate-limited path must be tested at the limit boundary (exactly N allowed, N+1 blocked)
7. **Cascade / side-effects** — deleting a parent must be tested to confirm children are gone
8. **Response envelope** — every endpoint response must have `{success, data, meta, error}` shape

### What to test for every new model
1. Create and query back — all fields round-trip correctly
2. Unique constraints — duplicate key raises `IntegrityError`
3. CHECK constraints — invalid enum values raise `IntegrityError`
4. Cascade deletes — `session.delete(parent)` removes children
5. Boolean/default columns — value is correct immediately after flush (no refresh needed)
6. Date vs datetime columns — `due_date` must be `date`, timestamps must be `datetime`

### Fix code, not tests
If a test fails and the test logic is correct, the **code is wrong** — fix the code.
Never add `refresh()` calls, `try/except` wrappers, or skip markers to make a broken
implementation pass. The test is the spec.

Exceptions: test-infrastructure fixes (e.g. SQLite PRAGMA, conftest setup) are
acceptable as long as they make the test environment match production behaviour — document
why in a comment.

### Test file naming
| What | File |
|---|---|
| Unit tests for a module | `tests/test_<module_name>.py` |
| Integration / end-to-end | `tests/test_integration_<feature>.py` |
| Exception / error paths | `tests/test_exception_handlers.py` |
| Concurrency | `tests/test_concurrency.py` |
| Performance / latency | `tests/test_performance.py` |
| Model CRUD + constraints | `tests/test_models.py` |

### Concurrency test rules
- Use `asyncio.gather()` to fire coroutines simultaneously
- Every Redis read-then-write sequence (OTP verify, token use) must have a concurrent test
  proving only one caller wins
- Do **not** use concurrent requests to test DB uniqueness through the HTTP layer —
  the shared SQLAlchemy session in tests cannot handle concurrent flushes.
  Test DB uniqueness at the model layer (`test_models.py`) instead.

### Performance test rules
- All thresholds must be generous enough to pass on a cold dev laptop (not tuned for CI)
- Single HTTP request: < 300 ms
- Health check: < 50 ms
- JWT encode/decode: 1 000 ops < 1 s
- Bulk inserts (50 rows): < 2 s
- If a performance test starts flaking, raise the threshold with a comment explaining why —
  never delete the test

---

## Code Tracker (mandatory)

Every new file, endpoint, model, or test must be documented in `docs/CODE_TRACKER.md` **in the same commit**.

The tracker records: what the file does, every column in new models, every endpoint (method + path + inputs + outputs + error codes), and any design decisions or known TODOs. Future sessions start from this file — if it's stale, context is lost.

---

## Before writing any code, ask yourself:

1. Is this feature in the current phase scope?
2. Does this endpoint have role validation?
3. Will this work offline (for Flutter)?
4. Is there a test for this?
5. Am I storing dates in UTC?
6. Does every new model have a `default=` (Python-side) for every column that has `server_default=`?
7. Does every new relationship that owns its children have `cascade="all, delete-orphan"`?

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
