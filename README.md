# NORAM Attendance — Multi-Organization Workforce Attendance Management Platform

**Built by NORAM DIGITAL SOLUTIONS**

A commercial, multi-tenant workforce attendance management SaaS platform serving independent organizations (hotels, hospitals, factories, restaurants, schools, offices, retail, construction, NGOs) with strict tenant isolation, Employee ID + PIN attendance terminals, overnight shift calculations, break tracking, leave and attendance correction workflows, and exportable reports.

---

## Technology Stack

- **Frontend**: Next.js (App Router), React, TypeScript, Tailwind CSS, Lucide React, Recharts
- **Backend**: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Argon2id (`argon2-cffi`), JWT (`PyJWT`), OpenPyXL
- **Database**: PostgreSQL 16/18
- **Deployment**: Docker & Docker Compose, environment-based configuration

---

## Quick Start (Local Development)

### 1. Configure Environment Variables
```bash
cp .env.example .env
```
Update `.env` with your PostgreSQL credentials (`DATABASE_URL`) and a strong random `SECRET_KEY`.

### 2. Start PostgreSQL & Create Database
Ensure PostgreSQL is running, then create the database and user:
```sql
CREATE USER attendance_user WITH PASSWORD 'CHANGE_ME_LOCAL_DEV_PASSWORD';
CREATE DATABASE attendance_platform OWNER attendance_user;
```

### 3. Backend Setup & Migrations
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --port 8000
```
- API Docs (Swagger/OpenAPI): `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
- Web Portal: `http://localhost:3000`
- Attendance Kiosk Terminal: `http://localhost:3000/terminal`

---

## Running Automated Tests

### Backend Tests (pytest)
Tests cover authentication, Argon2id hashing, RBAC, **release-blocking multi-tenant isolation**, department manager scoping, overnight shifts (`22:00`–`06:00`), break calculations, duplicate check-in prevention, and auditable attendance corrections.
```bash
cd backend
python -m pytest -v
```

---

## Local Development Seed Credentials
> **Note**: Never use default development passwords in production. Set `PLATFORM_ADMIN_EMAIL` and `PLATFORM_ADMIN_PASSWORD` in `.env`.

When seeded locally with `app/db/seed.py`:
- **Platform Owner**: `platform-admin@noramdigital.com` (password from `PLATFORM_ADMIN_PASSWORD` in `.env`, default `ChangeMeDevAdmin!2026`)
- **Demo Data (Optional)**: Set `SEED_DEMO_DATA=true` in `.env` before running `python -m app.db.seed` to create `[DEMO] Abyssinia Grand Hotel` (`hotel-admin@noramdigital.com` / `DemoHotelAdmin!2026`, sample employee `HTL-001` PIN `1234`).

---

## Docker Deployment (Production)
```bash
cp .env.example .env
# Edit .env with production secrets
docker compose up -d --build
```

---

## Database Backup & Restore

### Backup (pg_dump)
```bash
pg_dump -U attendance_user -h localhost -Fc attendance_platform > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Restore (pg_restore)
```bash
pg_restore -U attendance_user -h localhost -d attendance_platform --clean --if-exists backup_file.dump
```

---

## User Guides

### Organization Onboarding (Platform Owner)
1. Sign in at `/login` as the Platform Owner.
2. Open **Platform Console** (`/platform`) and click **Onboard Organization**.
3. Enter organization details, time zone (e.g., `Africa/Addis_Ababa`), and initial Organization Administrator credentials.

### Administrator Guide
1. Sign in at `/login` with your Organization Administrator account.
2. Configure **Departments**, **Locations**, **Attendance Terminals**, and **Policies** under **Organization Settings** (`/settings`).
3. Copy the generated `ntk_...` terminal token and connect your shared kiosk device at `/terminal`.
4. Register employees individually or via CSV Bulk Import under **Employees** (`/employees`).
5. Create day or overnight shifts under **Shifts & Schedules** (`/shifts`) and assign them to employees or departments.
6. Monitor live attendance on **Overview** (`/dashboard`) and export CSV/Excel reports under **Reports & Exports** (`/reports`).

### Employee Attendance Terminal Guide
1. Open `/terminal` on the registered kiosk tablet or desktop.
2. Enter your **Employee ID** and **PIN**.
3. Press **Check In** when starting your shift or **Check Out** when finishing.
4. Wait for the green confirmation message; the terminal resets automatically for the next employee.
