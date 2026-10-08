# EduVault API — Frontend Handoff

Base URL: `{API_ORIGIN}/api/` · Format: JSON (`Content-Type: application/json`) except resource upload (`multipart/form-data`).
This document is the API contract. There is no Swagger/OpenAPI page or schema file (`/api/docs/`, `/api/schema/`, `/api/redoc/` all return `404`).

All examples below are shapes, not real data. IDs are UUIDs, timestamps are ISO-8601 UTC.

---

## 0. URL map

The API has no landing page: `GET /` and `GET /api/` are intentionally unmatched (`404`). Endpoint documentation is this file. Django's development `404` page at `/` lists every URL pattern the project serves.

| Group | Base URL | What it is for |
|---|---|---|
| accounts | `/api/accounts/` | logout, refresh, me, password change, forgot/reset password (shared by both portals); register/login kept as deprecated aliases of `/api/student/register|login/` |
| admin sign-in | `/api/admin/login/` | email + password, then an e-mailed 6-digit code (30 s): `login/`, `login/2fa/verify/`  |
| student portal | `/api/student/` | `dashboard/`, `profile/`, `course/`, `viewing/`, `access/`, `payment/create-checkout/`, `payments/`, `learning-history/`, `notifications/` |
| payment webhook | `/api/payment/stripe/webhook/` | called by Stripe only (signature-verified, no JWT) |
| admin portal | `/api/admin/` | `course/` (+ `course/resources/`), `students/` (+ `students/approval-requests/`, `students/access/`, `students/payments/`, `students/{id}/decision/`), `reports/` (+ `reports/dashboard/`), `audit-logs/`, `settings/`, `notifications/` |

**Registration decision** (new): `POST /api/admin/students/{id}/decision/` with `{decision: immediate|payment_required|pending, course, note?}`.
`immediate` grants access; `payment_required` marks the student as needing to pay (the course must be a priced payment-required course; the student can then call `student/payment/create-checkout/`, including after a revocation); `pending` keeps the request pending. Returns the CourseAccess record (`state`, `payment_required`). A student with live access gets `409 ALREADY_HAS_ACCESS`.

**URLs changed in Phase 2** (old URLs return `404`; no aliases):

| Old | New |
|---|---|
| `/accounts/admin/login/`, `/accounts/admin/2fa/*` | `/admin/login/`, `/admin/login/2fa/*` |
| `/admin/courses/...` | `/admin/course/...` |
| `/admin/resources/...` | `/admin/course/resources/...` |
| `/admin/users/...` | `/admin/students/...` (`reactivate/` is now `reinstate/`) |
| `/admin/registrations/...`, `/admin/access/...`, `/admin/payments/...` | `/admin/students/approval-requests/...`, `/admin/students/access/...`, `/admin/students/payments/...` |
| `/admin/dashboard/` | `/admin/reports/dashboard/` |
| `/course/...`, `/viewing/...` | `/student/course/...`, `/student/viewing/...` |
| `/payment/create-checkout/` | `/student/payment/create-checkout/` |
| `/notifications/...` | `/student/notifications/...` (students) and `/admin/notifications/...` (admins); each portal accepts only its own role |
| `/accounts/me/` | still valid; `/student/profile/` is a student-only alias view of the same data |

**Stripe:** the webhook endpoint registered in the Stripe Dashboard (or `stripe listen --forward-to`) must now be `{API_ORIGIN}/api/payment/stripe/webhook/`.

Unknown URLs return the standard JSON error (`404 NOT_FOUND`), never an HTML page.

---

## 1. Conventions

### Response envelope

Success:

```json
{ "success": true, "data": { }, "meta": { } }
```

Error:

```json
{
  "success": false,
  "error": { "code": "MACHINE_CODE", "message": "Human readable message", "details": { } }
}
```

* Branch on `error.code`, never on `message`.
* Validation errors: HTTP 400, `code = VALIDATION_ERROR`, `details.fields = { "<field>": ["message", ...] }`.
* 5xx responses are always `INTERNAL_ERROR` with no internal detail.

### Authentication header

```
Authorization: Bearer <access_token>
```

* Access tokens are short-lived (default 15 min). Refresh tokens default to 7 days and **rotate on every use**: always store the *new* refresh token returned by `/accounts/refresh/`; the old one is dead.
* The server also enforces an **inactivity timeout** (default 30 min, admin-configurable). After it, any call returns `401 SESSION_EXPIRED`; the user must log in again.
* `401` codes you must handle: `NOT_AUTHENTICATED`, `TOKEN_NOT_VALID` (expired/invalid access token → try refresh once), `SESSION_EXPIRED`, `USER_INACTIVE` (account suspended), `INVALID_REFRESH_TOKEN`.

### Pagination

List endpoints accept `?page=1&page_size=20` (max 100). The envelope's `data` is the array of items and `meta` is:

