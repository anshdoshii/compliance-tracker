# ComplianceOS — API Reference

Base URL: `https://api.complianceos.in/v1`
All requests need: `Authorization: Bearer <jwt_token>`
All responses: `{ success, data, meta, error }`

---

## Auth endpoints (no token needed)

### POST /auth/otp/send
Send OTP to mobile number.
```json
Request:  { "mobile": "9876543210", "role": "ca" | "smb" }
Response: { "otp_ref": "abc123", "expires_in": 300 }
```

### POST /auth/otp/verify
Verify OTP and get tokens.
```json
Request:  { "mobile": "9876543210", "otp": "123456", "otp_ref": "abc123" }
Response: { "access_token": "...", "refresh_token": "...", "user": {...}, "is_new_user": true }
```

### POST /auth/token/refresh
```json
Request:  { "refresh_token": "..." }
Response: { "access_token": "..." }
```

---

## CA endpoints (role: ca only)

### GET /ca/profile
Get own CA profile + plan details + linked client count.

### PUT /ca/profile
Update CA profile (firm name, city, GSTIN etc.).

### GET /ca/clients
Get all linked clients with health scores.
```
Query: ?status=active|pending|removed&sort=health_score|name|last_activity&page=1&limit=20
```

### POST /ca/clients/invite
Invite a client by mobile number.
```json
Request:  { "mobile": "9876543210", "company_name": "Krishna Industries" }
Response: { "invite_id": "...", "status": "pending" }
```

### POST /ca/clients/import
Bulk import clients via CSV data.
```json
Request:  { "clients": [{ "mobile", "company_name", "gstin", "email" }] }
Response: { "invited": 45, "already_linked": 3, "failed": 2 }
```

### DELETE /ca/clients/:client_id
Remove a client from CA's list (sets link status to 'removed').

### GET /ca/tasks
Get all tasks across all clients.
```
Query: ?client_id=uuid&status=pending&assigned_to=ca|client&due_before=2024-12-31
```

### POST /ca/tasks
Create a task for a client.
```json
Request: { "client_id", "title", "description", "assigned_to", "due_date", "compliance_item_id?" }
```

### PUT /ca/tasks/:task_id
Update task status, due date, description.

### GET /ca/document-requests
Get all document requests CA has sent.

### POST /ca/document-requests
Request a document from a client.
```json
Request: { "client_id", "description", "due_date", "task_id?" }
```

### GET /ca/messages/:client_id
Get chat thread with a specific client.
```
Query: ?page=1&limit=50
```

### POST /ca/messages/:client_id
Send a message to a client.
```json
Request: { "content": "...", "attached_document_id"?, "linked_task_id"? }
```

### GET /ca/compliance/:client_id
Get compliance calendar for a specific client.
```
Query: ?financial_year=2024-25&type=GST|Labour|ROC&status=pending|overdue|filed
```

### POST /ca/compliance/:client_id/items
Manually add a compliance item for a client.

### PUT /ca/compliance/:client_id/items/:item_id
Update compliance item status.

### GET /ca/invoices
Get all invoices CA has generated.

### POST /ca/invoices
Generate a new invoice for a client.
```json
Request: {
  "client_id": "uuid",
  "line_items": [{ "description": "GST Filing Oct 2024", "amount": 250000 }],
  "due_date": "2024-12-15",
  "send_whatsapp": true
}
```

### POST /ca/invoices/:invoice_id/send
Mark invoice as sent and generate Razorpay payment link.

### GET /ca/regulations
Get regulation alerts relevant to CA's client base.
```
Query: ?unread=true&type=GST|Labour|ROC&page=1
```

### GET /ca/analytics
Get CA practice analytics (Pro/Firm plans only).
```
Query: ?from=2024-01-01&to=2024-12-31
```

---

## Client (SMB) endpoints (role: smb only)

### GET /client/profile
Get SMB profile + linked CA details + plan info.

### PUT /client/profile
Update company profile (sectors, states, employee count etc.)
Note: Updating profile triggers health score recalculation.

### POST /client/invite/accept/:invite_id
Accept a CA's invitation to link.

### GET /client/health-score
Get current health score + breakdown + history.
```
Response: {
  "score": 72,
  "color": "amber",
  "breakdown": { "gst": 80, "labour": 60, "roc": 100, "licences": 70 },
  "history": [{ "score": 65, "date": "2024-10-01" }, ...]
}
```

### GET /client/compliance
Get own compliance calendar.
```
Query: ?status=pending|overdue|filed&type=GST|Labour&financial_year=2024-25
```

### GET /client/tasks
Get tasks assigned to this client.
```
Query: ?status=pending|done&page=1
```

### PUT /client/tasks/:task_id
Mark task done or add note.
```json
Request: { "status": "done", "note": "Uploaded all invoices" }
```

### GET /client/documents
Get own document vault.
```
Query: ?financial_year=2024-25&type=invoice|statement|notice&page=1
```

### POST /client/documents/upload
Upload a document (multipart/form-data).
```
Fields: file (binary), document_type, financial_year, task_id?, document_request_id?
Max size: 20MB. Allowed types: pdf, jpg, png, xlsx, docx
```

### GET /client/document-requests
Get pending document requests from CA.

### GET /client/messages
Get chat thread with linked CA.
```
Query: ?page=1&limit=50
```

### POST /client/messages
Send message to linked CA.
```json
Request: { "content": "...", "attached_document_id"? }
```

### GET /client/invoices
Get invoices from CA.

### POST /client/invoices/:invoice_id/pay
Initiate payment for an invoice (returns Razorpay order details).

---

## AI endpoints (both roles)

### POST /ai/chat
Streaming AI chat (SSE).
```json
Request: { "message": "Which clients have GST due this week?", "context_client_id"? }
Response: text/event-stream — tokens streamed as "data: {token}\n\n"
          Final event: "data: [DONE]\n\n"
```

Note: System prompt is role-aware. CA gets professional CA assistant. SMB gets plain-language explainer.

---

## Webhook endpoints (server-to-server, no user token)

### POST /webhooks/razorpay
Razorpay payment events. Verified via HMAC signature.

### POST /webhooks/whatsapp
Meta WhatsApp Cloud API message delivery status.

---

## Error codes

| Code | Meaning |
|---|---|
| 400 | Bad request — check request body |
| 401 | Token missing or expired |
| 403 | Role not allowed for this endpoint |
| 404 | Resource not found |
| 409 | Conflict (e.g. duplicate invite) |
| 413 | File too large (>20MB) |
| 422 | Validation error — check field errors |
| 429 | Rate limited |
| 500 | Server error |

All errors:
```json
{ "success": false, "data": null, "error": { "code": "ROLE_FORBIDDEN", "message": "CAs cannot access client-only endpoints" } }
```
