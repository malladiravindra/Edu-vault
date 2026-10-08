# EduVault Project Issues & Security Audit

The single authoritative audit/issue file. Older dated reports were merged into it and removed (section 15). Where any other document disagrees, this file wins.

Verified 2026-10-06 on SQLite + an in-memory cache (tests) and on real `runserver` processes with throw-away SQLite databases (live checks).
Status words: **PASS** verified and correct · **FIXED** was a problem, now corrected and tested · **WARNING** works, but a risk, trade-off or limitation to know about · **BLOCKER** must be resolved before production go-live.
No password, token, OTP or secret is recorded here.

## 1. Architecture audit

```
                       EDUVAULT  (one accounts.User table, role = admin | student)
    ┌───────────────────────┬───────────────────────────────┬───────────────────────────────────┐
    │ Django Admin  /admin/ │ Admin application /api/admin/ │ Student application /api/student/ │
    │ e-mail + password     │ e-mail + password             │ e-mail + password                 │
    │ Django session        │ + e-mailed 6-digit code (30 s)│ (approved, active students only)  │
    │ database administration│ → JWT → Admin dashboard      │ → JWT → Student dashboard         │
    └───────────────────────┴───────────────────────────────┴───────────────────────────────────┘
```

| Finding | Status |
|---|---|
| Three separate interfaces with separate credentials; no shared login code path between the Django session and either JWT flow (tests: `test_three_systems.py`) | **PASS** |
| One `User` table; `AdminUser` / `StudentUser` are proxy models (no tables) used only for the Django admin lists | **PASS** |
| DRF `APIView` + explicit `path()` only (no ViewSet/router; guard tests) | **PASS** |
| Layout: `config/` (settings, urls), `core/` (shared infrastructure), `portal/` (API route composers + student dashboard), domain apps at the backend root (`accounts, access, audit, courses, notifications, payments, platform_settings, resources, viewing`, model-less `reports`). No `apps/` package; moving them would touch every import and migration label | **PASS** (no `apps/` package: deliberate) |
| Cache (Redis in production) holds lockout counters, OTP hashes, device sessions/epochs, throttles; PostgreSQL is the intended production database | **WARNING** (see section 17) |

## 2. Django Admin audit (`/admin/`)

E-mail + password → Django session → admin. No OTP, TOTP, backup code, challenge token or JWT (**PASS**, tests `test_django_admin_login.py`, live).

- Access = `is_active ∧ is_staff ∧ role=admin ∧ status=active`, checked at sign-in **and on every request** (`EduVaultAdminSite.has_permission`): a suspended/rejected/pending admin, or one who loses `is_staff` or the role, is out at once; a student flagged `is_staff` is refused (**PASS**).
- Credential check is the API's `authenticate_credentials` (per-(email, IP) + per-email lockout, audit events, timing equalised, identical error for unknown/wrong/student); Django's `LoginView` creates the session (key cycled → no fixation), same-host `next` only, `LOGIN_REDIRECT_URL=/admin/` (**PASS**). Previous defect "admin refused unless TOTP enrolled" (**FIXED**).
- Host guard `core.middleware.AdminSiteHostGuardMiddleware` (404 outside `DJANGO_ADMIN_ALLOWED_HOSTS`, default localhost) intact; CSRF and secure cookies when `DEBUG` is off (**PASS**).
- **Sections** (sidebar): *Accounts → Admin users, Student users* (proxy models over the one table, wrong-section ids resolve to "does not exist"); there is **no** combined `/admin/accounts/user/` (404). Short paths `/admin/accounts/users/admin/` and `/admin/accounts/users/students/` redirect to them behind `admin_view`. Also registered: Courses, Resources, Course access, Payments, Stripe events, Notifications, Audit events, Platform settings, View activities; JWT blacklist tables are deliberately hidden. User names/phone editable; role, status, flags, secrets read-only/hidden; no add/delete (**PASS**).
- **WARNING AUTH-4:** `/admin/` is single-factor by requirement; protected only by the localhost-only host guard + shared lockout. Do not expose it publicly. **WARNING AUTH-7:** built-in `/admin/password_change/` exists (bypasses the app password policy, does not end API sessions). **WARNING AUTH-8:** no inactivity timeout (8 h absolute session).

## 3. Admin application authentication audit (`/api/admin/login/` → `/api/admin/login/2fa/verify/`)

