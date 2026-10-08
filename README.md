# EduVault

A secure educational vault system combining a high-performance Django REST backend with a modern Next.js frontend, providing watermarked document viewing, role-based access control, Stripe payments, and multi-factor authentication.

## Project Structure

```text
Edu_vauilt/
├── backend/                # Django 5 + DRF REST API (authentication, viewing, access, payments)
├── eduvault/               # Next.js 15 (React 19) frontend application
├── .env.example            # Root environment variable template
├── .gitignore              # Repository exclusions (secrets, databases, node_modules)
└── README.md               # Project documentation
```

## First-time Setup

### 1. Backend (Django REST Framework)

```powershell
# Navigate to backend
cd backend

# Create & activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env    # Fill in your local settings (never commit .env)

# Run migrations & start server
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

### 2. Frontend (Next.js)

```powershell
# Navigate to frontend
cd eduvault

# Install dependencies
npm install

# Configure environment
copy .env.example .env.local

# Start development server
npm run dev
```

The frontend will run at `http://localhost:3000` and the API will be available at `http://127.0.0.1:8000/api`.

## Key Features

- **Document Security**: Protected PDF viewing with dynamic watermarking.
- **Two-Factor Authentication**: OTP verification for registration, password reset, and admin 2FA.
- **Role-Based Access**: Separation of student portal and administrator control.
- **Payment Processing**: Integrated Stripe checkout and webhooks.
- **Audit Logging**: Comprehensive append-only audit trail for all sensitive operations.
