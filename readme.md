# ComplianceOS — Product Specification
**Version:** 1.0  
**Status:** Pre-build blueprint  
**Last updated:** April 2026

---

## 1. Vision

ComplianceOS is India's first two-sided compliance platform that serves both **Chartered Accountants (CAs)** and **small-to-mid-size businesses (SMBs)** in a single unified app.

- **For CAs:** A professional practice management tool to manage all clients, deadlines, documents, and communications from one dashboard.
- **For SMBs:** A self-serve compliance portal to track deadlines, upload documents, communicate with their CA, and understand their compliance health — without needing to be a compliance expert.

The analogy: **Shopify is to merchants what ComplianceOS is to CAs and their clients.** Shopify gave merchants a store and gave customers a shopping experience. We give CAs a practice and give their clients visibility.

---

## 2. The Problem

### For CAs
- Managing 50–200 clients via WhatsApp, Excel, and email
- No single place to see which clients are at risk of missing deadlines
- Clients call/message asking "did you file my GST?" — eating up hours every week
- Document collection is a nightmare (clients send blurry photos on WhatsApp)
- Billing clients is informal — no proper invoice trail
- No way to scale practice without hiring more people

### For SMBs
- 1,500+ compliance requirements across GST, Labour, ROC, sector licences
- No visibility into what's due when — they rely entirely on their CA remembering
- Get shocked by penalties after the fact
- Don't understand what a GST notice or ROC filing means
- No easy way to pay their CA digitally
- Use WhatsApp for everything — no paper trail, no accountability

---

## 3. The Solution: Two Personas, One Platform

### 3.1 User Types

| Type | Who they are | How they access |
|---|---|---|
| **CA User** | Chartered Accountant or CA firm | Web (primary) + Mobile |
| **SMB User** (linked) | Business client of a CA on the platform | Mobile (primary) + Web |
| **SMB User** (standalone) | Business with no CA, self-serve | Mobile (primary) + Web |

### 3.2 Key Principle: Same App, Role-Based Experience

When a user logs in, the app detects their role and shows the appropriate interface. A CA sees their practice dashboard. A business owner sees their compliance portal. The underlying data is shared — a task the CA creates appears in the client's task list automatically.

---

## 4. Pricing & Plans

### 4.1 CA Plans (B2B SaaS)

CAs pay based on the number of linked clients. This is the core monetisation engine.

| Plan | Price | Linked clients | Features |
|---|---|---|---|
| **Starter CA** | ₹999/month | Up to 10 clients | Client dashboard, compliance calendar, document requests, basic messaging |
| **Growth CA** | ₹2,499/month | Up to 50 clients | All Starter + AI assistant, regulation alerts, invoice generation, CA billing to clients |
| **Pro CA** | ₹5,999/month | Up to 150 clients | All Growth + multi-staff accounts, white-labelled client portal, analytics, priority support |
| **Firm CA** | ₹12,999/month | Unlimited clients | All Pro + API access, custom domain, dedicated account manager, SLA guarantee |

**Billing logic:**
- CA pays at the start of each billing cycle
- Linked clients = clients who have accepted the CA's invitation and activated their portal
- Pending invites do not count toward the limit
- If a CA exceeds their plan limit mid-cycle, they are nudged to upgrade (not hard-blocked for 7 days)
- Annual billing = 2 months free

### 4.2 SMB Standalone Plans (B2C SaaS)

For businesses that don't have a CA on the platform, or want to manage compliance themselves.

| Plan | Price | Features |
|---|---|---|
| **Free** | ₹0 | 5 compliance items tracked, basic calendar, 500MB document storage |
| **Solo** | ₹499/month | Unlimited compliance tracking, full calendar, 5GB storage, AI explainer (50 queries/month), WhatsApp alerts |
| **Business** | ₹1,499/month | All Solo + AI assistant (unlimited), GST-ready invoice generation, multi-user (3 seats), CA connect (invite your CA for free) |

### 4.3 Plan Interaction Rules

- A linked SMB client gets their portal **for free** — the CA pays for them
- If a linked client's CA downgrades or removes them, they are offered a standalone plan at a discount
- A standalone SMB can invite their CA to join the platform — the CA gets a 30-day free trial
- CAs can have a mix: some clients on the platform (linked), some not yet onboarded