Password → role admin + `status=active` → code e-mailed → `challenge_token` (5 min, single-use, **not** a bearer token: tested) + message only → `verify` {challenge_token, otp} → JWT. The only place an admin token is issued (**PASS**). Students, unknown accounts, wrong passwords and not-approved admins get the same `401`; a suspended admin gets `403` and no e-mail. Every `/api/admin/*` view uses `IsAdminRole`, which now requires `role=admin` **and** `status=active` read from the database on every request (**FIXED** today: it checked only the role; the JWT layer already rejected suspended users). Role/ids/query parameters supplied by the client are never trusted (tested). The Django admin never calls this flow.

## 4. Student authentication audit (`POST /api/student/login/`, `POST /api/student/register/`)

- Registration is three calls (`register/send-otp/`, `register/verify-otp/`, `register/`): verified e-mail first, then one `role=student`, `status=pending` user, **no tokens**, admin notified (**PASS**). Client-supplied `role/status/is_staff` are ignored.
- Login is e-mail + password only (no OTP/challenge). **Only `active` students get a JWT**: `pending` → `403 REGISTRATION_PENDING`, `rejected` → `403 REGISTRATION_REJECTED` (+ reason), `suspended` → `403 ACCOUNT_SUSPENDED`; unknown e-mail, wrong password and admin accounts → the same `401`. Status errors appear only after a correct password. A pending/rejected login previously succeeded; **FIXED** earlier today. There is one common endpoint (no per-name login route).
- `/api/accounts/register/*` and `/api/accounts/login/` remain as **deprecated aliases** of the same views (**WARNING STU-3**: duplicate endpoints kept so existing clients keep working; remove when every client uses `/api/student/*`).
- Dashboard: `GET /api/student/dashboard/` and `GET /api/student/<name>/dashboard/` (same data; name = the student's first name, spaces as `-`, returned as `user.dashboard_path` at login). The JWT is the identity; the name is only compared with the authenticated student's own name (case-insensitive) and never used for a lookup: another student's name, or any unknown name, gives `403 STUDENT_MISMATCH` and no data; no token `401`; admin `403`; pending/rejected `403` (**FIXED**: the dashboard used to open for those tokens). The route is registered last so a name such as "Access" cannot shadow a fixed route (**PASS**).
- **WARNING STU-8:** names are not unique or immutable (first name is editable): two "Ravi"s share one URL and each sees only their own data; a renamed student gets a new `dashboard_path`. A globally unique URL-safe handle would need a new `User` field and migration; not added because the URL name is only a routing label.

## 5. OTP / 2FA audit (admin application)

Implemented once in `accounts/services.py` (`start_admin_login_otp`, `check_admin_login_otp`) on the existing cache-backed OTP helpers, lockout, throttles, audit and e-mail services. **PASS** for each:
`secrets` 6-digit code, no fixed/dev OTP · stored only as `HMAC-SHA256(SECRET_KEY, purpose:admin:attempt:otp)` in the cache, no plaintext/database row · exactly 30 s (cache TTL **and** server-clock issue timestamp; never extended) · single-use · newest wins · bound to purpose `admin_login_2fa` + admin + attempt · expired code ⇒ generic error, no JWT, admin must repeat e-mail + password for a new code · `ADMIN_LOGIN_OTP_MAX_ATTEMPTS` (3) burns the code, failures feed the per-admin lockout · generation cooldown 10 s and 10/hour (after a correct password only) · never in responses, URLs, JWT claims, audit metadata or logs (log capture tested) · audit events `auth.admin_otp.sent/verified/expired/rate_limited`.
**WARNING AUTH-5:** an e-mail code is a weaker factor than an authenticator app (mailbox + password = access); accepted by requirement. **WARNING AUTH-6:** no recovery if an admin loses mailbox access (operator edits the e-mail in the database). **WARNING OTP-2:** the development e-mail backend is `console`, so the code is printed in the server terminal in development. **WARNING OTP-3:** a failed e-mail send is swallowed and logged (subject only); the admin sees "sent" without receiving mail; no dedicated test. **PASS:** TOTP/backup-code **code** is removed (routes, services, command, settings, `pyotp`); **WARNING TOTP-2:** the dormant `User.totp_secret`, `User.two_factor_enabled` (always false, still in the user payload), table `AdminBackupCode` and `accounts/crypto.py` (needed by migration 0002) were kept so no production data is destroyed; dropping them is a destructive migration that needs your approval.

## 6. JWT audit

Unchanged and re-asserted by tests: HS256, dedicated `JWT_SIGNING_KEY` (≥ 32 chars and ≠ `SECRET_KEY` enforced when `DEBUG` is off, no default), access 15 min, refresh 7 days, rotation + blacklist-after-rotation, `Bearer` header, `user_id` claim, no role/e-mail/status/OTP in claims (**PASS**). `SessionAwareJWTAuthentication` also requires a live per-device session (`sid`, inactivity TTL) and a current per-user epoch (`ep`, bumped on password change/reset/suspension); refresh replay ends that device session and is audited; expired, tampered, wrong-algorithm, refresh-as-access, blacklisted and logged-out tokens are rejected (**PASS**; logout kills both tokens, tested). Fixed earlier: concurrent-refresh race, logout with a garbage refresh token, weak production signing key (**FIXED**).
**WARNING JWT-4** the library's `OutstandingToken` table stores refresh-token strings (hidden in the admin; restrict DB access, schedule `flushexpiredtokens`). **WARNING JWT-5** no absolute session lifetime (a refresh chain used every 30 min can continue indefinitely). **WARNING JWT-7** session/epoch state lives in the cache: a Redis data loss signs everyone out (fails closed). **WARNING JWT-8** refresh tokens travel in the JSON body (HttpOnly-cookie storage needs a frontend contract change). Refresh successes/failures are not individually audited (only reuse; intentional).

## 7. Role / permission audit

Permission classes read `role`/`status` from the database user: `IsAdminRole` (admin + active), `IsStudentRole`, `IsApprovedStudent` (student + active; 403 `REGISTRATION_PENDING/REJECTED` otherwise), `HasCourseAccess` (viewer). Verified by a parametrised walk over **every** route: anonymous 401 (except the documented public routes: student register/login/OTP steps, accounts aliases, forgot/reset password, refresh, admin login + verify, Stripe webhook), student 403 on all `/api/admin/*`, admin 403 on all student routes (**PASS**). Admin write operations (course, resource, approval, access, settings) are admin-only with audit events carrying the admin as actor; a denied attempt writes nothing (**PASS**). No endpoint reads a student id from the request (grep) (**PASS**). Admin accounts are created only with `manage.py createsuperuser` (**WARNING**: no admin invitation flow).

## 8. Student approval audit

Lifecycle enforced server-side: `pending → active` (approve), `pending → rejected` (reject, optional reason), `active → suspended` (suspend revokes all sessions), `suspended → active` (reinstate); any other transition is `409 INVALID_STATE` (e.g. pending cannot be suspended, rejected cannot be approved) (**PASS**). Each decision is audited and notifies the student (`registration_approved/rejected`); a new registration notifies admins and appears in `GET /api/admin/students/approval-requests/` (pending by default). Setting `registration_requires_approval=False` makes new students `active` immediately (**PASS**). Pending/rejected/suspended students never obtain a student JWT (**FIXED/PASS**).

## 9. Course / access audit

One evaluator, `access.services.evaluate_access()`, decides everything (no second state system). States returned to clients: `granted` (active, unexpired), `pending`, `requestable`, `payment_required`, `expired`, `rejected`, `revoked`, `unavailable`; a suspended student cannot sign in at all (**PASS**; tests `test_courses_access.py`, `test_student_decision.py`, `test_approval_payment_pdf_workflow.py`).
- **manual** (`manual_approval`): student request → `pending` → admin approve → `granted` (notified) / reject → `rejected`. **immediate**: access active at once (no fake approval record). **payment** (`payment_required`, positive price enforced by a DB constraint): a request creates a `pending` record; the admin's `payment_required` decision flags it; only then checkout is allowed (`403 PAYMENT_NOT_APPROVED` before any Payment/Stripe call). Transitions: `none→pending→active` (manual), `none→active` (immediate), payment access only via the verified webhook, `active→revoked` (admin or full refund), `active→expired` by `expires_at`.
- Client fields (`student_id`, `status`, `price`, `amount`, `currency`, `payment_required`, `access_status`) are ignored on every student route (tested). Students see only published courses; admin-only fields are never returned.

## 10. Payment audit

`POST /api/student/payment/create-checkout/` (approved + admin-approved payment course) → amount/currency from the database → Stripe hosted Checkout → `POST /api/payment/stripe/webhook/` (no JWT, **signature-verified**; unsigned, wrong-secret, stale and tampered bodies rejected) → payment `paid` + access `active` inside one transaction. A pending Payment row never grants access; amount/currency mismatch does not activate access (admins get `payment_attention`); events are idempotent by event id (replay = no second payment/access/notification); failed/cancelled/expired sessions leave access `pending`; a full refund revokes access (**PASS**). A client-supplied "payment succeeded" can never activate paid access. **WARNING:** Stripe was exercised with mocked SDK calls and locally signed webhooks only, never against a Stripe account (**NOT live-verified**); partial refunds and disputes do not revoke access.

## 11. PDF / resource security audit

Students never receive a raw PDF or storage URL: only server-rendered, watermarked pages (`GET /api/student/viewing/resources/<id>/pages/<n>/`, JSON image, `Cache-Control: no-store`) after: authenticated → approved student → resource published → course published → `evaluate_access()` allows. `pending / payment_required / rejected / revoked / expired` → 403 with the specific code, suspended student → denied, anonymous 401, admin is not a viewer (403). `/download/`, `/media/`, `/public/` are 404; no `storage_key` or URL appears in any response; PDFs are validated on upload; each page view is recorded in `ViewActivity` and the student's history is own-only (**PASS**; `test_viewer.py`, `test_course_crud_pdf_access.py`). **WARNING:** watermarking is a deterrent (screenshots are possible), rendering is synchronous/uncached (throttled 180 pages/min/user), uploads are not malware-scanned, S3 storage is implemented but only the local backend is tested.

## 12. IDOR / data-isolation audit

**PASS.** Ravi's JWT on Ravi's data = allow; on Rahul's name = 403 (`STUDENT_MISMATCH`) with no data; Rahul's JWT on Ravi's = 403. Another student's access record, payment, notification, learning history and viewer activity resolve to 404/403; there is no endpoint that accepts a student id on student routes; admin JWT on student routes = 403; student JWT on admin routes = 403; `?student=`/`?email=` query strings and `X-Role` headers change nothing (tests: `test_three_systems.py`, `test_student_workflow.py`, `test_courses_access.py`, `test_payments.py`, `test_notifications.py`, `test_security.py`). Admin accessing "student data" is the admin API only, by design.

## 13. URL audit

`config/urls.py` has five includes: `admin/`, `api/accounts/`, `api/payment/`, `api/student/` (→ `portal/student_urls.py`), `api/admin/` (→ `portal/admin_urls.py`). **85 API routes** frozen in `backend/tests/url_inventory.json` (checked by `test_url_structure_contract.py`; regenerate only on purpose). `/` and `/api/` are unmatched (404); there is no `/api/admin/` index route (`GET /api/admin/` is 404; the dashboard is `/api/admin/reports/dashboard/`). Route history: TOTP setup/confirm removed (82 → 80); student register/login added (→ 84); named dashboard added (→ 85). Public routes are exactly those listed in section 7. Duplicates kept on purpose and marked deprecated (**WARNING**): `/api/accounts/register*` + `/api/accounts/login/` (STU-3) and `/api/admin/students/registrations/` (alias of `approval-requests/`; remove when the frontend has moved). Django admin URLs live under `/admin/` only; `portal/*_urls.py` are API composers, not Django-admin URLs.

## 14. Duplicate / dead-code audit

Scan (all non-test modules, non-migration): every module-level function/class is referenced, except decorator-registered Django admin classes, app configs, and the retained dormant TOTP schema (`AdminBackupCode`, `crypto.keyed_hash` which is only exercised by the byte-compatibility tests). No duplicate authentication, OTP, JWT or serializer code was found: the admin code check is a single function used by the API; the Django admin reuses `authenticate_credentials`; student and admin login share one credential service. **No code was deleted in this pass** (nothing was proven unused). Earlier cleanup (already done): TOTP/backup-code/enrolment code, the Django-admin 2FA page, the API documentation package. **WARNING:** the deprecated aliases in section 13 are the only intentional duplicates.

## 15. Markdown cleanup audit

Classified every Markdown file in the project:

| File | Class | Action |
|---|---|---|
| `Readme.md` | required | kept, updated |
| `PROJECT_ISSUES_AUDIT.md` | the one audit file | this file |
| `backend/docs/FRONTEND_HANDOFF.md` | required (API contract) | kept, updated |
| `LIVE_SERVER_AUDIT.md` | runbook (ngrok/friend-PC setup, backed by `test_tunnel_config.py`) | **renamed** `LIVE_SERVER_RUNBOOK.md` (it is not an audit) |
| `backend/ADMIN_COURSE_APPROVAL_AUDIT.md`, `ADMIN_COURSE_CRUD_PDF_ACCESS_AUDIT.md`, `PAYMENT_APPROVAL_PDF_WORKFLOW_AUDIT.md` | dated reports of 2026-10-05 | **merged** into sections 7, 9, 10, 11, 12 and **removed** |
| `backend/API_ENDPOINT_VERIFICATION.md` | generated snapshot (100 route/method probes, old test counts, no generator in the repo) | **removed**: superseded by `tests/url_inventory.json` (every route, method, view, name, permission) enforced by tests, and by `FRONTEND_HANDOFF.md` |
| 5 admin/2FA reports, `JWT_SECURITY_AUDIT`, `FINAL_BACKEND_AUDIT`, `BACKEND_AUDIT`, 3 URL/structure audits | dated/contradictory | merged and removed in the previous pass |

No `CLAUDE.md` or other architecture file exists. No competing audit remains; removed files were copied to the session scratchpad first (the folder is not a git repository, so deletions cannot be undone from the project itself). `team.context.txt` and `empty.txt` (plain-text notes, not Markdown) still mention the removed file names; they were left untouched.

## 16. Test results

| Check | Result (2026-10-06) |
|---|---|
| `manage.py check` | **PASS** |
| `manage.py makemigrations --check` | **PASS** (no changes; this audit added no migration) |
| `pytest` | **1394 passed, 15 skipped, 0 failed** (the skips are the public routes in the anonymous guard test) |
| URL configuration | **PASS** (85 routes match the frozen inventory) |
| Live smoke: `/admin/`, `/admin/login/`, `/api/admin/login/`, `/api/admin/*`, `/api/student/login/`, `/api/student/<name>/dashboard/` | **PASS** (see below) |

Key modules: `test_three_systems.py` (independence of the three interfaces, admin account checks, Ravi/Rahul, blacklist, sidebar), `test_django_admin_login.py`, `test_admin_email_otp.py`, `test_student_workflow.py` (incl. `TestNamedDashboard`), `test_django_admin.py`, `test_security.py`, `test_jwt_security.py`, `test_courses_access.py`, `test_approval_payment_pdf_workflow.py`, `test_payments.py`, `test_viewer.py`, `test_url_structure_contract.py`. Live checks on throw-away databases: Django admin e-mail + password opens `/admin/` with no 2FA text and no e-mail (A); admin password → code → JWT → dashboard, real 31 s expiry refused, old code refused after a new one (B); student register → pending 403 → approve → login → dashboard and named dashboard, wrong-name 403, logout/suspend (C).

## 17. External-service verification status

| Service | Status |
|---|---|
| PostgreSQL (your own server) | **BLOCKER for production** — not installed/verified here; a throw-away PostgreSQL 16 run on 2026-10-01 passed the suite earlier and found one SQLite-hidden bug (fixed) |
| Redis | **BLOCKER for production** — lockout, OTP, sessions and throttles need a persistent shared Redis; only the in-memory cache was exercised |
| SMTP | **BLOCKER for production** — the 30 s admin code depends on timely delivery; only in-memory/console mail was used |
| Stripe | **WARNING** — mocked SDK + locally signed webhooks; never run against a Stripe account (use `stripe listen`) |
| S3 | **WARNING** — implemented (`django-storages`), local storage only tested |
| WSGI/ASGI server, `check --deploy` | **WARNING** — no server package in `requirements.txt`; `check --deploy` was last reviewed before the Django admin site was restored |

Nothing above is claimed production-verified.

## 18. Remaining issues

| ID | Status | Issue | Action |
|---|---|---|---|
| ENV-1 | **BLOCKER** (production) | PostgreSQL, Redis, SMTP not exercised against real services; production keys/hosts (`DEBUG=False`, `SECRET_KEY`, `JWT_SIGNING_KEY`, `FIELD_ENCRYPTION_KEY`, `ALLOWED_HOSTS`, CORS, `DJANGO_ADMIN_ALLOWED_HOSTS`) not configured | follow section 19 checklist |
| AUTH-4 | WARNING | `/admin/` single-factor | keep it local |
| AUTH-5/6 | WARNING | e-mail-only second factor; no recovery path | decide on stronger factor / operator procedure |
| AUTH-7/8 | WARNING | `/admin/password_change/`; no admin-session inactivity timeout | disable/wrap; add timeout |
| OTP-2/3 | WARNING | console e-mail backend prints the code in development; delivery failures are silent | use SMTP; surface failures |
| TOTP-2 | WARNING | dormant TOTP columns/table/`crypto.py` | approve a destructive migration later |
| STU-3 | WARNING | deprecated duplicate endpoints (`/api/accounts/register*`, `/login/`, admin `registrations/`) | remove once clients migrate |
| STU-8 | WARNING | student names are not unique/immutable (routing label only) | add a unique handle only if the frontend needs it |
| JWT-4/5/7/8 | WARNING | token table, no absolute session cap, cache-held session state, refresh in JSON body | see section 6 |
| AUD-1 | WARNING | no DB-level protection of audit rows (admin shows them read-only; direct SQL can edit) | optional trigger migration |
| ENV-2 | WARNING | unpinned requirements | generate a lock file |
| MIG-1 | WARNING | migration `accounts/0005` (proxy models, state-only) is not applied to the dev database | `python manage.py migrate` |
| OTHER | WARNING | carried from earlier reports, not re-verified: registration reveals e-mail existence only via the 409 race; synchronous PDF rendering; no malware scan; partial refunds/disputes ignored; publishing a course notifies every active student in one request; no health endpoint | as needed |

## 19. Recommended future work

1. Provision PostgreSQL + Redis + SMTP, run `migrate`, and repeat the live smoke test (section 16) against that stack; exercise Stripe with `stripe listen` and an S3 bucket.
2. Production settings: `DEBUG=False`, dedicated `SECRET_KEY`, `JWT_SIGNING_KEY`, `FIELD_ENCRYPTION_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `TRUST_PROXY_HEADERS` behind a proxy that overwrites `X-Forwarded-For`; a WSGI/ASGI server; run `manage.py check --deploy`; schedule `flushexpiredtokens`.
3. Decide on a stronger admin second factor and an admin-recovery procedure; consider disabling `/admin/password_change/` and adding a Django-admin inactivity timeout.
4. Move the frontend off the deprecated aliases, then delete them; remove the dormant TOTP schema in a reviewed migration.
5. Optional hardening: audit-row trigger, absolute session lifetime, unique student handle, admin invitation flow, AV scanning and page caching, lock file for dependencies.

---

**What changed in this pass:** `IsAdminRole` now requires `status=active` (**FIXED**); new acceptance tests `test_three_systems.py` (16); the three workflow reports and the endpoint snapshot were merged and removed; `LIVE_SERVER_AUDIT.md` renamed `LIVE_SERVER_RUNBOOK.md`. Earlier today: Django admin password-only session, admin e-mail OTP, student login gate and named dashboard, TOTP code removal.

---

## 20. LAN testing (same Wi-Fi only, 2026-10-07)

Scope: local development, a friend on the same Wi-Fi reaches this PC. Not a deployment; nothing is exposed to the internet.

| Item | Result |
|---|---|
| LAN IP (Wi-Fi, at time of test) | 192.168.0.168 (DHCP: re-check with `ipconfig` and update `.env` if it changes) |
| Start command (from `backend/`) | `..\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000` (0.0.0.0 = listen on all interfaces; browsers must use the LAN IP, never 0.0.0.0) |
| PC URL / friend URL | `http://127.0.0.1:8000` / `http://192.168.0.168:8000` (`/admin/`, `/api/student/login/`, `/api/admin/login/`) |
| Config changed | `.env` only: `ALLOWED_HOSTS` + `DJANGO_ADMIN_ALLOWED_HOSTS` gained the LAN IP (the `/admin/` host guard 404s any host not in the second list). `.env.example` documents it. No code change. |
| CSRF | **PASS, no change.** The API is JWT-only (no cookies); the only session surface is `/admin/`, which is same-origin, so `CSRF_TRUSTED_ORIGINS` is not needed (and a test forbids adding it blindly). |
| CORS | **PASS, no change.** Only needed if a browser app is served from another device: then add that exact origin to `CORS_ALLOWED_ORIGINS`. Unlisted origin gets no `Access-Control-Allow-Origin`. |
| Windows Firewall | **WARNING.** Wi-Fi profile is *Public*; no port-8000 rule and no rule for the venv `python.exe` exists, so the friend is probably blocked. See command below. Not executed (needs an elevated shell; self-test from the PC cannot prove inbound reachability). |
| Stripe | Unchanged. Stripe cannot reach a LAN IP: use `cloudflared tunnel --url http://127.0.0.1:8000` (`.trycloudflare.com` is already in `ALLOWED_HOSTS`) and set the webhook to the HTTPS tunnel URL + `/api/payment/stripe/webhook/`. Keys stay in `.env`. |
| WARNING: `TRUST_PROXY_HEADERS=True` | Needed for tunnels, but on a LAN a direct client can forge `X-Forwarded-For` and dodge IP-based lockout/throttles. Set it to `False` when no tunnel is running. |

Firewall (elevated PowerShell). The rule applies to the Private profile only, so either mark the Wi-Fi as Private first (Settings > Network > Wi-Fi > Network profile type; only on a trusted home network) or the rule will not match:

```powershell
New-NetFirewallRule -DisplayName "EduVault Django LAN 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private -RemoteAddress LocalSubnet
```

Remove later: `Remove-NetFirewallRule -DisplayName "EduVault Django LAN 8000"`.

Test results (from this PC, server on 0.0.0.0:8000): `manage.py check` clean; `makemigrations --check` no changes; pytest 1394 passed / 15 skipped. 127.0.0.1 and 192.168.0.168 both: `/admin/login/` 200, `/` 404 (by design), login routes 405 on GET; admin API bad login 401; student dashboard without JWT 401; foreign Host header 400; foreign CORS origin gets no allow header. **Not tested:** the friend's device (needs the firewall step), a real admin e-mail OTP round trip and student login over LAN (covered by `tests/test_three_systems.py`, unchanged).

---

## 21. Frontend & Backend Final Integration Audit & Fixes (2026-10-07)

### Audit Findings & Root Causes
1. **Mock Code Debris**: `src/lib/mock/data.ts`, `src/lib/mock/seed.ts`, and `src/lib/api/mock-utils.ts` were dead legacy files. `mock-utils.ts` imported non-existent `MOCK_LATENCY_MS`, breaking `next build`.
2. **API Envelope Handling**: Django wraps all responses in `{ success: true, data: ..., meta: ... }` and errors in `{ success: false, error: { code, message, details } }`. Frontend `http.request` in `client.ts` returned raw envelopes without unwrapping `data` or normalizing `meta` pagination (`count`, `page_size`, `total_pages`), breaking table pagination and object access (`course.name`, `data.tokens`, etc.).
3. **Token Refresh Envelope**: `/api/accounts/refresh/` returns `{ success: true, data: { tokens: { access, refresh } } }`. `refreshAndRetry` looked for top-level `tokens`, causing refresh attempts to throw a TypeError.
4. **Error Handling Envelope**: Backend error responses have `{ error: { code, message, details } }`. `client.ts` expected `message` at the top level, obscuring error messages.
5. **Student Authentication Canonical Endpoints**: Student login was calling deprecated `/accounts/login/` instead of `/student/login/`. Registration was calling `/student/register/` directly without the required email OTP verification steps (`send-otp/`, `verify-otp/`) or `phone_number`, failing with 403 `EMAIL_NOT_VERIFIED`.
6. **Admin vs Student Login Routing**: The login page had no distinction between Admin application login (POST `/api/admin/login/` + OTP) and Student login (POST `/api/student/login/`). Dedicated routes `/login/admin` and `/login/student` were missing.
7. **Resource API Parameter Mismatches**: Resource list queried `course_id` instead of backend's `course`. Multipart upload used `name` instead of `title`. Base64 protected page responses were not formatted as data URIs for client image rendering.
8. **Payment & Access API Contract Mismatches**: Checkout session creation sent `course_id` instead of `course` expected by `CheckoutSerializer`. Access decision PATCH sent `{ status }` instead of `{ action: "approve" | "revoke" }` required by `AccessDecisionSerializer`.
9. **Environment Configuration**: `.env.local` pointed to relative `/api` while `.env.example` still referenced `/api/v1` and `USE_MOCK_API=true`. Backend `CORS_ALLOWED_ORIGINS` was missing `http://127.0.0.1:3000`.

### Fixes Applied
- **Removed Dead Mock Code**: Deleted `src/lib/mock/` and `src/lib/api/mock-utils.ts`. Verified 0 remaining mock business data imports.
- **Envelope Unwrapping & Pagination Normalization**: `client.ts` now inspects `{ success, data, meta }`. For paginated responses, normalizes to `PaginatedResponse<T>` (`{ data, page, pageSize, total, totalPages, unreadCount }`). For standard responses, unwraps `json.data`. Errors extract `json.error.message`, `code`, and `details`.
- **Token Refresh**: `refreshAndRetry` correctly unwraps `json.data.tokens` and persists rotated refresh tokens.
- **Auth Flow Separation**:
  - Student Login: POST `/api/student/login/` → JWT → `/student/dashboard`.
  - Admin Login: POST `/api/admin/login/` → 6-digit OTP email challenge → `/verify-2fa` → POST `/api/admin/login/2fa/verify/` → JWT → `/admin/dashboard`.
  - Django Admin: completely distinct session-based auth at `/admin/login/`.
  - Routes added: `/login/admin`, `/login/student`, and `/login` with an intuitive role switcher.
- **Student Registration Flow**: Implemented full 3-step registration:
  1. Details collection (`name`, `email`, `phone`, `password`, `confirmPassword`).
  2. Send OTP (`POST /api/student/register/send-otp/`).
  3. Verify OTP (`POST /api/student/register/verify-otp/`) & Register (`POST /api/student/register/` with `first_name`, `last_name`, `phone_number`, `email`, `password`).
- **Resource, Access & Payment APIs Fixed**:
  - `course`: used in `paymentApi.createCheckoutSession`, `resourceApi.listByCourse`, `resourceApi.upload`, `registrationApi.requestAccess`.
  - `action`: mapped in `accessApi.updateStatus` (`"approve"` / `"revoke"`).
  - Page viewing: `resourceApi.getPage` formats base64 payload as `data:image/jpeg;base64,...`.
  - Admin dashboard stats: mapped ORM aggregate counts directly to `AdminDashboardStats`.
- **Environment & CORS**:
  - `eduvault/.env.local`: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api`, `NEXT_PUBLIC_USE_MOCK_API=false`.
  - `eduvault/.env.example`: updated without `/v1`, with `NEXT_PUBLIC_USE_MOCK_API=false`.
  - `backend/.env`: added `http://127.0.0.1:3000` and LAN IP `http://192.168.0.168:3000` to `CORS_ALLOWED_ORIGINS`.

### Files Changed & Deleted
- **Deleted**:
  - `eduvault/src/lib/api/mock-utils.ts`
  - `eduvault/src/lib/mock/data.ts`
  - `eduvault/src/lib/mock/seed.ts`
- **Updated**:
  - `backend/.env`
  - `eduvault/.env.local`
  - `eduvault/.env.example`
  - `eduvault/src/types/index.ts`
  - `eduvault/src/lib/api/client.ts`
  - `eduvault/src/lib/api/authApi.ts`
  - `eduvault/src/lib/api/courseApi.ts`
  - `eduvault/src/lib/api/accessApi.ts`
  - `eduvault/src/lib/api/paymentApi.ts`
  - `eduvault/src/lib/api/registrationApi.ts`
  - `eduvault/src/lib/api/resourceApi.ts`
  - `eduvault/src/lib/api/studentApi.ts`
  - `eduvault/src/lib/api/reportApi.ts`
  - `eduvault/src/hooks/use-auth.ts`
  - `eduvault/src/components/auth/auth-schemas.ts`
  - `eduvault/src/components/auth/login-view.tsx`
  - `eduvault/src/components/auth/register-view.tsx`
  - `eduvault/src/components/auth/verify-two-factor-view.tsx`
- **Created**:
  - `eduvault/src/app/(hero-auth)/login/student/page.tsx`
  - `eduvault/src/app/(hero-auth)/login/admin/page.tsx`

### Verification Test Results
- `python manage.py check`: **PASS (0 issues)**
- `python manage.py makemigrations --check`: **PASS (no changes detected)**
- `pytest`: **1394 passed, 15 skipped, 0 failed**
- `npm run lint`: **PASS (0 errors, 0 warnings)**
- `npm run build`: **PASS (Compiled in 3.5s, all 33/33 static and dynamic routes generated successfully)**

---

## 22. Next.js API Proxy & Auth 401 Interception Resolution (2026-10-07)

### Issue Identified
1. **Next.js Rewrite Trailing Slash Stripping**: Requests through `/api/*` rewrites in `next.config.ts` stripped the trailing slash when forwarding to Django (`/api/student/login` instead of `/api/student/login/`). When a `POST` request arrived without trailing slash, Django's `CommonMiddleware` (with `APPEND_SLASH=True`) raised `RuntimeError: You called this URL via POST, but the URL doesn't end in a slash and you have APPEND_SLASH set. Django can't redirect to the slash URL while maintaining POST data.`.
2. **Next.js 308 Canonical Redirect**: Next.js by default redirected requests with trailing slashes via HTTP 308 to non-trailing slash routes.
3. **Client 401 Interceptor Masquerading Login Failures**: `client.ts` automatically invoked `refreshAndRetry` on any 401 response. When logging in with invalid credentials or an unverified email, the server returned 401 `INVALID_CREDENTIALS`, but `client.ts` tried to refresh an absent token, causing a misleading "Session expired. Please log in again." error.
4. **Clarification on Root URL (`/`)**: Navigating directly to `http://127.0.0.1:8000/` or `/api/` in a web browser produces a Django 404 page ("Page not found at /") by design. Django is an API backend with no HTML root; Django Admin is at `/admin/`, and the web application is accessed via Next.js at `http://localhost:3000`.

### Fix Applied
1. Updated `eduvault/next.config.ts`:
   - Set `skipTrailingSlashRedirect: true`.
   - Added explicit rewrite matching `/api/:path*/` -> `${backendOrigin}/api/:path*/` to guarantee trailing slashes are strictly preserved on proxied API calls.
2. Updated `eduvault/src/lib/api/client.ts`:
   - Added `isAuthPath` check so that 401 responses on authentication endpoints (`/login`, `/register`, `/refresh`, `/forgot-password`, `/reset-password`) are passed through to the error handler instead of triggering `refreshAndRetry`.
3. Updated `eduvault/src/components/auth/login-view.tsx`:
   - Removed "Continue with Google" button and divider from the student login form as requested.
4. Updated `eduvault/src/lib/api/authApi.ts`:
   - Aligned TypeScript signatures for `resendTwoFactor` eliminating all compiler and linter warnings.

