# EduVault backend

Django 5 + Django REST Framework (`APIView` only, explicit `path()` routes). PostgreSQL and Redis in production, S3-compatible private storage for PDFs, Stripe payments, e-mailed one-time code (30 s) + JWT for the admin API.

## Project layout

```text
Edu_vauilt/
├── .venv/                  virtual environment (outside backend/, git-ignored)
├── backend/                this folder (run every manage.py command from here)
└── frontend/               not part of this repository checkout
```

## First-time setup (Windows / PowerShell)

```powershell
# from the project root (the folder that contains backend/)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

cd backend
copy .env.example .env          # then fill in real values; .env is never committed
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Activate the environment in every new terminal with `.\.venv\Scripts\Activate.ps1` (from the project root). In VS Code, select the interpreter `Edu_vauilt\.venv\Scripts\python.exe`.

## Configuration

Everything comes from `backend/.env` (see `.env.example` for every variable). There is a single settings module, `config/settings.py`.

| | Local development | Production |
|---|---|---|
| Database | `DATABASE_URL=sqlite:///...` is acceptable | PostgreSQL: `postgres://USER:PASSWORD@HOST:5432/eduvault` |
| Cache / sessions / rate limits | `REDIS_URL=locmemcache://` | Redis: `redis://HOST:6379/1` |
| `DEBUG` | `True` | `False` (then `FIELD_ENCRYPTION_KEY` is mandatory) |

## Tests and checks

```powershell
cd backend
pytest                              # the test suite (pytest, not "manage.py test")
python manage.py check
python manage.py makemigrations --check
```

`pytest.ini` forces an in-memory SQLite database and cache, so the suite never touches PostgreSQL, Redis, Stripe or SMTP.

## API

Route groups (mounted in `config/urls.py`, each app defines its own `urls.py`):

| Prefix | Purpose |
|---|---|
| `/api/accounts/` | logout, refresh, me, password change, forgot/reset password (register/login kept as deprecated aliases) |
| `/api/student/course/` | published course catalogue |
| `/api/student/` | register (3 steps), login (email + password), dashboard, access, payments, learning history |
| `/api/student/viewing/` | protected, watermarked PDF pages |
| `/api/payment/` | Stripe checkout and webhook |
| `/api/student/notifications/` | in-app notifications |
| `/api/admin/` | login (password, then the e-mailed code at `login/2fa/verify/`), course (+ resources), students (+ registrations, access, payments, decision), reports, settings, audit-logs, notifications |

`/` and `/api/` are intentionally unmatched (Django's 404 page lists every URL pattern while `DEBUG=True`).  There is no Swagger/OpenAPI documentation endpoint; the API contract is `docs/FRONTEND_HANDOFF.md`.

Full contract for the frontend: [`docs/FRONTEND_HANDOFF.md`](docs/FRONTEND_HANDOFF.md). Issues, security findings and status: [`PROJECT_ISSUES_AUDIT.md`](PROJECT_ISSUES_AUDIT.md) (the single audit file).

## Apps

`accounts` (users, auth, admin sign-in code) · `courses` · `access` (who may see which course) · `resources` (PDF upload and validation) · `viewing` (protected rendering, activity) · `payments` (Stripe) · `notifications` · `audit` (append-only log) · `platform_settings` (runtime settings). `core` (shared infrastructure), `reports` and `portal` (API route composers) are plain packages with no models.

**Django admin site:** `http://127.0.0.1:8000/admin/login/` — sign in with an admin account's e-mail and password (`python manage.py createsuperuser` creates one); no OTP/TOTP/JWT is involved. It is separate from the EduVault admin API under `/api/admin/` (password + e-mailed 6-digit code, 30 s, then JWT), is served only on `localhost` / `127.0.0.1`, and lists users in two sections: Admin users and Student users (one `User` table). Details: `PROJECT_ISSUES_AUDIT.md`.
