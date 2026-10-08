# EduVault live backend (ngrok) - backend on my PC, Next.js on my friend's PC

> Note (2026-10-06): the admin sign-in is now password + e-mailed 6-digit code (see `PROJECT_ISSUES_AUDIT.md`); TOTP enrolment no longer exists. Read the rest of this runbook with that in mind.

Updated 2026-10-05. This replaces the earlier two-tunnel draft: only the Django backend is tunnelled; the frontend runs on the friend's PC.
No secret, token or `.env` value is written here. `<...>` is a value that only exists once ngrok runs.

```text
Local Backend:      http://127.0.0.1:8000
Public Backend:     https://<ngrok-domain>          (printed by `ngrok http 8000`; changes on every restart on the free plan)
API Prefix:         /api/                            (there is no /api/v1/)
Frontend Location:  Friend's PC (Next.js, port 3000 unless they tell you otherwise)
Frontend API Base:  https://<ngrok-domain>/api
```

## 0. Status at a glance (re-checked 12:52)

| Item | Status |
|---|---|
| Backend: Django + DRF, existing database (SQLite file), no Docker | PASS (`manage.py check` clean) |
| Python packages (`backend\requirements.txt`) in the project venv `Edu_vauilt\.venv` (Python 3.12.6, Django 5.2.17) | PASS - all installed, `pip check` clean; nothing to install |
| ngrok installed | **FAIL** - `ngrok` not found; install and sign in (section 3) |
| ngrok running / public URL | **NOT TESTED** - no tunnel exists, so there is no public URL yet |
| Tunnel settings in `backend\.env` (hosts, CORS header, proxy trust) | PASS (set) - **but the Django process answering on port 8000 is stale** (see below) |
| Django bound privately | PASS - only `127.0.0.1:8000` now (no `0.0.0.0`); **two** Django processes (PIDs 17024, 5640) share that port |
| Friend's frontend | **NOT TESTED** - it is on the friend's PC |
| CORS / JWT / student + admin API through the real tunnel | **NOT TESTED** (PASS in the loopback simulation, section 5) |
| Stripe webhook | **NOT TESTED** (signature check unchanged) |

**Stale server warning (verified):** the server now answering on `127.0.0.1:8000` returned `400` for an ngrok-style `Host`, and its CORS preflight did **not** list `ngrok-skip-browser-warning`. That process was started before the tunnel block was added to `.env` (Django reads `.env` only at start). Press Ctrl+C in **both** Django terminals (or `Stop-Process -Id 17024,5640`), then start exactly one server with the commands in section 3. Otherwise the tunnel would show `DisallowedHost` / CORS errors.

## 0b. Required Python packages (verified installed; do not reinstall)

From `backend\requirements.txt`: Django 5.1-5.2, djangorestframework, djangorestframework-simplejwt, django-cors-headers, django-environ, psycopg[binary], django-redis, redis, argon2-cffi, pyotp, pypdfium2, Pillow, django-storages[s3], stripe, cryptography (+ pytest, pytest-django, pytest-env for tests). All are present in `Edu_vauilt\.venv`. The tunnel needs **no Python package**; ngrok is a separate program. Only on a fresh machine: `pip install -r requirements.txt`.

## 1. What the audit found (backend as it is now)

