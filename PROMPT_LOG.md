# AI Prompt Log

AI tools were used throughout this project. This document records material AI interactions, what was accepted/rejected, and specific corrections made.

**Tools used:** Antigravity (Claude) — used as a pair programming assistant for code generation, architecture review, and test design.

---

## Prompt 1: Project Scaffolding

**Date:** 2026-08-27
**Goal:** Generate Django + React + Docker project structure
**Prompt:** "Create the foundation for a sessions marketplace with Django backend, React/Vite frontend, PostgreSQL, and Nginx in Docker Compose"

**AI approach:** Generated complete project scaffolding including Docker Compose, Nginx config, Django settings, and React app structure.

**What I accepted:**
- Docker Compose structure with 4 containers and persistent volume
- Django settings organization with environment variables
- Nginx reverse proxy configuration
- Vite configuration with API proxy

**What I changed:**
- AI initially named the Django session app `sessions`, which conflicts with Django's built-in sessions framework. Changed to `sessions_app`.
- AI used `FROM python:3.11` instead of `python:3.11-slim` — changed to slim for smaller image size.

**Verification:** Docker configuration reviewed for correct service dependencies, volume mounting, and port mapping.

---

## Prompt 2: Booking Service with Concurrency Safety

**Date:** 2026-08-27
**Goal:** Implement transaction-safe booking with SELECT FOR UPDATE
**Prompt:** "Implement the booking service that prevents overbooking under concurrent requests using PostgreSQL row locking"

**AI approach:** Generated a booking service using `transaction.atomic()` and `select_for_update()`.

**What I accepted:**
- Core transaction structure with `SELECT FOR UPDATE`
- Ordered invariant checks (start_time → duplicate → capacity)
- IntegrityError catch as safety net

**What I rejected/changed:**
- AI initially placed the idempotency check *inside* the transaction. Moved it *before* the transaction — if an idempotency record exists, we can return immediately without acquiring the row lock. This reduces unnecessary lock contention.
- AI initially didn't create BookingEvent records for rejected attempts. Added event creation for all rejection types (capacity, duplicate, started) for audit trail completeness.

**Verification:** Reviewed the full transaction flow manually. Confirmed SELECT FOR UPDATE is inside the atomic block. Confirmed IntegrityError catch produces clean error, not raw SQL exposure.

---

## Prompt 3: Concurrency Tests

**Date:** 2026-08-27
**Goal:** Create real concurrency tests that exercise PostgreSQL locking
**Prompt:** "Create concurrency tests for the booking system that use genuinely concurrent requests, not sequential loops"

**AI approach:** Generated tests using Django's `TestCase` with `threading.Thread`.

**What I rejected:**
- **AI used `TestCase` instead of `TransactionTestCase`.** This is a critical error. Django's `TestCase` wraps everything in a single transaction, which means `SELECT FOR UPDATE` doesn't actually block — all threads share the same transaction context. The tests would "pass" but not test real concurrency.

**What I changed:**
- Switched to `TransactionTestCase` which uses real committed transactions
- Added `threading.Barrier` to synchronize thread start (AI used simple thread start which allows sequential execution before all threads are ready)
- Added explicit final database state assertions (`Booking.objects.filter(...).count()`) instead of just counting application-level return values

**Verification:** Added timing logs to confirm threads actually block on the row lock. Confirmed the test fails if `select_for_update()` is removed from the service.

---

## Prompt 4: OAuth Flow

**Date:** 2026-08-27
**Goal:** Implement GitHub OAuth with proper error handling
**Prompt:** "Implement GitHub OAuth callback that handles cancellation, failure, and success cases"

**AI approach:** Generated OAuth callback with code exchange and user creation.

**What I accepted:**
- Core GitHub API integration (token exchange, user profile fetch)
- Email fallback to `/user/emails` endpoint when email is not public

