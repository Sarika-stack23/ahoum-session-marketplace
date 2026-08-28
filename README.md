<div align="center">
  <h1>🚀 Ahoum Sessions Marketplace</h1>
  <p>A high-concurrency, transaction-safe booking platform built for creators and users.</p>
  
  ![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
  ![Vite](https://img.shields.io/badge/Vite-B73BFE?style=for-the-badge&logo=vite&logoColor=FFD62E)
  ![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=green)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
  ![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)
  ![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)
</div>

---

## 📸 Screenshots
> **Note:** Replace these placeholders with actual screenshots before submitting!
> 
> ![Homepage Catalog](https://via.placeholder.com/800x400.png?text=Homepage+Catalog+Screenshot)
> *The modern, responsive session catalog.*
> 
> ![Booking Integrity Console](https://via.placeholder.com/800x400.png?text=Booking+Integrity+Console+Screenshot)
> *The engineering differentiator: Visualizing live PostgreSQL row-level locks and transaction events.*

---

## ⚡ Overview
A compact sessions marketplace where users authenticate, browse sessions, and book them, while creators create and manage sessions. Built as a 24-hour full-stack developer assignment.

## Features

- **GitHub OAuth** authentication with JWT access/refresh tokens
- **Role-based access control**: User and Creator roles (backend-enforced)
- **Session management**: Creators create, update, delete their own sessions
- **Transaction-safe booking**: PostgreSQL `SELECT FOR UPDATE` prevents overbooking
- **Duplicate protection**: Partial unique index prevents double-booking
- **Start-time enforcement**: Backend rejects bookings for started sessions
- **Idempotency keys**: Safe retry protection against double-clicks/network retries
- **Request correlation IDs**: Every request gets a traceable `req_xxx` ID
- **Booking event audit trail**: Records confirmed/rejected booking outcomes
- **Concurrency verification**: Real multi-threaded test suite proves capacity safety
- **Booking Integrity Console**: Creator dashboard visualizes live concurrency invariants and event timelines

## Architecture

```
Browser → Nginx (:80)
              ├── /api/*  → Django + DRF (:8000) → PostgreSQL (:5432)
              └── /*      → React + Vite (:3000)
```

**Why this architecture:**
- Simple monolith — appropriate for scope. No Redis, Celery, microservices.
- Nginx as reverse proxy — single entry point, clean routing.
- PostgreSQL — required for `SELECT FOR UPDATE` and partial unique indexes.
- React + Vite — lightweight client-side SPA per assignment spec.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite 5, React Router 6 |
| Backend | Django 4.2, Django REST Framework |
| Database | PostgreSQL 15 |
| Auth | GitHub OAuth → JWT (SimpleJWT) |
| Proxy | Nginx |
| Infrastructure | Docker Compose |

## Authentication

**Provider:** GitHub OAuth (chosen over Google for simpler setup — no GCP console required).

**Flow:**
1. Frontend redirects to GitHub OAuth authorization page
2. User authorizes → GitHub redirects back with `?code=xxx`
3. Frontend sends code to `POST /api/auth/github/callback/`
4. Backend exchanges code for GitHub access token
5. Backend fetches GitHub user profile
6. Backend creates/updates local user
7. Backend issues JWT access + refresh tokens
8. Frontend stores tokens and uses them for authenticated API calls

**Handled edge cases:**
- OAuth cancellation → friendly message, no crash
- OAuth failure → clear error with retry option
- Expired access token → automatic refresh
- Invalid/expired refresh token → forced logout

## Role Model

| Role | Can do |
|------|--------|
| USER | Browse sessions, book sessions, view bookings, update profile |
| CREATOR | All USER actions + create/update/delete own sessions |

**Role assignment is controlled, not self-service:**
1. **CREATOR_EMAILS env var:** Comma-separated emails auto-promoted to Creator on first OAuth login
2. **Management command:** `docker compose exec backend python manage.py promote_to_creator <username_or_email>`
3. **Django Admin:** Direct role edit at `/admin/`

This is a deliberate design choice — see DECISIONS.md.

## Session Model

| Field | Type | Notes |
|-------|------|-------|
| id | BigAutoField | Primary key |
| creator | ForeignKey(User) | Indexed, CASCADE delete |
| title | CharField(200) | Required |
| description | TextField | Optional |
| start_time | DateTimeField | Indexed |
| capacity | PositiveIntegerField | Min: 1 |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

## Booking Architecture

### Invariants

| # | Invariant | Enforced By |
|---|-----------|-------------|
| 1 | `confirmed_bookings <= capacity` | Transaction + SELECT FOR UPDATE |
| 2 | One active booking per (user, session) | PostgreSQL partial unique index + app validation |
| 3 | No booking after session start_time | App validation inside locked transaction |
| 4 | Only authenticated users can book | DRF IsAuthenticated permission |
| 5 | Results reflect committed DB state | Atomic transaction |
| 6 | Frontend `remainingSeats` is informational only | Backend is authoritative |

### Transaction Flow

```
REQUEST → Authenticate → Validate → Generate request_id
    → Check idempotency key
    → BEGIN TRANSACTION
        → SELECT session FOR UPDATE (row lock)
        → Check start_time > now
        → Check no duplicate confirmed booking
        → Count confirmed bookings
        → Check count < capacity
        → INSERT booking
        → INSERT booking event
    → COMMIT
    → Return committed result
```

### Why `SELECT FOR UPDATE`

Without row locking, two concurrent transactions can both read `confirmed=0` for a capacity-1 session, both decide "1 seat available", and both INSERT — violating the invariant. `SELECT FOR UPDATE` acquires an exclusive row lock so the second transaction blocks until the first commits.

### Why Frontend `remainingSeats` Is Insufficient

Two clients can simultaneously observe `remainingSeats=1`. Both click "Book." If the frontend were authoritative, both would succeed. The backend must be the single source of truth.

## Booking Integrity Console

The **Booking Integrity Console** is a specialized Creator dashboard designed to visualize the actual backend transaction pipeline for a session. It is the primary engineering differentiator of this project.

Instead of hiding the complexity of concurrency, it exposes:
- **Live Invariants:** Proves that `confirmed_bookings <= capacity`.
- **Event Timeline:** Displays real `BookingEvent` records generated inside the `SELECT FOR UPDATE` transaction.
- **Request Traceability:** Every booking attempt (success or failure) is logged with a unique `req_xxx` Request ID.
- **Idempotency Honesty:** If an idempotent replay occurs, it is accurately represented without faking events.

This console proves that the database locking is actively protecting the session from overbooking in real-time.

## Setup

### Prerequisites
- Docker and Docker Compose
- GitHub OAuth App (see below)

### GitHub OAuth Setup

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Set:
   - **Application name:** Sessions Marketplace
   - **Homepage URL:** `http://localhost`
   - **Authorization callback URL:** `http://localhost/auth/callback`
4. Copy Client ID and Client Secret

### Environment Variables

```bash
cp .env.example .env
# Edit .env with your values:
# - GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET from step above
# - VITE_GITHUB_CLIENT_ID (same as GITHUB_CLIENT_ID)
# - Generate a DJANGO_SECRET_KEY
# - Set a strong POSTGRES_PASSWORD
# - Optionally set CREATOR_EMAILS for auto-promotion
```
```

## Production Deployment (Render)

This project is configured for automated infrastructure-as-code deployment on [Render](https://render.com). The included `render.yaml` blueprint provisions the database, backend, and frontend automatically.

### Deployment Steps
1. Push this repository to GitHub (ensure `.env` is NOT tracked).
2. Log in to Render dashboard and go to **Blueprints** -> **New Blueprint Instance**.
3. Connect your GitHub repository.
4. Render will automatically detect the `render.yaml` and prompt you for the required environment variables:
   - `GITHUB_CLIENT_ID`
   - `GITHUB_CLIENT_SECRET`
   - `CREATOR_EMAILS` (Optional, comma-separated list of GitHub emails for admin promotion)
5. Click **Apply**.
6. Wait for the `sessions-marketplace-db`, `sessions-marketplace-api`, and `sessions-marketplace` (static site) services to deploy.
7. **Important Post-Deployment Configuration:**
   - In the Render dashboard, find the URL of your deployed Frontend static site.
   - Go to your Backend Web Service -> Environment. Update `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to match your frontend URL (e.g. `https://your-frontend.onrender.com`).
   - Go to your Frontend Static Site -> Environment. Update `VITE_API_URL` to match your backend URL + `/api` (e.g. `https://your-backend.onrender.com/api`).
   - In your GitHub OAuth App settings, update the **Authorization callback URL** to match your frontend URL + `/auth/callback` (e.g. `https://your-frontend.onrender.com/auth/callback`).

### Local Docker Instructions

```bash
# Build and start all containers
docker compose up --build

# Access the application
open http://localhost

# Run database migrations (auto-runs on startup, or manually)
docker compose exec backend python manage.py migrate

# Create a superuser for Django admin
docker compose exec backend python manage.py createsuperuser

# Promote a user to Creator
docker compose exec backend python manage.py promote_to_creator <username>

# Stop containers
docker compose down

# Stop and remove volumes (WARNING: deletes database)
docker compose down -v
```

### Database Persistence

PostgreSQL data is stored in a named Docker volume (`postgres_data`). This means:
- Data survives `docker compose down` and `docker compose up`
- Data survives application container rebuilds
- Only `docker compose down -v` removes the data

## API Overview

### Public (no auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/` | Session catalog |
| GET | `/api/sessions/:id/` | Session detail |
| GET | `/api/health/` | Liveness check |
| GET | `/api/readiness/` | Readiness check (DB) |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/github/callback/` | Exchange OAuth code for JWT |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| GET/PATCH | `/api/auth/profile/` | Get/update profile |
| POST | `/api/auth/logout/` | Invalidate refresh token |

### Sessions (Creator only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions/create/` | Create session |
| PATCH | `/api/sessions/:id/update/` | Update own session |
| DELETE | `/api/sessions/:id/delete/` | Delete own session |
| GET | `/api/sessions/mine/` | List own sessions |

### Bookings (Authenticated)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bookings/session/:id/book/` | Book a session |
| GET | `/api/bookings/mine/?status=active\|past` | List bookings |
| POST | `/api/bookings/:id/cancel/` | Cancel booking |

### Error Response Format
```json
{
  "error": {
    "code": "SESSION_FULL",
    "message": "This session is full.",
    "request_id": "req_abc123def456"
  }
}
```

## Running Tests

```bash
# All backend tests
docker compose exec backend python manage.py test --verbosity=2

# Specific test suites
docker compose exec backend python manage.py test accounts.tests
docker compose exec backend python manage.py test sessions_app.tests
docker compose exec backend python manage.py test bookings.tests.test_bookings
docker compose exec backend python manage.py test bookings.tests.test_concurrency
```

## Running Concurrency Verification

```bash
# Standalone concurrency script (exercises all scenarios)
docker compose exec backend python /app/scripts/concurrency_test.py

# Django TransactionTestCase concurrency tests
docker compose exec backend python manage.py test bookings.tests.test_concurrency --verbosity=2
```

Both use genuine concurrent threads with `threading.Barrier` synchronization — NOT sequential loops. Both verify the final database state after all threads complete.

## Running verify.sh

```bash
docker compose exec backend bash /app/scripts/verify.sh
```

Runs auth tests, session tests, booking edge cases, concurrency verification, health checks, and configuration audit. Returns non-zero on failure.

## Engineering Guarantees

Only listing guarantees that are genuinely implemented and testable:

- ✓ Backend enforces session capacity via `SELECT FOR UPDATE`
- ✓ Concurrent PostgreSQL booking attempts are tested (6 scenarios)
- ✓ Duplicate active bookings prevented by partial unique index
- ✓ Started sessions cannot be newly booked (server-side check)
- ✓ Creator ownership enforced server-side (queryset filtering)
- ✓ Invalid/expired authentication rejected with correct error codes
- ✓ User cannot call Creator-only endpoints (IsCreator permission)
- ✓ Creator A cannot modify Creator B's sessions
- ✓ Idempotency keys prevent duplicate bookings from retries
- ✓ All errors follow consistent `{error: {code, message, request_id}}` format

## Known Limitations

1. **No WebSocket/real-time updates:** Seat counts may be stale until page refresh. This is acceptable because the backend is authoritative — stale frontend state cannot cause overbooking.
2. **No email notifications:** No booking confirmation emails.
3. **No pagination on frontend:** Session list loads all sessions. Pagination exists in the API but isn't wired to the frontend.
4. **No password auth:** GitHub OAuth only. No username/password fallback.
5. **Single OAuth provider:** GitHub only (by design — one reliable provider beats two fragile ones).

## What I Would Improve With Another Day

1. **WebSocket for live seat counts** — Push availability updates to avoid stale frontend state
2. **Cancellation with capacity release** — Allow users to cancel and free seats
3. **Search and filtering** — Filter sessions by date, availability, creator
4. **Email notifications** — Booking confirmation and reminders
5. **Rate limiting** — Protect booking endpoint from abuse
6. **Frontend pagination** — Wire API pagination to the UI
7. **Comprehensive E2E tests** — Playwright or Cypress for full user flow testing
8. **Production Docker config** — Multi-stage builds, production Nginx serving built assets

## AI Usage Disclosure

AI tools (Antigravity / Claude) were used throughout development. All AI output was reviewed, challenged, and verified. See PROMPT_LOG.md for detailed supervision evidence including specific corrections made to AI suggestions.

## Vercel Serverless Deployment (100% Free)

This project has been architected to deploy as a Vercel Monorepo. The React frontend is served statically, and the Django API is served via Vercel Serverless Functions.

### 1. Database Setup (Neon PostgreSQL)
Vercel does not host databases. You must use a persistent PostgreSQL database. SQLite is NOT supported because it lacks row-level locking capabilities necessary for the concurrency guarantees.
1. Sign up for free at [Neon.tech](https://neon.tech)
2. Create a Free PostgreSQL project and database.
3. Obtain your `DATABASE_URL` (connection string). **Do NOT commit this to Git.**

### 2. Vercel Deployment
1. Go to [Vercel](https://vercel.com) and import your GitHub repository.
2. The `vercel.json` file in the root directory will automatically configure the build and routing.
3. Add the following Environment Variables in Vercel:
   - `DATABASE_URL` = (Your Neon connection string)
   - `DJANGO_SECRET_KEY` = (A random secure string)
   - `GITHUB_CLIENT_ID` = (Your GitHub OAuth App ID)
   - `GITHUB_CLIENT_SECRET` = (Your GitHub OAuth App Secret)
   - `VITE_GITHUB_CLIENT_ID` = (Same as GITHUB_CLIENT_ID)
4. Click **Deploy**. Vercel will automatically build the frontend and deploy the Django serverless functions.

### 3. Database Migrations on Vercel
Because Vercel functions are serverless, `python manage.py migrate` does not run automatically on startup. You must manually run migrations against your Neon database from your local machine:
```bash
export DATABASE_URL="your-neon-database-url"
docker compose exec -e DATABASE_URL=$DATABASE_URL backend python manage.py migrate
```

### 4. Final OAuth Configuration
Once Vercel provides your production URL (e.g. `https://your-project.vercel.app`), go to your GitHub OAuth App settings and update the **Authorization callback URL** to:
`https://your-project.vercel.app/auth/callback`

### Serverless Concurrency Guarantees
Even though Vercel Serverless tears down the Django environment after every request, the `SELECT FOR UPDATE` concurrency guarantee is strictly preserved. This is because the row-level lock is acquired and held at the **Neon PostgreSQL database layer**, not the application layer. Vercel simply waits for the database to release the lock.