| Area | Finding |
|---|---|
| Auth | bearer JWT in `Authorization: Bearer <access_token>`; no cookies, no sessions, **no CSRF middleware**, so `CSRF_TRUSTED_ORIGINS` is neither needed nor set |
| CORS | `django-cors-headers`, exact origins from `CORS_ALLOWED_ORIGINS`; never `CORS_ALLOW_ALL_ORIGINS`. Default allowed request headers already include `Authorization` and `Content-Type` |
| ngrok warning page | on free plans ngrok answers browser calls with an HTML warning page unless the request carries `ngrok-skip-browser-warning`; that page has no CORS headers, so the browser reports a CORS error. The backend therefore must **allow that header**: this was the one backend change (see section 2) |
| `ALLOWED_HOSTS` | env-driven; an ngrok hostname that is not listed raises `DisallowedHost` |
| Client IP | `TRUST_PROXY_HEADERS` (env, default False). Through ngrok every request reaches Django from `127.0.0.1`, so login lockout (per e-mail + IP), OTP cooldown and throttles would be shared by every visitor; ngrok sends the real address in `X-Forwarded-For` |
| `FRONTEND_URL` | only used to build Stripe checkout return URLs: it must be the origin of the friend's frontend |
| API surface | `/api/accounts/*`, `/api/student/*`, `/api/admin/*`, `/api/payment/stripe/webhook/`. There are no API-docs pages (Swagger/OpenAPI were removed). No landing page (`/` is 404 by design). No public file/media route |
| What the frontend must send | the three auth flows: student `POST /api/accounts/login/`; admin `POST /api/admin/login/` then `/api/admin/login/2fa/{setup,confirm,verify}/`; then `Authorization: Bearer <access>` and, when it expires (15 min), `POST /api/accounts/refresh/`. JSON bodies, `Content-Type: application/json` (PDF upload is multipart) |
| Database / cache | SQLite file + in-memory cache, kept as is. Nothing else is opened to the network (no PostgreSQL / Redis here) |
| Local server today | earlier a `0.0.0.0:8000` server (reachable from the whole Wi-Fi) was seen; it is gone. Now two servers share `127.0.0.1:8000`, both older than the `.env` tunnel block (see section 0). Stop both, start one |
| Virtual environment | the project venv is **`Edu_vauilt\.venv`** (project root). There is no `backend\venv`, so `.\venv\Scripts\Activate.ps1` inside `backend` does not exist |
| ngrok | **not installed** on this PC; I cannot sign in for you (the authtoken is yours) |

## 2. Backend changes made (the only ones)

* `config/settings.py`: `CORS_ALLOW_HEADERS` = django-cors-headers defaults **+** `CORS_EXTRA_ALLOW_HEADERS` from the environment (default empty, so nothing changes unless you set it). No other code changed, no URL changed.
* `backend/.env` (dev file; secrets untouched) - tunnel block:
  ```
  ALLOWED_HOSTS=localhost,127.0.0.1,.ngrok-free.app,.ngrok-free.dev
  CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
  CORS_EXTRA_ALLOW_HEADERS=ngrok-skip-browser-warning
  FRONTEND_URL=http://localhost:3000
  TRUST_PROXY_HEADERS=True
  ```
  `.ngrok-free.app` / `.ngrok-free.dev` are suffix matches, so a new free URL needs no edit; for something stricter replace them with the exact host ngrok prints.
  **Friend's origin:** CORS must list the exact origin in the *friend's browser address bar* (scheme + host + port, no path, no trailing slash). `http://localhost:3000` is already there. If they run on another port, or open it by IP or a domain, add that exact origin to `CORS_ALLOWED_ORIGINS` (comma separated) and restart Django.
  Set `TRUST_PROXY_HEADERS=False` again when the tunnel is stopped.
* `backend/.env.example` documents `CORS_EXTRA_ALLOW_HEADERS`.
* `tests/test_tunnel_config.py` (12 tests): preflight with Authorization + the ngrok header, unknown origins get no CORS header, never `*`, header list from the environment, ngrok host suffix accepted and look-alike hosts rejected (400), real client IP used behind the proxy (and a forged `X-Forwarded-For` ignored when the setting is off), bearer JWT through proxy headers.

## 3. MY PC

One-time:
```powershell
winget install --id Ngrok.Ngrok
ngrok config add-authtoken YOUR_NGROK_TOKEN     # token stays in ngrok's own config; never in Django's .env, never in Git
```
Every time (two terminals). The project's virtual environment is `Edu_vauilt\.venv` (not `backend\venv`):

Terminal 1 - Django, private on loopback only:
```powershell
cd "C:\Users\Malladi Ravidra\OneDrive\Desktop\Edu_vauilt"
.\.venv\Scripts\Activate.ps1
cd backend
python --version; python -m django --version     # expect Python 3.12.x and Django 5.2.x
python manage.py check
python manage.py runserver 127.0.0.1:8000        # never 0.0.0.0
```
Terminal 2 - tunnel:
```powershell
ngrok http 8000
```
Copy the `Forwarding  https://<ngrok-domain> -> http://localhost:8000` URL. Read it again any time with `Invoke-RestMethod http://127.0.0.1:4040/api/tunnels`. Check from your PC:
```powershell
curl.exe -i http://127.0.0.1:8000/api/student/profile/          # 401 = Django is answering
curl.exe -i -H "ngrok-skip-browser-warning: 1" https://<ngrok-domain>/api/student/profile/
curl.exe -i -X OPTIONS https://<ngrok-domain>/api/accounts/login/ -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: authorization,content-type,ngrok-skip-browser-warning" -H "ngrok-skip-browser-warning: 1"
```
The last one must answer `200` with `Access-Control-Allow-Origin: http://localhost:3000`. Send your friend the URL `https://<ngrok-domain>/api`. Ctrl+C both terminals when done and set `TRUST_PROXY_HEADERS=False`.