---

## 5. Feature Specification

### 5.1 CA Dashboard

**5.1.1 Client Overview**
- List of all linked clients with compliance health score (0–100, colour coded: red/amber/green)
- Sortable by: health score, next deadline, last activity, alphabetical
- Filter by: status (at risk, on track, inactive), compliance type, industry sector
- Quick action: "Send reminder to all clients with overdue items" (WhatsApp bulk message)
- Search clients by name, GST number, or PAN

**5.1.2 Task Management**
- Master task list across all clients
- Each task has: client name, task type, due date, status (pending / in progress / waiting on client / done), assigned staff member
- CA can create tasks for clients (appears in client's portal as a to-do)
- CA can request documents (client gets a notification and upload link)
- Tasks are auto-generated from the compliance calendar based on client profile
- Task templates: CA can save custom task templates for recurring workflows (e.g., "Monthly GST package")

**5.1.3 Compliance Calendar**
- Unified calendar view across all clients
- Colour-coded by client or by compliance type (toggle)
- Week/month/agenda views
- Clicking a deadline shows: which clients it affects, current status, quick action buttons
- Export to Google Calendar / iCal

**5.1.4 Document Centre**
- Request documents from specific clients (with deadline and instructions)
- Client receives WhatsApp notification + in-app notification
- Client uploads directly in-app — no email needed
- CA sees upload status in real time
- Documents auto-tagged by: client, compliance type, financial year
- Bulk download per client or per compliance type

**5.1.5 Client Messaging**
- Threaded chat per client (not a group chat — one-to-one per client)
- Can attach documents, link specific tasks
- Templates for common messages: "Your GST filing is complete", "We need your bank statement by [date]"
- Message history searchable
- CA can mark messages as requiring action

**5.1.6 AI Assistant (CA-facing)**
- Understands the CA's client context — knows their clients, their compliance status, pending tasks
- Sample queries:
    - "Draft a reply to the GST notice for Krishna Industries"
    - "Which of my clients have a PF return due in the next 10 days?"
    - "Summarise the latest GST council circular and tell me which of my clients are affected"
    - "Generate a compliance checklist for a new pharma manufacturer in Gujarat"
- Powered by OpenRouter (model routing: Claude for complex legal drafting, fast model for simple lookups)
- Responses are role-aware: professional, legally precise, CA-grade language
- AI never gives definitive legal advice — always frames as "based on current regulations" with a disclaimer

**5.1.7 Billing Module (CA billing their clients)**
- CA can generate invoices for compliance services rendered to a client
- Invoice auto-fills: CA GSTIN, client details, service description, SAC code (998211 for legal/CA services), GST @ 18%
- Supports: per-filing fees, monthly retainer, per-hearing fees (for litigation support)
- Client receives invoice via WhatsApp + in-app
- Client can pay via UPI (Razorpay integration) directly in-app
- CA sees payment status in real time
- Export invoices as PDF, export monthly statement as Excel

**5.1.8 Regulation Monitor**
- Daily digest of new government notifications: GST Council, MCA, EPFO, ESIC, RBI, SEBI, FSSAI, State labour departments
- AI reads each circular and classifies: which compliance type, which sectors affected, which states affected
- CA sees only alerts relevant to their client base
- One-click: "Notify all affected clients" — sends a plain-language WhatsApp summary to clients

**5.1.9 Analytics (Pro and Firm plans)**
- Revenue by client, by month
- Collection rate (invoiced vs paid)
- Client health score distribution over time
- Most common compliance types across client base
- Staff productivity (tasks completed per week)

---

### 5.2 Client Portal (SMB View)

**5.2.1 Compliance Health Dashboard**
- Single health score (0–100) with breakdown by category: Tax, Labour, Statutory Filings, Licences
- "What's urgent" — 3 most time-sensitive items highlighted at the top
- Plain-language status: "You're mostly on track. One GST filing needs attention."
- History chart: health score over the past 6 months

**5.2.2 My Deadlines**
- Upcoming compliance deadlines in a clean calendar/list view
- Each item shows: what it is, due date, current status, who's responsible (CA or client)
- Overdue items highlighted in red with penalty information if applicable
- Filter by: upcoming (7/30/90 days), overdue, completed

**5.2.3 My Tasks**
- Tasks assigned by the CA appear here automatically
- Client can mark tasks as done (e.g., "Uploaded bank statement")
- Document upload directly from this screen
- Client can add notes to a task
- Notifications: WhatsApp + push notification when a new task is assigned

**5.2.4 My Documents**
- Organised vault of all uploaded documents
- Folder structure: by financial year, by compliance type
- CA-uploaded documents (notices, filed returns, acknowledgements) are visible here
- Download any document
- 5GB storage on Solo plan, 20GB on Business plan, unlimited for CA-linked clients

**5.2.5 Chat with My CA**
- Threaded chat with their linked CA
- Clients on standalone plans see a "Find a CA" prompt instead
- Can attach documents from their vault or upload new
- Message read receipts
- CA response time shown ("Typically responds within 4 hours")

**5.2.6 AI Explainer (SMB-facing)**
- Different from CA's AI — simpler, friendlier, explains things in plain language
- Sample queries:
    - "What is GSTR-1 and why do I need to file it?"
    - "We got a notice from the GST department — what does it mean?" (upload the notice)
    - "What is the penalty if we miss TDS payment?"
    - "My CA asked for Form 16A — what is that?"
- Responses in simple English (or Hindi — language selector)
- Never replaces CA — always adds "Your CA can help you with this. Message them here →"
- SMB plan: 50 queries/month on Solo, unlimited on Business

**5.2.7 Pay My CA**
- See all invoices from their CA
- Pay via UPI, net banking, or card (Razorpay)
- Payment history and receipts downloadable

**5.2.8 Standalone SMB Extra: Self-Serve Compliance**
- For SMBs without a CA
- Profile setup: company type, turnover, employee count, sector, states of operation
- System auto-generates their full compliance calendar
- Can mark items as "handled manually" (e.g., "Filed GST myself")
- Directory: find and invite a CA from the platform (CAs can create public profiles)

---

### 5.3 Onboarding Flows

**5.3.1 CA Onboarding**
1. Sign up with mobile OTP
2. Enter: Full name, CA membership number (ICAI), firm name, city
3. ICAI number verified against public directory (async, non-blocking)
4. Plan selection (with 30-day free trial on Growth plan)
5. Import clients: CSV upload (name, mobile, email, GST number) or manual add
6. System sends WhatsApp invitation to each client: "Your CA [name] has added you to ComplianceOS. Click to set up your free compliance portal."
7. CA sets up their first compliance calendar — guided setup by sector

**5.3.2 SMB Client Onboarding (via CA invite)**
1. Receives WhatsApp/SMS invite from CA
2. Clicks link → lands on mobile-optimised web page
3. Enters mobile OTP to verify
4. Short profile setup: company name, GST number (optional), industry
5. Portal is immediately populated with tasks and calendar from CA
6. Prompted to download the app

**5.3.3 SMB Standalone Onboarding**
1. Downloads app or visits web
2. Mobile OTP login
3. Company profile setup: type, turnover range, employee count, sector, states
4. System generates compliance calendar
5. Free plan activated — upgrade prompt after seeing the calendar

---

## 6. Technical Architecture

### 6.1 Frontend
- **Framework:** Flutter (single codebase for Android, iOS, Web, Desktop)
- **State management:** Riverpod
- **HTTP client:** Dio with interceptors for auth token refresh
- **Local storage:** Hive (lightweight, fast, works offline)
- **Offline sync:** SQLite via drift — key screens (task list, calendar, chat) work offline
- **Real-time:** WebSocket for chat and live notifications
- **File handling:** file_picker, cached_network_image

### 6.2 Backend (Single Python Server)
- **Framework:** FastAPI (async, native streaming support for AI)
- **Auth:** JWT (access token 15min, refresh token 30 days) + OTP via SMS (Twilio/MSG91)
- **Task queue:** Celery + Redis for background jobs
- **ORM:** SQLAlchemy (async) + Alembic for migrations
- **File storage:** Cloudflare R2 (S3-compatible, cheaper than AWS S3)
- **Cache:** Redis (session cache, CNR lookup cache, regulation alerts)

### 6.3 AI Layer
- **Provider:** OpenRouter (model routing)
    - Complex legal drafting → `anthropic/claude-sonnet-4-5`
    - Fast lookups, classification → `google/gemini-flash-1.5`
    - SMB explainer (Hindi) → multilingual model via OpenRouter
- **RAG pipeline:** pgvector (lives in Postgres — no separate infra)
    - Corpus: GST Act, Companies Act, Labour laws, ESIC/EPF regulations, FSSAI guidelines
    - Updated monthly with new circulars
- **Streaming:** Server-Sent Events (SSE) from FastAPI → Flutter StreamBuilder
- **Context injection:** Before every AI call, inject relevant client context (compliance status, pending tasks, recent notices)

### 6.4 Database (PostgreSQL)
Key tables:
- `users` — all users (CA and SMB), role field
- `ca_profiles` — extended profile for CA users
- `smb_profiles` — extended profile for SMB users
- `ca_client_links` — many-to-many: which CAs manage which clients
- `compliance_items` — master list of compliance requirements (populated from regulation database)
- `client_compliance_items` — per-client compliance tracking (status, due date, assigned CA)
- `tasks` — tasks assigned by CA to client or to self
- `documents` — metadata for uploaded files (actual files in R2)
- `messages` — CA-client chat messages
- `invoices` — CA-to-client invoices
- `payments` — payment records (Razorpay webhook updates)
- `regulations` — scraped government notifications, classified by type/sector
- `notifications` — notification log (WhatsApp, push, email)

### 6.5 External Integrations
- **WhatsApp Business API:** Meta Cloud API (not a third-party proxy) — for notifications and bulk alerts
- **Payments:** Razorpay — UPI, cards, net banking; webhook for payment confirmation
- **SMS/OTP:** MSG91 (Indian numbers, reliable delivery)
- **Court/Case data:** Pluggable `CourtAPIAdapter` interface — initially Kleopatra API (future-proof for lawyer ERP module)
- **GST verification:** GST search API (verify client GSTIN during onboarding)

### 6.6 Background Jobs (Celery)
- `deadline_reminder_job` — runs daily at 8 AM: sends WhatsApp reminders for items due in 1/3/7 days
- `regulation_scraper_job` — runs nightly: scrapes MCA, GSTN, EPFO, ESIC, FSSAI, state labour dept portals
- `regulation_classifier_job` — runs after scraper: sends new circulars to AI for classification and affected-client mapping
- `health_score_calculator_job` — runs daily: recalculates compliance health scores for all active clients
- `payment_reconciliation_job` — runs hourly: reconciles Razorpay payment status

---

## 7. Project Folder Structure

```
complianceos/
├── server/                         # Python FastAPI backend
│   ├── main.py                     # App entry point, middleware, CORS
│   ├── routers/
│   │   ├── auth.py                 # OTP login, JWT refresh
│   │   ├── ca.py                   # CA-specific endpoints
│   │   ├── client.py               # SMB client endpoints
│   │   ├── compliance.py           # Compliance items, calendar
│   │   ├── tasks.py                # Task CRUD
│   │   ├── documents.py            # File upload, download, management
│   │   ├── messages.py             # Chat (REST + WebSocket)
│   │   ├── invoices.py             # Invoice generation, payment
│   │   ├── ai.py                   # AI chat (streaming SSE)
│   │   ├── regulations.py          # Regulation alerts, CA notification
│   │   └── webhooks.py             # Razorpay webhook handler
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
│   │   ├── payment.py
│   │   └── regulation.py
│   ├── services/
│   │   ├── ai_service.py           # OpenRouter calls, context builder, streaming
│   │   ├── whatsapp_service.py     # Meta Cloud API wrapper
│   │   ├── payment_service.py      # Razorpay integration
│   │   ├── storage_service.py      # Cloudflare R2 file ops
│   │   ├── notification_service.py # Unified: WhatsApp + push + email
│   │   ├── health_score_service.py # Compliance health score calculator
│   │   ├── gst_service.py          # GST number verification
│   │   └── court_adapter.py        # Pluggable court API (future)
│   ├── workers/
│   │   ├── celery_app.py           # Celery config
│   │   ├── deadline_reminder.py
│   │   ├── regulation_scraper.py
│   │   ├── regulation_classifier.py
│   │   ├── health_score_calculator.py
│   │   └── payment_reconciliation.py
│   ├── core/
│   │   ├── config.py               # Settings, env vars (pydantic-settings)
│   │   ├── auth.py                 # JWT verify, OTP logic
│   │   ├── database.py             # Async SQLAlchemy engine, session
│   │   └── dependencies.py         # FastAPI dependency injection
│   ├── migrations/                 # Alembic migration files
│   ├── regulation_data/            # Seed data: compliance calendar templates by sector
│   └── requirements.txt
│
├── flutter_app/                    # Flutter frontend (all platforms)
│   ├── lib/
│   │   ├── main.dart
│   │   ├── app.dart                # App root, routing, theme
│   │   ├── core/
│   │   │   ├── api/
│   │   │   │   ├── api_client.dart         # Dio setup, interceptors
│   │   │   │   ├── auth_interceptor.dart   # JWT refresh logic
│   │   │   │   └── websocket_client.dart   # WebSocket for chat
│   │   │   ├── local_db/
│   │   │   │   ├── hive_setup.dart
│   │   │   │   └── drift_database.dart     # Offline SQLite schema
│   │   │   ├── router/
│   │   │   │   └── app_router.dart         # GoRouter config (role-aware)
│   │   │   ├── theme/
│   │   │   │   └── app_theme.dart          # Colors, typography, components
│   │   │   └── providers/
│   │   │       └── auth_provider.dart      # Current user, role detection
│   │   ├── features/
│   │   │   ├── auth/               # OTP login, onboarding flows
│   │   │   ├── ca_dashboard/       # CA home, client list, analytics
│   │   │   ├── client_portal/      # SMB home, health score, deadlines
│   │   │   ├── compliance/         # Calendar, compliance items
│   │   │   ├── tasks/              # Task list, task detail
│   │   │   ├── documents/          # Document vault, upload, viewer
│   │   │   ├── messages/           # CA-client chat
│   │   │   ├── ai_chat/            # AI assistant (role-aware)
│   │   │   ├── invoices/           # Billing (CA generates, SMB pays)
│   │   │   ├── regulations/        # Regulation alerts (CA only)
│   │   │   └── settings/           # Profile, plan management, notifications
│   │   └── shared/
│   │       ├── widgets/            # Reusable UI components
│   │       └── utils/              # Date helpers, formatters, validators
│   ├── assets/
│   │   ├── fonts/
│   │   └── images/
│   └── pubspec.yaml
│
├── docs/                           # This spec + API docs + design references
│   ├── PRODUCT_SPEC.md             # This file
│   ├── API_REFERENCE.md            # All endpoint definitions
│   ├── DATABASE_SCHEMA.md          # Full schema with relationships
│   └── REGULATION_DATA_FORMAT.md   # How compliance items are structured
│
├── docker-compose.yml              # Local dev: Postgres, Redis, server, worker
├── .env.example                    # All required env vars documented
└── README.md
```

---

## 8. API Design Principles

1. **Role-aware responses** — every endpoint checks the user's role and returns filtered data accordingly. A CA calling `/tasks` gets all tasks across their clients. A client calling `/tasks` gets only their own tasks.

2. **Consistent envelope** — all responses follow:
```json
{
  "success": true,
  "data": {},
  "meta": { "page": 1, "total": 100 },
  "error": null
}
```

3. **Optimistic UI** — write endpoints return the created/updated object immediately so Flutter can update the UI before confirmation.

4. **Streaming for AI** — `/ai/chat` returns `text/event-stream` (SSE), not JSON. Flutter uses a stream builder to display tokens as they arrive.

5. **Webhook-first payments** — never trust the client for payment status. Only Razorpay webhooks update payment records.

---

## 9. AI Prompt Architecture

### 9.1 CA System Prompt
```
You are a professional compliance assistant for Chartered Accountants in India.
You have expert knowledge of Indian tax law (GST, Income Tax, TDS), corporate law
(Companies Act 2013), labour law (PF, ESIC, Factories Act, Shops & Establishments),
and sector-specific regulations (FSSAI, drug licences, pollution control, etc.).

Current context:
- CA: {ca_name}, {firm_name}, {city}
- Active client count: {client_count}
- Clients with overdue items: {overdue_client_names}

Rules:
- Always give professional, legally precise responses
- When drafting notices or replies, follow Indian legal document conventions
- Frame regulatory opinions as "based on current regulations" — not as definitive legal advice
- Reference specific sections of relevant Acts when applicable
- When client context is provided, personalise your answer to that client
- Keep responses concise unless drafting a document
```

### 9.2 SMB System Prompt
```
You are a friendly compliance guide for small and medium businesses in India.
Your job is to explain compliance requirements in plain, simple language —
as if you were a knowledgeable friend, not a lawyer.

Current context:
- Business: {business_name}, {industry}, {state}
- Linked CA: {ca_name} (if linked)

Rules:
- Explain things simply — no jargon. If you must use a term, explain it.
- Respond in {user_language} (Hindi or English based on user preference)
- Never tell them to do something without explaining why it matters
- Always end responses about serious issues with: "Your CA {ca_name} can help you with this."
- If no CA is linked, end with: "A CA can handle this for you. Find one on ComplianceOS."
- Never give advice that could replace their CA
- Be warm, reassuring, never alarming — compliance is manageable
```

---

## 10. Compliance Calendar Data Model

Each company's compliance requirements are derived from their profile. This is the core intelligence of the product.

### Profile fields that drive the calendar:
- `company_type`: Private Ltd / LLP / Partnership / Proprietorship / OPC
- `turnover_range`: <40L / 40L-1.5Cr / 1.5Cr-5Cr / 5Cr+
- `employee_count`: <10 / 10-20 / 20-100 / 100+
- `gst_registered`: boolean
- `gst_composition`: boolean
- `sectors`: array (manufacturing, food, pharma, IT, retail, etc.)
- `states`: array of states they operate in
- `listed`: boolean (for SEBI/ROC requirements)
- `has_factory`: boolean (Factories Act)
- `import_export`: boolean (DGFT, customs)

### Compliance item structure:
```json
{
  "id": "GST_GSTR1_MONTHLY",
  "name": "GSTR-1 Monthly Filing",
  "type": "GST",
  "authority": "GSTN",
  "frequency": "monthly",
  "due_day": 11,
  "due_day_rule": "11th of following month",
  "applicable_if": {
    "gst_registered": true,
    "gst_composition": false,
    "turnover_range": ["40L-1.5Cr", "1.5Cr-5Cr", "5Cr+"]
  },
  "penalty_per_day": 200,
  "max_penalty": 5000,
  "description": "Monthly outward supply return for regular GST taxpayers",
  "document_checklist": ["Sales invoices", "Debit notes", "Credit notes"],
  "ca_action_required": true,
  "client_action_required": ["Upload sales data / invoices"]
}
```

---

## 11. Regulation Scraper Architecture

### Sources to monitor (daily):
- `https://www.gst.gov.in/` — GST Council, GSTN notifications
- `https://www.mca.gov.in/` — MCA21, Companies Act amendments
- `https://www.epfindia.gov.in/` — EPFO circulars
- `https://www.esic.in/` — ESIC notifications
- `https://www.fssai.gov.in/` — FSSAI circulars
- State-specific labour department portals (18 major states)
- `https://taxmann.com/` + `https://www.taxguru.in/` — aggregated updates (backup)

### Classification pipeline:
1. Scraper fetches new documents (PDFs, HTML pages)
2. Text extracted and stored in `regulations` table
3. Classifier job sends each regulation to AI:
   ```
   Classify this regulation:
   - Type: [GST / Income Tax / Labour / ROC / Sector / Other]
   - Sectors affected: [list]
   - States affected: [list or "All India"]
   - Company types affected: [list]
   - Turnover threshold: [if applicable]
   - Action required by: [date or "no deadline"]
   - One-line plain English summary for business owners
   - Two-line professional summary for CAs
   ```
4. Classification stored; affected client mapping computed nightly

---

## 12. Health Score Algorithm

Score is 0–100. Calculated per client every 24 hours.

```
Base score: 100

Deductions:
- Overdue item (0–7 days):     -5 per item
- Overdue item (8–30 days):    -10 per item
- Overdue item (31+ days):     -15 per item
- Unanswered CA document request (>3 days): -3 per request
- Expired licence (not renewed): -20 per licence
- Pending GST notice (unresponded): -15

Caps:
- Maximum deduction from any single category: 40 points
- Minimum score: 0

Colour coding:
- 80–100: Green (on track)
- 50–79:  Amber (needs attention)
- 0–49:   Red (at risk)
```

---

## 13. MVP Scope (What to Build First)

Build in this exact order. Don't skip ahead.

### Phase 1 — Core loop (8 weeks)
- [ ] Auth: OTP login, JWT, role detection (CA vs SMB)
- [ ] CA onboarding: profile, plan selection, client import via CSV
- [ ] SMB onboarding: invite flow, profile setup
- [ ] Basic compliance calendar: manual items, due dates, status tracking
- [ ] Task system: CA creates tasks, client sees and responds
- [ ] Document upload: CA requests, client uploads, CA views
- [ ] Basic chat: CA-client messaging (no real-time yet, polling)
- [ ] Health score: basic calculation and display
- [ ] Billing: CA plans, Razorpay subscription, plan enforcement

### Phase 2 — Intelligence (6 weeks)
- [ ] AI assistant: CA and SMB versions (basic, no RAG yet)
- [ ] Real-time chat: WebSocket upgrade
- [ ] WhatsApp notifications: deadline reminders, task alerts, document requests
- [ ] Regulation monitor: manual seed data of 50 key compliance items
- [ ] Regulation scraper: automate GST and MCA sources first
- [ ] CA invoice generation: PDF invoices, Razorpay payment link

### Phase 3 — Scale features (ongoing)
- [ ] RAG on Indian law corpus
- [ ] Multi-staff accounts for CA firms
- [ ] Analytics dashboard for CAs
- [ ] SMB CA directory (find a CA)
- [ ] Sector-specific compliance packs (pharma, food, manufacturing)
- [ ] Hindi language support in SMB AI
- [ ] Mobile app (Android first, then iOS)

---

## 14. Non-Negotiable Quality Rules

These rules exist specifically to prevent vibe coding from killing the product.

1. **No feature ships without a test.** Every API endpoint has at least one happy-path and one error-path test. No exceptions.

2. **Role checks are mandatory on every endpoint.** Every route that returns data must verify: is this user allowed to see this data? A client must never see another client's data. A CA must never see another CA's clients.

3. **AI responses are never shown raw.** Always sanitise before displaying. Never inject AI output directly into HTML.

4. **Payment state is always server-side.** The Flutter app never trusts itself to declare a payment successful. Only the Razorpay webhook can mark a payment as paid.

5. **File uploads are always validated.** Check file type (magic bytes, not extension), file size (max 20MB), and scan for malformed files before storing.

6. **Deadlines and dates are always stored in UTC.** Display in IST. Never store IST in the database.

7. **Every background job is idempotent.** Running a job twice must produce the same result as running it once.

8. **Database migrations are never destructive without a backup step.** No `DROP COLUMN` or `DROP TABLE` in a migration without a preceding data backup migration.

9. **Compliance calendar data is versioned.** When regulations change, old snapshots of a client's compliance items are preserved — you cannot rewrite history.

10. **The AI must never make up regulation details.** If the RAG pipeline returns no result, the AI must say "I don't have current information on this — please check with a CA or the official portal." A hallucinated penalty amount or deadline is worse than no answer.

---

## 15. Environment Variables (`.env.example`)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/complianceos

# Redis
REDIS_URL=redis://localhost:6379

# Auth
JWT_SECRET_KEY=your-secret-key-minimum-32-chars
OTP_EXPIRY_SECONDS=300

# OpenRouter (AI)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_DEFAULT_MODEL=anthropic/claude-sonnet-4-5
OPENROUTER_FAST_MODEL=google/gemini-flash-1.5

# WhatsApp (Meta Cloud API)
WHATSAPP_TOKEN=your-meta-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your-webhook-verify-token

# Razorpay
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=your-secret
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret

# Cloudflare R2 (file storage)
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=complianceos-documents
R2_PUBLIC_URL=https://your-bucket.r2.cloudflarestorage.com

# SMS / OTP
MSG91_AUTH_KEY=your-msg91-key
MSG91_TEMPLATE_ID=your-otp-template

# GST Verification
GST_VERIFY_API_KEY=your-key

# Sentry (error tracking)
SENTRY_DSN=https://...

# Environment
ENVIRONMENT=development  # development | staging | production
```

---

*This document is the single source of truth for ComplianceOS. Any feature, design decision, or architecture choice not covered here should be documented here before implementation begins.*