```json
{ "count": 57, "page": 1, "page_size": 20, "total_pages": 3 }
```

Notifications additionally return `meta.unread_count`.

### Filtering

Query-string filters are **case-insensitive** for enum values: `?status=ACTIVE` and `?status=active` are equivalent. Enum values in responses are lowercase.

### Throttling

`429` with `error.code = RATE_LIMITED` (`details.retry_after` seconds) or `ACCOUNT_LOCKED` after repeated failed logins / 2FA attempts.

---

## 2. Roles and account states

| Role | How created | Notes |
|---|---|---|
| `student` | `POST /student/register/` | Needs admin approval (setting `registration_requires_approval`, default on). |
| `admin` | `manage.py createsuperuser` | Must enter the e-mailed 6-digit code (valid 30 s) on every login. |

Student `status`:

| status | Can log in | Can use courses/viewer/payments | UI should show |
|---|---|---|---|
| `pending` | **no** (`403 REGISTRATION_PENDING`, "awaiting admin approval") | no | "Awaiting approval" page after registering |
| `active` | yes | yes | normal app |
| `rejected` | **no** (`403 REGISTRATION_REJECTED`, `error.details.reason` when the admin gave one) | no | rejection notice |
| `suspended` | **no** (`403 ACCOUNT_SUSPENDED`) | no | account suspended message |

Lifecycle (admin API): `pending -> active` (approve), `pending -> rejected` (reject), `active -> suspended` (suspend; `suspended -> active` via reinstate). Only an approved, active student ever receives tokens. The status errors are returned only after the password was correct, so they reveal nothing to someone guessing e-mail addresses.

Gate your routes on `user.status` and `user.role` from `/accounts/me/` for UX only — the server re-checks everything.

---

## 3. Authentication (students)

### Register — `POST /student/register/` (public, three calls, see "Registration" below)

Creates one student (`role=student`, `status=pending`) and a registration request for the admin. **No tokens are returned**; the student cannot sign in until an admin approves. `201`:

```json
{ "success": true, "data": { "message": "Student account created successfully.",
    "student": { "id": "…", "email": "student@example.com", "full_name": "Asha Rao", "status": "pending" } }, "meta": {} }
```

Errors: `409 EMAIL_ALREADY_REGISTERED`, `403 EMAIL_NOT_VERIFIED`, `400 VALIDATION_ERROR` (password policy: minimum length is admin-configurable, default 10, plus common/numeric/similarity rules; `details.fields.password` lists the messages).

### Login — `POST /student/login/` (public, students only)

```json
{ "email": "student@example.com", "password": "…" }
```

`200` → `{ "user", "tokens": { "access", "refresh" } }`. **Email + password only: there is no OTP, challenge or second step for students** (the e-mailed code is the admin API only).
Errors: `401 INVALID_CREDENTIALS` (also for unknown e-mails and for admin accounts - admins use `/admin/login/`), `403 REGISTRATION_PENDING`, `403 REGISTRATION_REJECTED`, `403 ACCOUNT_SUSPENDED`, `429 ACCOUNT_LOCKED`.

> `POST /accounts/register/*` and `POST /accounts/login/` still work as **deprecated aliases** (same views, same behaviour) until existing clients move to `/student/register/*` and `/student/login/`. Refresh, logout, me, password change and password reset stay under `/accounts/`.

### Refresh — `POST /accounts/refresh/` (public)

```json
{ "refresh": "<refresh token>" }
```

`200` → `{ "tokens": { "access": "…", "refresh": "…" } }` (**replace both**). Errors: `401 INVALID_REFRESH_TOKEN`, `401 SESSION_EXPIRED`.

### Logout — `POST /accounts/logout/` (auth)

```json
{ "refresh": "<refresh token>" }
```

Blacklists the refresh token and ends the server session. Always clear local storage afterwards.

### Current user / profile

* `GET /accounts/me/` → user object.
* `PATCH /accounts/me/` body `{ "full_name": "New Name" }` → updated user. Role, status and email cannot be changed here.
* `POST /accounts/password-change/` body `{ "current_password": "…", "new_password": "…" }` → `{ "tokens": {…} }`. **All other sessions are signed out; store the returned tokens.**

### Forgot password (OTP) — three steps, all public

1. `POST /accounts/forgot-password/` `{ "email": "…" }` → always `200` (no account enumeration). A 6-digit code is emailed (default validity 10 min).
2. `POST /accounts/forgot-password/verify/` `{ "email": "…", "otp": "123456" }` → `{ "reset_token": "…" }` (valid ~15 min, single use). Errors: `400 INVALID_OTP` (wrong/expired; the code is burned after too many wrong attempts — ask the user to request a new one).
3. `POST /accounts/reset-password/` `{ "reset_token": "…", "new_password": "…" }` → `200`. Errors: `400 INVALID_RESET_TOKEN`, `400 VALIDATION_ERROR`. All existing sessions are revoked; send the user to login.

