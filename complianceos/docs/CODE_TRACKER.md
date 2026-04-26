# ComplianceOS — Code Tracker

Every file added to this project is documented here.  
**Rule:** Update this file in the same commit as any new file, endpoint, model, or test. See CLAUDE.md for the reminder.

---

## Table of Contents

1. [Project Layout](#1-project-layout)
2. [Phase 1 — Server Bootstrap](#2-phase-1--server-bootstrap)
   - [Entry Point](#21-entry-point)
   - [Core Modules](#22-core-modules)
   - [SQLAlchemy Models](#23-sqlalchemy-models)
   - [Alembic Migration](#24-alembic-migration)
   - [Routers](#25-routers)
   - [Tests](#26-tests)
3. [Key Design Decisions](#3-key-design-decisions)
4. [Patterns & Conventions](#4-patterns--conventions)
5. [Known TODOs (deferred to later phases)](#5-known-todos)

---

## 1. Project Layout

```
complianceos/
├── CLAUDE.md                        ← project rules for Claude
├── docs/
│   ├── PRODUCT_SPEC.md              ← full product spec (source of truth)
│   ├── API_REFERENCE.md             ← all planned endpoints
│   ├── DATABASE_SCHEMA.md           ← full DB schema spec
│   └── CODE_TRACKER.md              ← THIS FILE
├── server/                          ← FastAPI backend
│   ├── main.py
│   ├── requirements.txt
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   └── dependencies.py
│   ├── models/
│   │   ├── user.py
│   │   ├── ca_profile.py
│   │   ├── smb_profile.py
│   │   ├── ca_client_link.py
│   │   ├── compliance_item.py
│   │   ├── task.py
│   │   ├── document.py
│   │   ├── message.py
│   │   ├── invoice.py
│   │   ├── health_score.py
│   │   ├── payment.py
│   │   ├── regulation.py
│   │   └── notification.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── ca.py
│   │   └── client.py
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/001_initial_schema.py
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_ca.py
│       ├── test_client.py
│       ├── test_models.py
│       ├── test_core_auth.py
│       ├── test_config.py
│       ├── test_dependencies.py
│       ├── test_exception_handlers.py
│       ├── test_middleware.py
│       ├── test_integration_auth.py
│       ├── test_concurrency.py
│       └── test_performance.py
└── flutter_app/                     ← (not started yet)
```

---

## 2. Phase 1 — Server Bootstrap

### 2.1 Entry Point

#### `server/main.py`
FastAPI application entry point.

**What it does:**
- Creates the `FastAPI` app with docs at `/v1/docs`, `/v1/redoc`, `/v1/openapi.json`
- `lifespan` context manager connects Redis on startup, disconnects on shutdown (`app.state.redis`)
- CORS: all localhost origins in `development`, three `complianceos.in` subdomains in `production`
- Three global exception handlers, all returning the standard envelope `{success, data, meta, error}`:
  - `StarletteHTTPException` / `HTTPException` — passes through router-set envelopes; wraps plain strings
  - `RequestValidationError` — strips raw input values (prevents OTP/mobile leakage), returns 422
  - `Exception` — catches unhandled errors, logs to Sentry if `SENTRY_DSN` is set, returns 500
- Routers registered (all under `/v1`):
  - `auth_router` → `/v1/auth`
  - `ca_router` → `/v1/ca`
  - `client_router` → `/v1/client`
- Health check: `GET /v1/health`

---

### 2.2 Core Modules

#### `server/requirements.txt`
Pinned dependencies (Python 3.11 required — 3.14 cannot build pydantic-core wheels):

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.115.0 | Web framework |
| uvicorn[standard] | 0.30.6 | ASGI server |
| sqlalchemy[asyncio] | 2.0.36 | ORM + async engine |
| asyncpg | 0.29.0 | PostgreSQL async driver |
| alembic | 1.13.3 | DB migrations |
| pydantic-settings | 2.5.2 | Settings from `.env` |
| pydantic[email] | 2.9.2 | Request validation |
| python-jose[cryptography] | 3.3.0 | JWT encode/decode |
| redis[asyncio] | 5.1.1 | Redis client |
| httpx | 0.27.2 | Async HTTP (MSG91 calls + tests) |
| fakeredis | 2.26.1 | In-memory Redis for tests |
| aiosqlite | 0.20.0 | In-memory SQLite for tests |
| pytest-asyncio | 0.24.0 | Async test runner |

---

#### `server/core/config.py`
`pydantic-settings` `BaseSettings` subclass. Reads from `.env` file.

**Settings fields:**

| Field | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | postgres+asyncpg://... | Async DB connection |
| `REDIS_URL` | redis://localhost:6379 | Redis connection |
| `JWT_SECRET_KEY` | `change-me-...` | HS256 signing key |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 15 | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 30 | Refresh token TTL |
| `OTP_EXPIRY_SECONDS` | 300 | OTP TTL in Redis |
| `OTP_MAX_ATTEMPTS` | 5 | Max wrong OTP tries before invalidation |
| `OTP_RATE_LIMIT_PER_HOUR` | 5 | OTPs allowed per mobile per hour |
| `OPENROUTER_API_KEY` | `""` | AI (Phase 2+) |
| `WHATSAPP_TOKEN` | `""` | WhatsApp Cloud API (Phase 2+) |
| `RAZORPAY_*` | `""` | Payment gateway (Phase 1 billing) |
| `R2_*` | `""` | Cloudflare R2 file storage (Phase 1 docs) |
| `MSG91_AUTH_KEY` | `""` | OTP SMS provider |
| `MSG91_TEMPLATE_ID` | `""` | OTP SMS template |
| `GST_VERIFY_API_KEY` | `""` | GSTIN validation (Phase 2+) |
| `SENTRY_DSN` | `""` | Error tracking |
| `ENVIRONMENT` | `development` | `development` or `production` |

**Key behaviours:**
- `@property is_development` / `is_production`
- `@model_validator(mode="after")` raises `ValueError` if `JWT_SECRET_KEY` starts with `"change-me"` when `ENVIRONMENT == production`
- `@lru_cache` singleton: `settings = get_settings()` — import and use directly

---

#### `server/core/database.py`
Async SQLAlchemy engine, session factory, and dialect-aware custom types.

**What it does:**
- `create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)` — reconnects dropped connections
- `AsyncSessionLocal = async_sessionmaker(...)` with `expire_on_commit=False` — ORM objects stay accessible after commit
- `Base = DeclarativeBase()` — imported by all models
- `get_db()` — async generator dependency; commits on success, rolls back on exception

**Custom types (dialect-aware):**

| Export | PostgreSQL | SQLite (tests) | Used for |
|---|---|---|---|
| `JsonB` | `JSONB` | `JSON` | Structured JSON columns |
| `TextArray` | `ARRAY(Text)` | `JSON` (list) | String array columns |

This allows the same model code to run against both PostgreSQL (production) and SQLite (tests) without any changes.

---

#### `server/core/auth.py`
All OTP and JWT logic. No HTTP layer — pure functions testable in isolation.

**OTP functions:**

| Function | Description |
|---|---|
| `generate_otp()` | 6-digit string via `secrets.randbelow(900000) + 100000` |
| `store_otp(redis, otp_ref, mobile, otp, role)` | Stores `{mobile, otp, role, attempts: 0}` as JSON in Redis key `otp:{otp_ref}`, TTL = `OTP_EXPIRY_SECONDS` |
| `verify_otp(redis, otp_ref, mobile, otp)` | Atomic GETDEL fetch-and-delete. Mobile check → attempt limit → constant-time compare. Re-stores key on wrong attempt. Returns `role` on success. |
| `check_otp_rate_limit(redis, mobile)` | Redis pipeline INCR + conditional EXPIRE (`nx=True`). Returns `True` if under limit. |
| `send_otp_via_msg91(mobile, otp)` | HTTP POST to MSG91. In development with no `MSG91_AUTH_KEY`, logs OTP to console instead. |

**JWT functions:**

| Function | Description |
|---|---|
| `create_access_token(user_id, role)` | HS256 JWT, 15 min TTL, includes `jti: secrets.token_hex(16)` to prevent identical tokens |
| `create_refresh_token(user_id)` | HS256 JWT, 30 day TTL, includes `jti` |
| `store_refresh_token(redis, token, user_id)` | SHA-256 hash of token → `refresh:{hash}` → `user_id` in Redis |
| `invalidate_refresh_token(redis, token)` | Deletes the Redis key by hash |
| `decode_access_token(token)` | Decodes + validates; raises `JWTError` on failure; checks `type == "access"` |
| `decode_refresh_token(redis, token)` | Validates signature + checks Redis presence; returns `user_id` |

**Design note — atomic OTP verification:**  
`GETDEL` atomically fetches and deletes the Redis key in one command. Two concurrent requests with the same `otp_ref` cannot both pass — the second sees `None`. If validation fails, the key is re-stored with an incremented attempt counter so the user can retry.

---

#### `server/core/dependencies.py`
FastAPI dependency functions for auth and role enforcement.

| Dependency | Description |
|---|---|
| `get_redis(request)` | Returns `request.app.state.redis` |
| `get_current_user(credentials, db)` | Decodes Bearer token → `uuid.UUID(payload["sub"])` → DB lookup → returns `User`. Raises 401 for any failure. |
| `require_ca(user)` | Raises 403 if `user.role != "ca"` |
| `require_smb(user)` | Raises 403 if `user.role != "smb"` |

**SQLite compatibility note:** `payload["sub"]` is a string from JWT. `user_uuid = uuid.UUID(raw_id)` is done explicitly before the DB query because SQLAlchemy's UUID type calls `.hex` on the value, which fails on plain strings in SQLite.

---

### 2.3 SQLAlchemy Models

All models inherit `Base` from `core.database`. All UUID primary keys have **both**:
- `default=uuid.uuid4` — Python-side, used by ORM for in-session inserts
- `server_default=func.gen_random_uuid()` — SQL-side, used for raw SQL inserts

This dual-default pattern ensures IDs are available after `flush()` without a DB round-trip, and that direct SQL inserts (e.g. from Alembic seeds) also work.

All `server_default` columns that are read before commit also have a matching Python `default=` (CLAUDE.md rule 6).

---

#### `server/models/user.py` — `users` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `mobile` | VARCHAR(15) UNIQUE NOT NULL | 10-digit Indian mobile |
| `email` | VARCHAR(255) | optional |
| `full_name` | VARCHAR(255) NOT NULL | default `""` |
| `role` | VARCHAR(20) NOT NULL | CHECK `IN ('ca','smb')` |
| `is_active` | BOOLEAN | default `True` |
| `created_at` | TIMESTAMPTZ | `func.now()` |
| `updated_at` | TIMESTAMPTZ | `func.now()`, `onupdate=func.now()` |

**Relationships:** `ca_profile` (one-to-one, cascade delete), `smb_profile` (one-to-one, cascade delete), `notifications` (one-to-many, cascade delete)

---

#### `server/models/ca_profile.py` — `ca_profiles` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `user_id` | UUID FK→users | CASCADE delete |
| `icai_number` | VARCHAR(20) UNIQUE | no live verification in Phase 1 |
| `firm_name` | VARCHAR(255) | |
| `city` | VARCHAR(100) | |
| `state` | VARCHAR(100) | |
| `gstin` | VARCHAR(15) | |
| `plan` | VARCHAR(20) | CHECK `IN ('starter','growth','pro','firm')`, default `starter` |
| `plan_client_limit` | INTEGER | default `10` (Starter limit) |
| `plan_expires_at` | TIMESTAMPTZ | null = trial/free |
| `razorpay_subscription_id` | VARCHAR(100) | set by webhook |
| `created_at` | TIMESTAMPTZ | |

**Relationships:** `user`, `client_links`, `tasks`, `messages`, `invoices`

---

#### `server/models/smb_profile.py` — `smb_profiles` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `user_id` | UUID FK→users | CASCADE delete |
| `company_name` | VARCHAR(255) NOT NULL | required on creation |
| `company_type` | VARCHAR(50) | e.g. Pvt Ltd, LLP |
| `gstin` | VARCHAR(15) | |
| `pan` | VARCHAR(10) | |
| `turnover_range` | VARCHAR(20) | |
| `employee_count_range` | VARCHAR(20) | |
| `sectors` | TEXT[] | `TextArray` |
| `states` | TEXT[] | `TextArray` |
| `gst_registered` | BOOLEAN | default `False` |
| `gst_composition` | BOOLEAN | default `False` |
| `has_factory` | BOOLEAN | default `False` |
| `import_export` | BOOLEAN | default `False` |
| `is_listed` | BOOLEAN | default `False` |
| `standalone_plan` | VARCHAR(20) | default `free` |
| `created_at` | TIMESTAMPTZ | |

**Relationships:** `user`, `ca_links`, `tasks`, `documents`, `messages`, `invoices`, `health_scores`, `compliance_items`

---

#### `server/models/ca_client_link.py` — `ca_client_links` table

Junction table linking a CA to a client with invite state.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `ca_id` | UUID FK→ca_profiles | CASCADE delete |
| `client_id` | UUID FK→smb_profiles | CASCADE delete |
| `status` | VARCHAR | CHECK `IN ('pending','active','removed')`, default `pending` |
| `invited_at` | TIMESTAMPTZ | `func.now()` |
| `accepted_at` | TIMESTAMPTZ | set on acceptance |
| `removed_at` | TIMESTAMPTZ | set on soft-remove |

**Constraints:** `UNIQUE(ca_id, client_id)` — prevents duplicate links

**Business rules encoded here:**
- Pending invites do NOT count toward CA plan client limit (only `status='active'` does)
- Soft-remove: status set to `'removed'`, never hard-deleted
- Re-invite: if status is `'removed'`, reset to `'pending'` (idempotent)

---

#### `server/models/compliance_item.py` — two tables

**`compliance_items`** — Master catalogue (seed data, not user-generated):

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(100) PK | human-readable slug, e.g. `gst_r1_monthly` |
| `name` | VARCHAR(255) NOT NULL | display name |
| `compliance_type` | VARCHAR(50) NOT NULL | GST / Labour / ROC / etc. |
| `frequency` | VARCHAR(20) | monthly / quarterly / annual |
| `applicable_conditions` | JSONB | which clients this applies to |
| `penalty_per_day` | INTEGER | in paise |
| `document_checklist` | TEXT[] | |
| `ca_action_required` | BOOLEAN | default `True` |

**`client_compliance_items`** — Per-client tracking instance:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `client_id` | UUID FK→smb_profiles | CASCADE delete |
| `ca_id` | UUID FK→ca_profiles | nullable |
| `compliance_item_id` | VARCHAR FK→compliance_items | |
| `financial_year` | VARCHAR(10) NOT NULL | e.g. `2024-25` |
| `due_date` | DATE NOT NULL | `Date()` not `DateTime` |
| `status` | VARCHAR | CHECK 6 values, default `pending` |
| `completed_at` | TIMESTAMPTZ | |

---

#### `server/models/task.py` — `tasks` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `ca_id` | UUID FK→ca_profiles | CASCADE delete |
| `client_id` | UUID FK→smb_profiles | CASCADE delete |
| `compliance_item_id` | UUID FK→client_compliance_items | nullable |
| `title` | VARCHAR(500) NOT NULL | |
| `assigned_to` | VARCHAR(10) | CHECK `IN ('ca','client')` |
| `status` | VARCHAR | CHECK 5 values, default `pending` |
| `due_date` | DATE | `Date()` type, not datetime |
| `created_by` | VARCHAR(10) | CHECK `IN ('ca','client','system')` |

---

#### `server/models/document.py` — `documents` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `client_id` | UUID FK→smb_profiles | CASCADE delete |
| `ca_id` | UUID FK→ca_profiles | nullable |
| `task_id` | UUID FK→tasks | nullable |
| `file_name` | VARCHAR(500) NOT NULL | |
| `file_size_bytes` | BIGINT NOT NULL | |
| `mime_type` | VARCHAR(100) NOT NULL | validated by magic bytes, not extension |
| `r2_key` | VARCHAR(500) UNIQUE NOT NULL | Cloudflare R2 object key |
| `document_type` | VARCHAR(50) | |
| `financial_year` | VARCHAR(10) | |
| `is_deleted` | BOOLEAN | soft delete, default `False` |

---

#### `server/models/message.py` — `messages` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `ca_id` | UUID FK→ca_profiles | NOT NULL |
| `client_id` | UUID FK→smb_profiles | NOT NULL |
| `sender_role` | VARCHAR(10) | CHECK `IN ('ca','client')` |
| `content` | TEXT NOT NULL | |
| `attached_document_id` | UUID FK→documents | nullable |
| `linked_task_id` | UUID FK→tasks | nullable |
| `is_read` | BOOLEAN | default `False` |

**Index:** `idx_messages_thread` on `(ca_id, client_id)` for fast thread queries

---

#### `server/models/invoice.py` — `invoices` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `ca_id` | UUID FK→ca_profiles | NOT NULL |
| `client_id` | UUID FK→smb_profiles | NOT NULL |
| `invoice_number` | VARCHAR(50) UNIQUE NOT NULL | CA-generated |
| `line_items` | JSONB NOT NULL | `[{description, amount}]` |
| `subtotal` | INTEGER NOT NULL | in paise |
| `gst_rate` | INTEGER | default `18` |
| `gst_amount` | INTEGER NOT NULL | in paise |
| `total_amount` | INTEGER NOT NULL | in paise |
| `status` | VARCHAR | CHECK `IN ('draft','sent','paid','overdue','cancelled')` |
| `razorpay_payment_link_url` | VARCHAR(500) | |

---

#### `server/models/health_score.py` — `health_scores` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `client_id` | UUID FK→smb_profiles | NOT NULL |
| `score` | INTEGER NOT NULL | CHECK `BETWEEN 0 AND 100` |
| `breakdown` | JSONB | `{gst, labour, roc, licences}` |
| `calculated_at` | TIMESTAMPTZ | |

**Index:** `idx_health_scores_client` on `client_id`  
**Note:** Calculated asynchronously every 24 hours (Phase 2 — not yet implemented)

---

#### `server/models/payment.py` — `payments` table (stub)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `invoice_id` | UUID FK→invoices | NOT NULL |
| `razorpay_payment_id` | VARCHAR(100) UNIQUE | from webhook |
| `amount` | INTEGER | in paise |
| `status` | VARCHAR(20) | CHECK `IN ('captured','failed','refunded')` |
| `webhook_payload` | JSONB | full raw webhook stored for audit |

**Rule:** Payment status is ONLY set from Razorpay webhooks, never from client-side requests.

---

#### `server/models/regulation.py` — `regulations` table (stub)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `source_url` | VARCHAR(500) | scraped government notification |
| `title` | VARCHAR(500) | |
| `raw_content` | TEXT | |
| `compliance_type` | VARCHAR(50) | |
| `sectors_affected` | TEXT[] | `TextArray` |
| `states_affected` | TEXT[] | `TextArray` |
| `company_types_affected` | TEXT[] | `TextArray` |
| `action_required_by` | DATE | |
| `plain_english_summary` | TEXT | AI-generated (Phase 2+) |
| `ca_summary` | TEXT | AI-generated CA-focused summary |
| `is_classified` | BOOLEAN | default `False` |
| `scraped_at` | TIMESTAMPTZ | |

**Note:** Populated by `regulation_scraper_job` (Phase 2+)

---

#### `server/models/notification.py` — `notifications` table (stub)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | dual default |
| `user_id` | UUID FK→users | NOT NULL |
| `notification_type` | VARCHAR(20) | CHECK `IN ('whatsapp','push','email','sms')` |
| `content` | TEXT | |
| `status` | VARCHAR(20) | CHECK `IN ('pending','sent','delivered','failed','read')` |
| `extra_data` | JSONB | column name `metadata` (ORM attr renamed to avoid SQLAlchemy conflict) |
| `sent_at` | TIMESTAMPTZ | |
| `delivered_at` | TIMESTAMPTZ | |

**Note on naming:** SQLAlchemy `DeclarativeBase` has a `.metadata` attribute. The ORM attribute is named `extra_data` with `mapped_column("metadata", ...)` to avoid the conflict.

---

### 2.4 Alembic Migration

#### `server/migrations/env.py`
Async-compatible Alembic env. Uses `run_async_migrations()` with `asyncpg` driver. Imports `Base.metadata` from `core.database` so all models are auto-discovered.

#### `server/migrations/versions/001_initial_schema.py`
Creates all 14 tables in FK dependency order:

1. `users`
2. `ca_profiles` (FK → users)
3. `smb_profiles` (FK → users)
4. `ca_client_links` (FK → ca_profiles, smb_profiles)
5. `compliance_items`
6. `client_compliance_items` (FK → smb_profiles, ca_profiles, compliance_items)
7. `tasks` (FK → ca_profiles, smb_profiles, client_compliance_items)
8. `documents` (FK → smb_profiles, ca_profiles, tasks, client_compliance_items)
9. `messages` (FK → ca_profiles, smb_profiles, documents, tasks) + index
10. `invoices` (FK → ca_profiles, smb_profiles)
11. `health_scores` (FK → smb_profiles) + index
12. `payments` (FK → invoices)
13. `regulations`
14. `notifications` (FK → users)

Downgrade reverses in reverse order.

---

### 2.5 Routers

All routers follow the standard response envelope:
```json
{ "success": true|false, "data": {...}|null, "meta": {...}|null, "error": null|{"code":"...","message":"..."} }
```

Error responses use `raise HTTPException(status_code=..., detail=_error("CODE", "message"))`.  
The custom exception handler in `main.py` detects dicts with an `"error"` key and passes them through unchanged.

---

#### `server/routers/auth.py`
No auth required. Three endpoints.

**`POST /v1/auth/otp/send`**
- Input: `{mobile: str (10 digits), role: "ca"|"smb"}`
- Validates mobile format via regex
- Rate-limit check: max 5 OTPs/hour per mobile (Redis pipeline)
- Generates OTP, calls MSG91 (or logs to console in dev), stores in Redis
- Returns: `{otp_ref: str, expires_in: 300}`

**`POST /v1/auth/otp/verify`**
- Input: `{mobile, otp, otp_ref}`
- Calls `verify_otp()` — raises 400 on wrong OTP, expired, or too many attempts
- Upserts User (creates on first login, fetches on return login)
- Role mismatch check: existing user with different role → 400 `ROLE_MISMATCH`
- Issues access token (15 min) + refresh token (30 days), stores refresh token in Redis
- Returns: `{access_token, refresh_token, user: {id, mobile, full_name, role, is_active}, is_new_user}`

**`POST /v1/auth/token/refresh`**
- Input: `{refresh_token: str}`
- Validates signature + Redis presence
- Reloads user for current role (long-lived tokens, role could change)
- Returns: `{access_token}` (new 15-min token)

---

#### `server/routers/ca.py`
All endpoints require `role = "ca"` (`require_ca` dependency). All queries filter by `CAProfile.id` derived from the authenticated user — a CA never sees another CA's data.

**`GET /v1/ca/profile`**
- Returns user fields + CA profile (null-safe if profile not yet created) + `stats.active_client_count`
- Active count queries only `status='active'` links

**`PUT /v1/ca/profile`**
- Input (all optional): `{full_name, icai_number, firm_name, city, state, gstin}`
- Creates `CAProfile` on first call with Python-side `plan="starter"`, `plan_client_limit=10`
- Partial patch: only fields explicitly provided are updated
- `full_name` is written to `users` table, all other fields to `ca_profiles`

**`GET /v1/ca/clients`**
- Query params: `?status=active|pending|removed`, `?sort=health_score|name|last_activity`, `?page=1`, `?limit=20`
- Returns paginated list with health score via correlated scalar subquery (latest score per client)
- Count query is separate (avoids subquery-in-COUNT issues)
- Alias `ClientUser = aliased(User, name="client_user")` avoids ORM ambiguity with CA's own User row

**`POST /v1/ca/clients/invite`**
- Input: `{mobile: str, company_name: str}`
- If mobile has no account: creates `User(role='smb')` + `SMBProfile` shell
- If mobile belongs to a CA: 400 `INVALID_ROLE`
- If link already `active|pending`: 409 `ALREADY_LINKED`
- If link was `removed`: re-invites (resets to `pending`)
- Plan limit check: if `active_count >= plan_client_limit` → `plan_limit_warning: true` in response (not a hard block — spec §5.1.1)
- Returns: `{invite_id, status, plan_limit_warning}`
- Status: 201

**`POST /v1/ca/clients/import`**
- Input: `{clients: [{mobile, company_name, gstin?, email?}]}`
- Same logic as single invite, run in a loop
- Per-item errors are caught and counted — one failure doesn't abort the batch
- Returns: `{invited, already_linked, failed, plan_limit_warning}`

**`DELETE /v1/ca/clients/{client_id}`**
- Soft-remove: sets `status='removed'`, `removed_at=now()`
- 404 if client not found, belongs to different CA, or already removed
- Double-remove returns 404 (idempotent from caller's perspective)

---

#### `server/routers/client.py`
All endpoints require `role = "smb"` (`require_smb` dependency). All queries filter by `SMBProfile.user_id == current_user.id`.

**`GET /v1/client/profile`**
- Returns user fields + SMB profile (null-safe) + active CA link (null if no active link)
- Only `status='active'` links are returned as `linked_ca`; pending links are not shown
- `CAUser = aliased(User, name="ca_user")` avoids ORM ambiguity in the join

**`PUT /v1/client/profile`**
- Input (all optional except `company_name` on first creation): all SMBProfile fields + `full_name`
- First creation: `company_name` is required (NOT NULL in DB); 422 `COMPANY_NAME_REQUIRED` if missing
- Updates: blank `company_name` rejected; all other fields are partial patch
- TODO Phase 2: trigger async health score recalculation after every update

**`POST /v1/client/invite/accept/{invite_id}`**
- Ownership check: `link.client_id == smb.id` — 403 `FORBIDDEN` if mismatch (a client cannot accept another client's invite)
- 400 `ALREADY_ACCEPTED` if status is already `active`
- 400 `INVITE_REMOVED` if status is `removed`
- Sets `status='active'`, `accepted_at=now()`
- Returns: `{link_id, status, accepted_at}`

---

### 2.6 Tests

**Test infrastructure:**
- Database: `sqlite+aiosqlite:///:memory:` — spun up and torn down per test function
- SQLite FK pragma enabled via `event.listens_for(engine.sync_engine, "connect")` — matches PostgreSQL FK enforcement
- Redis: `fakeredis.aioredis.FakeRedis(decode_responses=True)` — flushed after each test
- HTTP client: `httpx.AsyncClient(transport=ASGITransport(app=app))`
- Dependency overrides: `app.dependency_overrides[get_db]` and `app.state.redis`

**Shared fixtures in `conftest.py`:**

| Helper | Returns | Description |
|---|---|---|
| `make_ca_user(db, mobile)` | `(User, bearer_token)` | Creates CA user + JWT |
| `make_ca_profile(db, user)` | `CAProfile` | Creates starter CA profile |
| `make_smb_user(db, mobile)` | `(User, bearer_token)` | Creates SMB user + JWT |
| `make_smb_profile(db, user, name)` | `SMBProfile` | Creates SMB profile |

---

**Test files and coverage:**

| File | Tests | What it covers |
|---|---|---|
| `test_auth.py` | 21 | OTP send/verify/refresh — happy + error paths |
| `test_ca.py` | 58 | All 6 CA endpoints — all 8 CLAUDE.md categories |
| `test_client.py` | 30 | All 3 client endpoints — all 8 CLAUDE.md categories |
| `test_models.py` | 65 | Create/query/constraints/cascade for all 14 models |
| `test_core_auth.py` | 35 | OTP logic, JWT encode/decode, rate limiting, Redis atomicity |
| `test_config.py` | 7 | Settings loading, production guard, env var override |
| `test_dependencies.py` | 15 | `get_current_user`, `require_ca`, `require_smb` |
| `test_exception_handlers.py` | 13 | All three global exception handlers + envelope shape |
| `test_middleware.py` | 12 | CORS, health check, unknown routes |
| `test_integration_auth.py` | 15 | Full login → refresh → protected route flow |
| `test_concurrency.py` | 11 | OTP verify race condition, refresh token double-use |
| `test_performance.py` | 18 | Latency thresholds (300 ms per request, 50 ms health check) |
| **Total** | **300** | |

---

## 3. Key Design Decisions

### Atomic OTP verification
`verify_otp` uses Redis `GETDEL` (fetch + delete in one command). Two concurrent requests with the same `otp_ref` cannot both pass — the second sees `None`. The key is re-stored on wrong attempts so the user can retry, but the re-store happens with the incremented counter so brute-force is still blocked after 5 attempts.

### Refresh token revocation
Refresh tokens are stored in Redis as `refresh:{sha256(token)}` → `user_id`. The SHA-256 hash means the raw token never touches Redis directly. Checking Redis presence at decode time means logout (delete key) immediately invalidates the token even before JWT expiry.

### Dialect-aware types for testability
`_JsonB` and `_TextArray` are `TypeDecorator` wrappers that use `JSONB`/`ARRAY` on PostgreSQL and `JSON` on SQLite. This lets the entire test suite run without PostgreSQL, making tests instant and dependency-free.

### Dual UUID defaults
Every UUID primary key has `default=uuid.uuid4` (Python) + `server_default=func.gen_random_uuid()` (SQL). The Python default populates the ID immediately after `db.add()` + `db.flush()`, without needing a `db.refresh()`. The server default handles raw SQL inserts (e.g. from migrations or external tools).

### Plan limit enforcement (soft)
Per spec §5.1.1: "not hard-blocked for 7 days." Exceeding `plan_client_limit` sets `plan_limit_warning: true` in the response but the invite is still created. Hard enforcement is deferred to the billing phase.

### CA isolation
Every CA query includes `WHERE ca_id = {current_ca_profile.id}`. The CA profile is always loaded fresh from DB using the authenticated user's `user_id`, never from the token payload. This prevents privilege escalation.

### SMB invite ownership
`POST /client/invite/accept/:id` checks `link.client_id == smb.id` (not just that the link exists). A client cannot accept another client's invite even if they know the UUID.

---

## 4. Patterns & Conventions

### Response envelope
Every endpoint returns:
```python
{"success": True, "data": {...}, "meta": None, "error": None}      # success
{"success": False, "data": None, "meta": None, "error": {"code": "CODE", "message": "..."}}  # error
```

Raise errors as:
```python
raise HTTPException(status_code=400, detail=_error("CODE", "Human-readable message"))
```

### Pagination meta
Paginated list endpoints return:
```python
_success(items, meta={"page": 1, "total": 100, "limit": 20})
```

### UTC everywhere
All timestamps are stored as `DateTime(timezone=True)` (TIMESTAMPTZ in PostgreSQL).  
`_utc_now()` helper: `datetime.now(tz=timezone.utc)` — never use `datetime.utcnow()` (naive).

### Partial updates
PUT endpoints use the "only update if provided" pattern:
```python
if body.field_name is not None:
    model.field_name = body.field_name
```
This means sending `{}` is a valid no-op. Sending `null` is not (Pydantic strips it; use `""` to clear a field).

### Empty string → NULL
String fields that should be nullable accept empty string as a clear signal:
```python
ca.icai_number = body.icai_number or None  # "" → NULL
```

---

## 5. Known TODOs

Items that are explicitly deferred to later phases. Do NOT implement these until the corresponding phase is reached.

| TODO | Location | Phase |
|---|---|---|
| Health score recalculation on `PUT /client/profile` | `routers/client.py` | Phase 2 |
| Async health score calculation job (every 24h) | `models/health_score.py` | Phase 2 |
| ICAI number live verification | `routers/ca.py` | Phase 2+ |
| WhatsApp invite notification on `POST /ca/clients/invite` | `routers/ca.py` | Phase 2 |
| Hard plan limit enforcement with 7-day grace period | `routers/ca.py` | Phase 1 Billing |
| Regulation scraper job | `models/regulation.py` | Phase 2 |
| AI-generated summaries | `models/regulation.py` | Phase 2+ |
| Push/email/SMS notification sending | `models/notification.py` | Phase 2 |
| Razorpay webhook handler | `models/payment.py` | Phase 1 Billing |
| Document upload (R2 presigned URLs, magic byte validation) | `models/document.py` | Phase 1 |
| CA/client messaging endpoints | `models/message.py` | Phase 1 |
| Compliance calendar endpoints | `models/compliance_item.py` | Phase 1 |
| Task system endpoints | `models/task.py` | Phase 1 |
| Invoice generation + Razorpay payment links | `models/invoice.py` | Phase 1 Billing |