**What I changed:**
- AI stored OAuth state in `localStorage`. Changed to `sessionStorage` because localStorage persists across tabs, causing state mismatches in multi-tab scenarios.
- AI didn't validate the `state` parameter on callback. Added state validation to prevent CSRF attacks on the OAuth flow.

**Verification:** Tested OAuth flow manually including cancellation (verify `error=access_denied` is handled) and state mismatch rejection.

---

## Prompt 5: Role System Design

**Date:** 2026-08-27
**Goal:** Design a controlled role assignment mechanism
**Prompt:** "How should users be assigned the Creator role?"

**AI approach:** Initially suggested an unrestricted "Switch to Creator" toggle on the profile page.

**What I rejected:**
- The toggle approach allows any user to self-promote to Creator, which is a security concern. The assignment doesn't specify public role promotion.

**What I changed:**
- Implemented three controlled mechanisms:
  1. `CREATOR_EMAILS` env var for auto-promotion on first login
  2. Management command for admin use
  3. Django Admin for direct editing
- Made the `role` field read-only in the profile API serializer

**Verification:** Test `test_profile_update_cannot_change_role` confirms role cannot be changed via API.

---

## Prompt 6: Frontend Error Handling

**Date:** 2026-08-27
**Goal:** Handle all booking failure states in the UI
**Prompt:** "Create frontend components that handle all booking error cases without blaming the user for race conditions"

**AI approach:** Generated error handling for common cases.

**What I changed:**
- AI initially showed generic "Booking failed" for all errors. Changed to specific messages per error code (SESSION_FULL, DUPLICATE_BOOKING, SESSION_STARTED, etc.)
- AI didn't include the request ID in error displays. Added request ID display for debugging.
- AI's "session full" message said "try again later" which is misleading for a capacity issue. Changed to "Another booking completed before your request" which correctly explains the race condition.

**Verification:** Reviewed all error code mappings in SessionDetail.jsx against the backend error codes in services.py.

---

## What AI Got Wrong / What I Corrected

### Correction 1: TestCase vs TransactionTestCase for Concurrency

**AI proposed:** Using Django's `TestCase` for concurrency tests.

**Why it's wrong:** `TestCase` wraps the entire test in a single transaction. `SELECT FOR UPDATE` doesn't block within the same transaction — it only blocks between separate transactions. The concurrency test would "pass" but provide zero confidence about real-world concurrent behavior.

**My correction:** Switched to `TransactionTestCase` which commits transactions independently, allowing multiple threads to actually contend for the row lock. Added `threading.Barrier` for synchronized concurrent execution.

**How I verified:** Added timing instrumentation to confirm threads actually block on `SELECT FOR UPDATE`. Confirmed removing the lock causes the test to fail with overbooking.

### Correction 2: Unrestricted Role Self-Promotion

**AI proposed:** A "Switch to Creator" toggle on the profile page that directly updates the user's role.

**Why it's wrong:** The assignment doesn't specify public role promotion. An unrestricted toggle means any authenticated user can self-promote to Creator, bypassing any intended access control. This is both a security issue and an incorrect interpretation of the requirements.

**My correction:** Implemented controlled assignment via environment variable (CREATOR_EMAILS), management command, and Django Admin. Made the role field read-only in the profile serializer.

**How I verified:** Test confirms role field is ignored in profile PATCH requests. Test confirms User role is enforced on Creator-only endpoints regardless of frontend state.

### Correction 3: Idempotency Check Placement

**AI proposed:** Checking idempotency keys inside the `transaction.atomic()` block, after acquiring the `SELECT FOR UPDATE` lock.

**Why it's wrong:** If an idempotency record exists, we can return the cached response immediately without touching the session row. Placing the check inside the transaction means we acquire an unnecessary row lock for replayed requests, increasing contention.

**My correction:** Moved the idempotency check before the transaction block. Only new (non-replayed) requests enter the transaction and acquire the lock.

**How I verified:** Reviewed the code flow. Confirmed that idempotency replays return without executing the transaction block. This is a performance consideration, not a correctness one — but it demonstrates understanding of lock contention.