---

## 4. Admin login with an e-mailed code (email OTP)

Admin API access is impossible until the second factor succeeds: the password step returns only a short-lived `challenge_token` (5 min), which is **not** an access token, and e-mails a 6-digit code to the admin.

1. `POST /admin/login/` `{ "email", "password" }` →
   ```json
   { "requires_two_factor": true, "two_factor_method": "email_otp",
     "challenge_token": "…", "expires_in": 30, "message": "A verification code has been sent to your registered email." }
   ```
   The code is **never** in the response. It is valid for **30 seconds** (server clock), single-use, and only the newest code works.
2. `POST /admin/login/2fa/verify/` `{ "challenge_token", "otp": "482193" }` → `{ "user", "tokens" }`. This is the only call that issues admin tokens.
3. If the code expired or was refused too often, start again at step 1 (a new code is e-mailed, the old one stays invalid). There is no "resend" on the old challenge.

There is no TOTP / authenticator / backup-code step and no enrolment endpoint (`login/2fa/setup/` and `login/2fa/confirm/` were removed; they now return 404). `two_factor_enabled` stays in the user payload for compatibility and is always `false`. This API flow is separate from the Django admin site at `/admin/` (e-mail + password, Django session), which never uses these endpoints.

Errors: `401 INVALID_CREDENTIALS` (also for unknown / non-admin / not approved accounts), `403 ACCOUNT_SUSPENDED`, `401 INVALID_CHALLENGE` (expired → restart at step 1), `401 INVALID_TWO_FACTOR_CODE` (wrong, expired, used or replaced code - one message for all), `400` (code is not 6 digits), `429 OTP_RATE_LIMITED` (codes requested too often), `429 ACCOUNT_LOCKED` (too many failures).

---

## 5. Courses (student catalogue)

Requires an **approved** student. Only `published` courses are returned.

* `GET /student/course/` — filters: `q` (title), `category`, `access_mode`.
* `GET /student/course/{course_id}/`

```json
{ "id": "…", "title": "Algebra I", "slug": "algebra-i", "description": "…", "category": "Maths",
  "access_mode": "payment_required", "price_amount": "49.00", "currency": "USD",
  "access_duration_days": 180, "published_at": "…",
  "access": { "state": "payment_required", "allowed": false, "expires_at": null, "access_id": null } }
```

`access_mode`: `immediate` | `manual_approval` | `payment_required`.

### Access states (`course.access.state`)

| state | `allowed` | Meaning | UI action |
|---|---|---|---|
| `requestable` | false | Free/approval course, no request yet | "Get access" / "Request access" → `POST /student/access/` |
| `payment_required` | false | Admin approved the student's request to pay | "Pay now" → `POST /student/payment/create-checkout/` (only in this state) |
| `pending` | false | Awaiting admin approval | "Request pending" |
| `granted` | **true** | Active access (check `expires_at`) | "Open" → viewer |
| `expired` | false | Access time ran out | re-request / re-buy |
| `rejected` | false | Admin declined (can re-request) | "Request again" |
| `revoked` | false | Admin/refund removed access (cannot self-request) | contact support |
| `unavailable` | false | Course not published | hide |

Only `granted` unlocks the viewer.

### Access requests

* `POST /student/access/` `{ "course": "<uuid>" }` → `201` access record. `immediate` courses are granted at once (state `granted`); `manual_approval` become `pending`. For a `payment_required` course the request is stored as `pending` (an admin must approve it for payment before the student can check out). Errors: `403 ACCESS_REVOKED`, `404` (unpublished/unknown course).
* `GET /student/access/` — the student's own records. `GET /student/access/{access_id}/` — one record (other students' records return `404`).

```json
{ "id": "…", "student": "…", "student_email": "…", "course": "…", "course_title": "…",
  "status": "pending", "state": "pending", "source": "", "note": "", "requested_at": "…",
  "decided_at": null, "granted_at": null, "granted_by": null, "expires_at": null,
  "revoked_at": null, "revoked_by": null }
```

---

## 6. Payments (Stripe Checkout)

Flow — **the browser never confirms a payment; only Stripe's signed webhook activates access**:

1. `POST /student/payment/create-checkout/` `{ "course": "<uuid>" }` → `201` (only after an admin approved the payment request; otherwise `403 PAYMENT_NOT_APPROVED` and nothing is created)
   ```json
   { "id": "<payment id>", "course": "…", "course_title": "…", "amount": "49.00", "currency": "USD",
     "status": "pending", "paid_at": null, "created_at": "…", "checkout_url": "https://checkout.stripe.com/…" }
   ```
   Price and currency come from the server; do not send them.
