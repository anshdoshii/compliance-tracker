# PR Review Checklist & Learnings

A living document of what to check when reviewing PRs on this project, built from real misses.

---

## What to always do first

1. **Read the PR description** — understand intent before reading code.
2. **Fetch the diff** — don't rely on summaries. Use `gh pr diff <number>` or the `.diff` URL.
3. **Check existing bot reviews** — CodeRabbit, GitHub Actions, linters often catch things faster than reading line by line. Check the PR comments tab before writing your own review.
4. **Read the critical files directly** — for auth and DB changes, read the actual source, not just the diff.

---

## Security checklist

### Auth / JWT
- [ ] Secret keys have **no insecure defaults** that could slip to production. If a placeholder default exists, a `@model_validator` must reject it when `ENVIRONMENT=production`.
- [ ] `sub` (and any other JWT claim used for DB lookups) is **validated as the correct type** (UUID, int, etc.) before the query — a missing or malformed claim should return 401, not 500.
- [ ] JWT exceptions are re-raised with `from exc` so the original traceback appears in Sentry.

### OTP / SMS
- [ ] OTP is **sent before stored**. If the SMS gateway fails, no stale entry should linger in Redis.
- [ ] External SMS/email API responses are checked at the **application level**, not just HTTP level. MSG91 returns `{"type": "error"}` with HTTP 200.
- [ ] Rate limiting uses **atomic Redis operations** (pipeline with `INCR` + `EXPIRE NX`). Separate INCR and EXPIRE have a TOCTOU gap that can produce a key with no TTL.

### Input validation
- [ ] Pydantic 422 error responses **strip raw input values** (`input` field). Submitted OTPs, mobile numbers, and tokens must not appear in error bodies.
- [ ] Role mismatches on existing users are **rejected explicitly**, not silently ignored with the DB role winning.

### CORS
- [ ] `allow_origins` is **never `["*"]`**, even in development. Use explicit `http://localhost:PORT` origins.

---

## ORM type correctness (SQLAlchemy 2.0 Mapped)

`Mapped[X]` takes a **Python type**, not a SQLAlchemy column type. Common mistakes:

| Wrong | Correct |
|---|---|
| `Mapped[DateTime]` | `Mapped[datetime]` (import from `datetime`) |
| `Mapped[DateTime \| None]` | `Mapped[datetime \| None]` |
| `Mapped[DateTime]` for a `Date()` column | `Mapped[date]` with `mapped_column(Date())` |

**Always cross-check the ORM model type against the Alembic migration column type.** If the migration says `sa.Date()`, the ORM must say `Mapped[date]` + `mapped_column(Date())`, not `DateTime`.

Files to check on this project: every model under `server/models/`.

---

## Database / migration checklist

- [ ] `due_date` columns use `Date()` (not `DateTime`) in both migration and ORM.
- [ ] Nullable columns with a `CHECK` constraint: ensure `NULL` is either excluded from the CHECK or the column is made `NOT NULL` with a `server_default`. A nullable column with a CHECK only validates non-null values — NULL always passes.
- [ ] `updated_at` columns have `onupdate=func.now()` in the ORM **or** a DB-level trigger. Without one of these, the column never updates automatically.
- [ ] New indexes are created on FK columns used in `WHERE` filters for role-scoped queries (`ca_id`, `client_id`).

---

## Exception chaining (Ruff B904)

Any `raise X` inside an `except` block must use `raise X from exc`:

```python
# Wrong — loses original traceback
except JWTError:
    raise HTTPException(...)

# Correct
except JWTError as exc:
    raise HTTPException(...) from exc
```

---

## Test coverage gaps to check

Beyond happy-path tests, always verify:

- [ ] Lockout after max wrong OTP attempts (key is deleted, not just incremented).
- [ ] Refresh token is rejected after the user is deactivated.
- [ ] Role-enforcement dependencies (`require_ca`, `require_smb`) reject the wrong role.
- [ ] JWT with missing or non-UUID `sub` returns 401, not 500.
- [ ] Soft-deleted records (`is_deleted=True`) are excluded from all list endpoints.

---

## What CodeRabbit catches that's easy to miss

- `Mapped[DateTime]` vs `Mapped[datetime]` type annotation mismatches across all model files.
- Silent role mismatch on existing users during OTP verify.
- Non-atomic Redis patterns (INCR + EXPIRE without a pipeline).
- Exception chaining (`from exc`) omissions — shows up as Ruff B904.
- Validation errors leaking raw input fields in 422 responses.
- HTTP-200 API errors from third-party gateways (MSG91, Razorpay) not being checked.

**Lesson: always check the PR's Reviews/Comments tab for bot reviews before starting a manual review.**

---

## How to run the test suite

```bash
cd complianceos/server
pip install -r requirements.txt
pytest tests/ -v
```

Tests use in-memory SQLite + FakeRedis — no Docker needed.
