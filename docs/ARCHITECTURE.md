# Technical Architecture — NORAM Attendance Platform

## 1. Multi-Tenant SaaS Isolation Model
Every organization-owned table (`employees`, `departments`, `locations`, `positions`, `shifts`, `shift_assignments`, `attendance_terminals`, `attendance_sessions`, `attendance_events`, `break_records`, `attendance_summaries`, `leave_types`, `leave_requests`, `attendance_correction_requests`, `notifications`) includes a non-nullable `organization_id` foreign key.

- **Server-Side Context Derivation**: `get_current_auth` and `require_org_member` in `backend/app/core/dependencies.py` derive `organization_id` exclusively from the authenticated user's database record and JWT claims. Client-supplied organization IDs are never trusted for tenant-scoped queries.
- **Department Manager Scoping**: Users with `department_manager` role are restricted to `user.assigned_department_ids` across employee directories, dashboard metrics, attendance sessions, leave approvals, correction approvals, and report exports.
- **Terminal Authentication**: Kiosk terminals authenticate via `X-Terminal-Token` (hashed with SHA-256 in `attendance_terminals.token_hash`) and are bound to a single `organization_id` and optional `location_id`.

## 2. Security & Cryptography
- **Password & PIN Hashing**: Argon2id (`argon2-cffi`, `time_cost=3`, `memory_cost=65536`, `parallelism=4`).
- **Authentication**: Short-lived JWT access tokens + rotating SHA-256-hashed refresh tokens (`refresh_tokens`).
- **Rate Limiting & Lockout**: In-memory sliding-window rate limiting on `/auth/login` and terminal PIN attempts, plus persistent `failed_attempts` / `locked_until` lockout on `employee_credentials`.
- **Immutable Audit Trail**: `audit_logs` records logins, failed logins, onboarding, employee changes, shift updates, terminal registration, and correction/leave approvals without exposing passwords, PINs, or tokens.

## 3. Attendance & Overnight Shift Engine
- **Authoritative Server Clock**: All timestamps are recorded in UTC using server time and converted to `organization.timezone` (e.g., `Africa/Addis_Ababa`) to determine `work_date`.
- **Overnight Shifts**: Shifts where `crosses_midnight=True` (e.g., `22:00` to `06:00`) evaluate check-ins in the early morning against the previous day's active shift window, keeping the entire overnight shift in a single `AttendanceSession`.
- **Duration Separation**: `gross_minutes`, `break_minutes`, `net_minutes`, and `overtime_minutes` are stored separately; overtime approval is governed by `shift_policies.overtime_requires_approval` and `organization_settings.overtime_requires_approval`.