2. `window.location = checkout_url`.
3. Stripe redirects to `{FRONTEND_URL}/payments/success?payment_id=…` or `/payments/cancelled?payment_id=…`.
4. On the success page, **poll** `GET /student/payments/{payment_id}/` (every 2–3 s, up to ~30 s) until `status` is `paid`, then refresh the course (`access.state` = `granted`). The redirect itself proves nothing; if it stays `pending`, tell the user it is still processing.

Other endpoints: `GET /student/payments/` (`?status=`), `GET /student/payments/{id}/`.
Payment `status`: `pending` | `paid` | `failed` | `cancelled` | `refunded` (a refund also revokes the access).

Errors: `409 ALREADY_HAS_ACCESS`, `403 ACCESS_REVOKED`, `400 PAYMENT_NOT_REQUIRED`, `404` (unpublished), `503 PAYMENTS_DISABLED` / `PAYMENTS_NOT_CONFIGURED`, `502 PAYMENT_PROVIDER_ERROR`.

`POST /payment/stripe/webhook/` is for Stripe only — the frontend never calls it.

---

## 7. Protected viewer

The original PDF is never sent. Pages are rendered on the server, watermarked with the **authenticated student's** name, email, short id, course, UTC time and a per-view id, and returned as an image. Watermark identity cannot be influenced by the client.

All viewer endpoints need an approved student with `granted` access; otherwise `403` with a code derived from the state: `ACCESS_REQUESTABLE`, `ACCESS_PENDING`, `ACCESS_EXPIRED`, `ACCESS_REVOKED`, `ACCESS_REJECTED`, `ACCESS_PAYMENT_REQUIRED`. Unpublished courses/resources return `404`.

* `GET /student/viewing/courses/{course_id}/resources/` → paginated list of published resources:
  `{ "id", "course", "title", "description", "page_count", "published_at" }`
* `GET /student/viewing/resources/{resource_id}/` → same shape for one resource.
* `GET /student/viewing/resources/{resource_id}/pages/{page_number}/` (1-based) →
  ```json
  { "view_id": "<uuid>", "resource": "…", "page": 1, "page_count": 12, "width": 1200, "height": 1553,
    "content_type": "image/jpeg", "image": "<base64>", "watermark_id": "9f8e7d6c5b4a" }
  ```
  Render with `<img src={`data:${content_type};base64,${image}`} />`. The response is `Cache-Control: no-store`; don't persist it. `404 INVALID_PAGE` for pages out of range.
* `POST /student/viewing/resources/{resource_id}/activity/` `{ "view_id": "<from the page response>", "duration_seconds": 30 }` → `{ "view_id", "duration_seconds" }` (running total). Send when the student leaves a page or periodically (0–3600 per call). Only the student's own page views can be updated.

Page views are recorded automatically by the server when a page is requested. Rate limit: 180 page requests/min/user by default — prefetch at most the next page.

Learning history: `GET /student/learning-history/` (`?course=`, `?resource=`) →
`{ "id", "course", "course_title", "resource", "resource_title", "page_number", "duration_seconds", "viewed_at" }`.

---

## 8. Notifications

`GET /student/notifications/` (`?unread=true`, `?type=`) → items + `meta.unread_count`.

```json
{ "id": "…", "type": "access_granted", "title": "Course access granted", "message": "…", "data": { "course": "…" },
  "is_read": false, "read_at": null, "created_at": "…" }
```

Types: `registration_approved`, `registration_rejected`, `access_granted`, `access_revoked`, `payment_successful`, `course_published`, `security`.

* `POST /student/notifications/{id}/read/` · `POST /student/notifications/read-all/` → `{ "updated": n }` · `DELETE /student/notifications/{id}/`.
* Users only ever see their own notifications (other IDs → `404`). Admins have notifications too (security notices).

---

## 9. Student dashboard

`GET /student/dashboard/` — the signed-in student's own dashboard (approved, active students only; the student is always the JWT user).

**Name-based route:** `GET /student/<name>/dashboard/` (e.g. `/api/student/Ravi/dashboard/`) returns the same dashboard. The login response's `user.dashboard_path` is the exact URL to use (first name, spaces as `-`, URL-encoded). The name is a routing label only: the server authenticates with the JWT and compares the name with the signed-in student's own name (case-insensitive); any other name, with a valid token, gets `403 STUDENT_MISMATCH` and no data, and no token gets `401`. Names are not unique (two students may both be "Ravi"): each still sees only their own data.

```json
{ "profile": { … user … },
  "registration": { "status": "active", "reviewed_at": "…", "rejection_reason": "" },
  "active_courses": [ { "access_id", "course", "title", "slug", "expires_at",
                        "total_pages", "pages_viewed", "progress_percent" } ],
  "pending_requests": [ { "access_id", "course", "title", "requested_at" } ],
  "recent_activity": [ { "course", "course_title", "resource", "resource_title", "page_number", "viewed_at" } ],
  "notifications": { "unread_count": 2, "latest": [ … up to 5 … ] },
  "learning_stats": { "pages_viewed", "distinct_pages", "reading_minutes", "resources_opened",
                      "courses_studied", "active_courses", "last_viewed_at" } }
```