If you restart ngrok the domain changes: send the new URL (no Django edit is needed with the suffix hosts; restart Django only if you changed `.env`).

## 4. FRIEND'S PC

1. Open the Next.js project folder (the one with `package.json`).
2. Find how the project reads its API base URL (search for `process.env` / `API_BASE`); use that name. If none exists, create `frontend/.env.local` with:
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://<ngrok-domain>/api
   ```
   (public, browser-visible value: URL only, never a key or password; do not commit `.env.local`).
3. Every request to the backend must send the extra header `ngrok-skip-browser-warning: 1` (put it once in the project's single API client / fetch wrapper) plus `Authorization: Bearer <access_token>` after login and `Content-Type: application/json`.
4. Restart Next.js (env is read at start): `Ctrl+C`, then `npm run dev`.
5. Open `http://localhost:3000` in their browser.
6. Test student: register (OTP code is printed in **my** Django terminal because mail uses the console backend - I read it out to them) or log in -> dashboard -> My courses -> course details -> viewer -> payment requests -> notifications -> profile -> settings -> logout.
7. Test admin: login (password, then the 6-digit code e-mailed to the admin, valid 30 s) -> dashboard -> students -> courses -> resources/PDF -> access -> payments -> reports -> profile.
8. DevTools -> Network: every call must go to `https://<ngrok-domain>/api/...`. Nothing may go to `localhost:8000` or `127.0.0.1:8000` (that is the friend's own PC). Console must show no CORS errors.

## 5. Verification evidence

NOT possible yet with the real tunnel: ngrok is not installed or signed in, and the frontend is on another PC. What was verified instead, against a **temporary private server on 127.0.0.1:8011 with a scratch database** (your dev DB untouched, stopped afterwards), using your real `.env`, with the ngrok-style `Host`, `Origin`, `X-Forwarded-*` and `ngrok-skip-browser-warning` headers set by hand:

* 41 of 42 scripted checks passed; the one "failure" was a false positive of my own check (the word `password` matched the number setting `password_min_length`; the actual secret values are absent from the settings response).
* Host: the ngrok-style host and loopback accepted, a foreign host `400`.
* CORS: preflight returns the friend's origin and allows `authorization` + `ngrok-skip-browser-warning`; an unknown origin gets no CORS header.
* Student: login `200`, dashboard, profile, my courses, catalogue, course detail, payment requests, notifications, settings, learning history all `200`; no token `401`; student token on admin API `403`; wrong password `401`.
* Admin: password login gives only a 2FA challenge; the e-mailed code (not the password) gives tokens; dashboard, students, courses, resources, access, payments, reports, profile, settings, notifications all `200`; admin token on the student API `403`; settings response contains no secrets.
* Files: `/media/...`, `/private_media/...`, `/static/...` all `404`; viewer without a token `401`, with access and a token `200`.
* Stripe webhook without a valid signature is refused. pytest: 904 passed, 13 skipped.

## 6. Stripe

Current setup (one tunnel: friend's frontend -> ngrok -> Django API) supports normal frontend/backend testing, including creating a checkout if test-mode keys are set. **Stripe cannot reach the webhook** on a free tunnel unless Stripe is pointed at `https://<ngrok-domain>/api/payment/stripe/webhook/`, and until then paid access is never activated (that is by design: only a verified webhook activates it). Signature verification is not weakened. To test it, either add that URL as a *test-mode* webhook endpoint in the Stripe dashboard (put its signing secret in `backend\.env` as `STRIPE_WEBHOOK_SECRET`, with a test `STRIPE_SECRET_KEY`), or use the Stripe CLI listener forwarding to `http://127.0.0.1:8000/api/payment/stripe/webhook/`. Stripe webhook status: NOT TESTED.

## 7. Security

* Only Django is exposed, through ngrok. Do not forward router ports, open firewall rules, tunnel other ports, or run Django on `0.0.0.0`.
* Anyone with the URL can reach the API (login still required for everything private). Use dummy data in the shared dev database, test-mode Stripe keys only, and do not give your friend admin credentials or the admin enrolment code.
* The free ngrok domain is public and guessable only by whoever has the URL; stop the tunnel when finished.
* `TRUST_PROXY_HEADERS=True` makes Django believe `X-Forwarded-For`; acceptable only while Django listens on loopback and the tunnel is the sole path in.
* Secrets stay on your PC: `SECRET_KEY`, `JWT_SIGNING_KEY`, Stripe, SMTP and encryption keys never go into the friend's frontend or any `NEXT_PUBLIC_*` variable.
* The in-memory cache means a Django restart signs everyone out and clears lockouts/OTP codes.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| CORS error in the browser console | (1) the page origin is not in `CORS_ALLOWED_ORIGINS` (exact, no trailing slash; restart Django); (2) the request lacks `ngrok-skip-browser-warning` so ngrok's warning page answered (add the header to the API client); (3) the request carries another custom header not in `CORS_EXTRA_ALLOW_HEADERS` |
| `DisallowedHost` / 400 `Invalid HTTP_HOST header` | the ngrok host is not in `ALLOWED_HOSTS` (suffixes `.ngrok-free.app` / `.ngrok-free.dev` are set; a `*.ngrok.app` / `.ngrok.io` domain needs adding); no scheme, no spaces; restart Django |
| CSRF error | not expected (no CSRF middleware, bearer auth). If you see one the request is not hitting this backend |
| 502 / ERR_NGROK_8012 | Django is not running on 8000 or listens elsewhere; run it on `127.0.0.1:8000` and restart `ngrok http 8000` |
| ngrok HTML "visit site" page instead of JSON | missing `ngrok-skip-browser-warning: 1` header on that request |
| 401 `NOT_AUTHENTICATED` | no/expired token: the client must send `Authorization: Bearer <access>` and refresh through `/api/accounts/refresh/` |
| 429 `ACCOUNT_LOCKED` / `RATE_LIMITED` | too many tries for that e-mail + IP; wait 15 minutes or restart Django (in-memory) |
| login works for you but not the friend | wrong password/status: a *pending* student logs in but gets `REGISTRATION_PENDING` on content until approved |
| requests still go to `localhost:8000` | the friend's `.env.local` is not loaded: restart `npm run dev`; the variable must start with `NEXT_PUBLIC_`; search their code for hard-coded `localhost` |
| ngrok URL changed | send the new `https://<ngrok-domain>/api`; the friend updates `.env.local` and restarts Next.js; add nothing to Django (suffix hosts) unless you pinned an exact host |
| OTP e-mail never arrives | mail uses the console backend: the code is in **your** Django terminal |
| PDF will not display | the viewer returns JSON with a base64 image per page (no PDF URL by design); needs a Bearer token and an active access record |

## 9. Final report

```text
Backend:                 Django + DRF, existing database, no Docker. Local http://127.0.0.1:8000 is running but STALE (restart, see section 0); config verified on a temporary 127.0.0.1:8011 server (stopped)
Public:                  https://<actual-ngrok-domain>.ngrok-free.app   NOT AVAILABLE (no tunnel yet)
API:                     https://<actual-ngrok-domain>.ngrok-free.app/api/
Tunnel:                  ngrok - NOT INSTALLED -> FAIL
Docker:                  not used
ngrok:                   NOT RUNNING (not installed / not signed in)
Public API:              https://<ngrok-domain>/api   (unknown until you run `ngrok http 8000`)
API prefix:              /api/
Frontend:                Friend's PC (not accessible from here)
CORS:                    PASS in simulation (real tunnel + real frontend NOT TESTED)
JWT:                     PASS in simulation (Bearer through proxy headers)
Student API:             PASS in simulation (9 endpoints, isolation 401/403 checks)
Admin API:               PASS in simulation (10 endpoints, mandatory e-mailed code)
PDF/resource protection: PASS (no public file route, viewer needs token + access)
Stripe webhook:          NOT TESTED (signature check still enforced)
```