For `pending`/`rejected` students every list is empty — render from `registration`.

---

## 10. Admin APIs

All under `/api/admin/…`, admin token required (`403 PERMISSION_DENIED` for students, `401` unauthenticated).

### Users & registrations

| Method | URL | Notes |
|---|---|---|
| GET | `/admin/students/` | `?role=`, `?status=`, `?q=` (email/name) |
| GET/PATCH/DELETE | `/admin/students/{id}/` | PATCH body `{ "full_name" }` only; DELETE refuses admins and yourself (`400`), and users with kept records (`409 USER_IN_USE` → suspend instead) |
| POST | `/admin/students/{id}/suspend/` | `active → suspended`; revokes all of the user's sessions. `409 INVALID_STATE` otherwise |
| POST | `/admin/students/{id}/reinstate/` | `suspended → active` |
| GET | `/admin/students/approval-requests/` | students; `?status=PENDING` for the review queue |
| GET | `/admin/students/approval-requests/{id}/` | |
| POST | `/admin/students/approval-requests/{id}/approve/` | `pending → active`, records reviewer + time, notifies the student |
| POST | `/admin/students/approval-requests/{id}/reject/` | body `{ "reason": "…" }` (optional) → `rejected` |

User object (admin) adds `reviewed_by`, `reviewed_by_email`, `updated_at`. Self-actions return `400 CANNOT_MODIFY_SELF`.

### Courses

`GET/POST /admin/course/` (`?status=`, `?access_mode=`, `?category=`, `?q=`), `GET/PATCH/DELETE /admin/course/{id}/`, `POST …/publish/`, `POST …/archive/`.

Create/PATCH body: `title`, `description`, `category`, `access_mode`, `price_amount`, `currency` (3-letter), `access_duration_days`. New courses start as `draft`; **status changes only through publish/archive**. `payment_required` needs a positive `price_amount`; other modes must not have one. The `slug` is generated. DELETE returns `409 COURSE_IN_USE` if the course has access records, resources, payments or views — archive it instead.

### Resources (PDFs)

* `POST /admin/course/resources/` — `multipart/form-data`: `course` (uuid), `title`, `description?`, `file` (PDF). `201` with metadata (`status: "draft"`, `page_count`, `file_size`, `sha256`, `original_filename`). The file is checked by content (signature, structure, renderability, page/size limits), not by name. Errors: `400 INVALID_PDF`, `413 FILE_TOO_LARGE`, `409 COURSE_ARCHIVED`.
* `GET /admin/course/resources/` (`?course=`, `?status=`, `?q=`), `GET/PATCH/DELETE /admin/course/resources/{id}/` (PATCH: `title`, `description`; DELETE `409 RESOURCE_IN_USE` once viewed → archive).
* Lifecycle: `draft → POST …/validate/ → validated → POST …/publish/ → published`; `POST …/archive/` from any state. Publishing a draft returns `409 RESOURCE_NOT_VALIDATED`.
* Students only see `published` resources of `published` courses they hold access to. Storage keys are never exposed.

### Access control

* `GET /admin/students/access/` (`?student=`, `?course=`, `?status=`), `GET /admin/students/access/{id}/`.
* `POST /admin/students/access/grant/` `{ "course", "student", "note?" }` → grants directly (`source: "admin_approval"`).
* `PATCH /admin/students/access/{id}/` `{ "action": "approve" | "reject" | "revoke", "note?" }`. approve/reject only from `pending`, revoke only from `active` (`409 INVALID_STATE` otherwise).

### Payments · Audit

* `GET /admin/students/payments/` (`?status=`, `?student=`, `?course=`), `GET /admin/students/payments/{id}/` (includes Stripe ids).
* `GET /admin/audit-logs/` (`?action=`, `?actor=`, `?target_type=`, `?target_id=`, `?from=`, `?to=` ISO datetimes), `GET /admin/audit-logs/{id}/`. Read-only; there is no write/delete API.

### Dashboard & reports

* `GET /admin/reports/dashboard/` → `users`, `courses`, `resources`, `access`, `payments`, `activity_last_30_days`, `recent_activity` (last 10 audit events). All figures come from the database.
* `GET /admin/reports/{overview|users|courses|access|payments|activity}/` with `?days=1..365` (default 30); `courses` is paginated and takes `?status=`. Money values are fixed-2-decimal strings grouped by currency; never sum across currencies.

### Platform settings

* `GET /admin/settings/` → `{ "settings": {…effective values…}, "overridden": ["field", …], "integrations": { "stripe_configured", "stripe_webhook_configured", "email_backend", "storage_backend" } }`. Secrets are never returned.
* `PATCH /admin/settings/` with any subset of: `otp_expiry_seconds` (60–3600), `session_inactivity_seconds` (300–86400), `login_max_attempts` (3–20), `login_lockout_seconds` (60–86400), `password_min_length` (8–64), `registration_requires_approval`, `email_notifications_enabled`, `viewer_render_width` (600–2400), `viewer_jpeg_quality` (40–95), `payments_enabled`. Send `null` to reset a field to the deployment default. Takes effect immediately.
* `POST /admin/settings/test-email/` `{ "to?": "x@y.com" }` (defaults to the admin's own address) → `502 EMAIL_DELIVERY_FAILED` on SMTP problems.

---

## 11. Endpoint list

Public: `POST /student/register/` (+ `send-otp/`, `verify-otp/`), `/student/login/` (deprecated aliases: `/accounts/register/*`, `/accounts/login/`), `/accounts/refresh/`, `/accounts/forgot-password/`, `/accounts/forgot-password/verify/`, `/accounts/reset-password/`, `/admin/login/`, `/admin/login/2fa/verify/` (challenge-token based), `/payment/stripe/webhook/` (Stripe only).

Authenticated (any role): `POST /accounts/logout/`, `GET|PATCH /accounts/me/`, `POST /accounts/password-change/`. Students also use `/student/notifications/` (same routes under `/admin/notifications/` for admins), `POST /student/notifications/read-all/`, `POST /student/notifications/{id}/read/`, `DELETE /student/notifications/{id}/`.

Student (approved): `GET /student/course/`, `GET /student/course/{id}/`, `GET|POST /student/access/`, `GET /student/access/{id}/`, `POST /student/payment/create-checkout/`, `GET /student/payments/{id}/`, `GET /student/payments/`, `GET /student/learning-history/`, `GET /student/viewing/courses/{id}/resources/`, `GET /student/viewing/resources/{id}/`, `GET /student/viewing/resources/{id}/pages/{n}/`, `POST /student/viewing/resources/{id}/activity/`.
Student (approved, active): `GET /student/dashboard/` and `GET /student/<name>/dashboard/`.

Admin: everything under `/admin/…` listed in section 10.

See the sections above for the request and response shapes.

---

## 12. Error code reference

| HTTP | `error.code` | Meaning / suggested handling |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Show `details.fields` next to inputs |
| 400 | `PARSE_ERROR` | Malformed JSON body |
| 400 | `INVALID_PDF` | Upload rejected (not a valid/renderable PDF, too many pages, wrong type) |
| 400 | `INVALID_OTP`, `INVALID_RESET_TOKEN` | Restart the forgot-password flow |
| 400 | `INVALID_STUDENT`, `CANNOT_MODIFY_SELF`, `CANNOT_DELETE_ADMIN`, `PAYMENT_NOT_REQUIRED` | Business-rule rejection |
| 401 | `NOT_AUTHENTICATED`, `TOKEN_NOT_VALID`, `AUTHENTICATION_FAILED` | Refresh once, else go to login |
| 401 | `SESSION_EXPIRED`, `USER_INACTIVE` | Go to login |
| 401 | `INVALID_CREDENTIALS`, `INVALID_REFRESH_TOKEN`, `INVALID_CHALLENGE`, `INVALID_TWO_FACTOR_CODE` | Login/2FA failures |
| 402 | `PAYMENT_REQUIRED` | Start checkout |
| 403 | `PERMISSION_DENIED` | Role not allowed |
| 403 | `REGISTRATION_PENDING`, `REGISTRATION_REJECTED`, `ACCOUNT_SUSPENDED` | Account-state screens |
| 403 | `ACCESS_REQUESTABLE`, `ACCESS_PENDING`, `ACCESS_EXPIRED`, `ACCESS_REVOKED`, `ACCESS_REJECTED`, `ACCESS_PAYMENT_REQUIRED` | No active course access |
| 404 | `NOT_FOUND`, `COURSE_UNAVAILABLE`, `INVALID_PAGE`, `VIEW_NOT_FOUND` | Missing (or not yours) |
| 405 / 415 | `METHOD_NOT_ALLOWED`, `UNSUPPORTED_MEDIA_TYPE` | Client bug |
| 409 | `EMAIL_ALREADY_REGISTERED`, `ALREADY_HAS_ACCESS`, `INVALID_STATE`, `COURSE_IN_USE`, `RESOURCE_IN_USE`, `USER_IN_USE`, `RESOURCE_NOT_VALIDATED`, `COURSE_ARCHIVED` | Conflict with current state; refetch |
| 413 | `FILE_TOO_LARGE` | `details.max_bytes` |
| 429 | `RATE_LIMITED`, `ACCOUNT_LOCKED` | Back off (`details.retry_after`) |
| 500 | `INTERNAL_ERROR`, `STORAGE_ERROR`, `RENDER_FAILED` | Retry later |
| 502 | `PAYMENT_PROVIDER_ERROR`, `EMAIL_DELIVERY_FAILED` | Provider problem |
| 503 | `PAYMENTS_DISABLED`, `PAYMENTS_NOT_CONFIGURED`, `WEBHOOK_NOT_CONFIGURED` | Feature unavailable |
| 503 | `SERVICE_UNAVAILABLE` | Database or Redis is down; retry shortly (no internal details are returned) |

---

## 13. CORS & deployment notes for the frontend team

* The API only answers browsers whose origin is listed in the server's `CORS_ALLOWED_ORIGINS`. Give the backend team your exact origin(s).
* Tokens are returned in JSON; keep the access token in memory and the refresh token in the most protected store your app allows. No cookies are used, so CSRF does not apply.
* `FRONTEND_URL` (server setting) is used to build Stripe return URLs: `/payments/success` and `/payments/cancelled` must exist.


## Sessions, refresh tokens and lockout (Phase 3)

* Every sign-in is its own **device session**. Logging out (or inactivity expiry) affects only that device. Password change/reset and suspension end **all** devices.
* Refresh tokens rotate on every `POST /accounts/refresh/`. Sending an already-rotated refresh token again is treated as theft: that device's session ends (the new token stops working too) and the client must sign in again. Do not fire two refresh calls with the same token concurrently.
* E-mailed admin codes are single-use, valid 30 s, limited attempts (`ADMIN_LOGIN_OTP_MAX_ATTEMPTS`); 
* Failed logins are counted per **(email, IP)** (limit `LOGIN_MAX_ATTEMPTS`, default 5, lock `LOGIN_LOCKOUT_SECONDS`), with a wider per-email backstop at 4x the limit. A lock returns `429 ACCOUNT_LOCKED` with `details.retry_after`.

## Phase 4 additions

* **Admin notifications** (`GET /admin/notifications/`, in-app only, each admin has a private feed): types `new_registration` (a registration is waiting for approval), `access_requested` (manual-approval course; `data.course`, `data.access`, `data.user`), `payment_received` (after the verified Stripe webhook; `data.payment`, `data.course`, `data.user`).
* **Course lifecycle**: `draft -> published` (`POST /admin/course/{id}/publish/`), `published -> draft` (`POST /admin/course/{id}/unpublish/`, students lose access at once, access records are kept), `draft|published -> archived` (`.../archive/`). `PUT /admin/course/{id}/` replaces every editable field (omitted ones return to their defaults; `title` is required; `status` is never changed by PUT or PATCH). `PATCH` remains partial.
* **Granting access** (`POST /admin/students/access/grant/`, approving a pending request, and the decision endpoint) now returns `409 COURSE_UNAVAILABLE` / `400` for a course that is not published. A paid Stripe webhook still activates access even if the course was unpublished afterwards.
* **Registration detail** (`GET /admin/students/approval-requests/{id}/`) now also returns `accesses` (the student's CourseAccess records with `state`, `payment_required`, `expires_at`) and `payments`.
* **Checkout** (`POST /student/payment/create-checkout/`) returns the student's still-open Stripe session instead of creating another payment when the price is unchanged.
* **2FA challenge** is single-use after a successful verify/confirm (a failed code does not consume it).

## Student registration with e-mail OTP, login, forgot password (Phase 5)

Registration is three public calls (all `POST`, JSON, standard envelope):

1. `/student/register/send-otp/` `{ "email" }` -> `200 { "message": "Verification OTP sent successfully." }`. The code is e-mailed only (never in the response). Same answer for an address that already has an account (no e-mail is sent). Limits: one e-mail per address per `OTP_RESEND_COOLDOWN_SECONDS` (default 60, `429 OTP_COOLDOWN`, `details.retry_after`), `THROTTLE_OTP` per IP.
2. `/student/register/verify-otp/` `{ "email", "otp" }` -> `200 { "message", "email_verified": true }`. `400 INVALID_OTP` for a wrong, expired, used or burned code (`OTP_MAX_ATTEMPTS` wrong guesses burn it). Valid for `OTP_EXPIRY_SECONDS` (default 10 min). A verified e-mail may register for `REGISTRATION_VERIFICATION_SECONDS` (default 30 min), once.
3. `/student/register/` `{ first_name, middle_name?, last_name, phone_number, email, password, confirm_password }` -> `201 { "message": "Student account created successfully.", "student": { id, first_name, middle_name, last_name, full_name, email, phone_number, status } }`. `403 EMAIL_NOT_VERIFIED` if step 2 was not completed for that e-mail. **Registration no longer returns tokens: sign in afterwards** (`/accounts/login/`). `phone_number`: 7-15 digits, optional leading `+` (spaces, dashes, dots and brackets are stripped).

Login (`POST /student/login/`), profile (`GET /student/profile/`) and the catalogue with the signed-in student's access state (`GET /student/course/`) keep their URLs: the student is always the JWT user, never a name or id in the URL or query string. `user`/`student` objects now also carry `first_name`, `middle_name`, `last_name`, `phone_number` (`full_name` stays the display name).

Forgot password (unchanged URLs): `POST /accounts/forgot-password/` -> `POST /accounts/forgot-password/verify/` -> `POST /accounts/reset-password/` `{ reset_token, new_password, confirm_password }` (**`confirm_password` is now required**). Same cooldown and attempt limits; e-mails are "EduVault Email Verification OTP" and "EduVault Password Reset OTP".

## Student + admin workflow additions (Phase 6)

Student:
* `GET /student/courses/` - **my courses**: only courses the signed-in student has an access record for (any state, published courses only), each with `access.state` (`granted`, `pending`, `payment_required`, `expired`, `revoked`, ...). `?state=` filters. `GET /student/course/` stays the full published catalogue.
* `GET /student/course/{id}/` - now also returns `resources` (the published PDFs: id, title, page_count) **only when the central access check allows it**, otherwise `[]`. Reading pages is still only through `/student/viewing/...` (server-rendered, watermarked, no download endpoint; downloading is intentionally not offered).
* `GET /student/payment-requests/` - payments an admin asked this student to make: `{id, course:{id,title}, amount ("499.00" decimal string), currency, status:"pending", created_at}`. Pay with `POST /student/payment/create-checkout/`; access activates only from the verified Stripe webhook, after which the request disappears. The student also gets a `payment_requested` notification. `GET /student/dashboard/` has the same list as `payment_requests` and `learning_stats.pending_courses / payment_required_courses / total_courses`.
* `GET|PATCH /student/profile/` - editable: `first_name`, `middle_name`, `last_name`, `phone_number` (display name is recomputed), or just `full_name`. Role, status, flags, e-mail and password are never changed here.
* `GET|PATCH /student/settings/` - `{ "email_notifications": true|false }` (persisted; security notices are always e-mailed).

Admin:
* `POST /admin/students/{id}/decision/` `decision`: `immediate` (access active), `payment_required` (student must pay; priced payment-required course only), `pending` or its alias `manual` (keep in manual review).
* `GET /admin/students/access/?payment_required=true` lists open payment requests; `GET /admin/reports/dashboard/` has `access.payment_requests_pending` (and `pending_approvals` now excludes them).
* `GET|PATCH /admin/profile/` - same fields and rules as the student profile, admin accounts only.
* `POST /admin/course/resources/{id}/replace/` (multipart `file`) - swaps the PDF; the resource returns to `draft` (hidden from students) until validated and published again; the old file is deleted.

## Notifications (Phase 7)

Routes (same views and envelope for both portals; every query is scoped to the signed-in user, someone else's id is `404`): `GET /student|admin/notifications/` (`?unread=true`, `?type=`; `meta.unread_count`), `GET /.../{id}/` (new: retrieve one), `POST /.../{id}/read/`, `POST /.../read-all/`, `DELETE /.../{id}/`. Students use `/student/notifications/`, admins `/admin/notifications/`; the other role gets `403`.

Student types: `registration_approved`, `registration_rejected`, `access_granted`, `access_pending` (manual review decision), `access_rejected`, `access_revoked`, `payment_requested` (message names course, amount and currency; `data` = `{course, access, amount, currency, action:"pay"}`: pay with `POST /student/payment/create-checkout/`), `payment_successful` (`data.event` = Stripe event id), `payment_failed` (failed or expired checkout), `resource_available` (new PDF published in a course the student can open now), `course_published`, `security`.
Admin types: `new_registration`, `access_requested`, `payment_received`, `payment_attention` (Stripe amount/currency mismatch, or a refund).

E-mail: every notification is stored in-app first and never depends on mail delivery (a failing SMTP server is logged only). The student's `email_notifications` setting switches off only the optional copies (`access_granted`, `access_pending`, `resource_available`, `course_published`); security notices, registration decisions, payment requests/results and access rejected/revoked are always e-mailed (unless the admin master switch `email_notifications_enabled` is off).


## Admin URL structure (Phase 8)

Every `include()` now has its own prefix: `admin/students/approval-requests/`, `admin/students/access/`, `admin/students/payments/`, `admin/students/` (list, detail, suspend, reinstate, decision), `admin/course/resources/`, `admin/course/`.

* **Registrations are now "approval requests"**: `GET /admin/students/approval-requests/` (**pending by default**; `?status=active|rejected|suspended|pending|all`), `GET .../{id}/`, `POST .../{id}/approve/`, `POST .../{id}/reject/` `{reason?}`. Same responses and rules as before.
* **Temporary alias**: `/admin/students/registrations/...` still works with its old behaviour (the list shows every student unless `?status=` is given). It will be removed once the frontend uses `approval-requests/`.
* No other URL changed.
