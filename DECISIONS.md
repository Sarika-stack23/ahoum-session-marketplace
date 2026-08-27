# Engineering Decisions

## Decision 1: Concurrency Strategy — SELECT FOR UPDATE

### Problem
The assignment requires that two users booking the last seat simultaneously must never both succeed. Without explicit concurrency control, a classic time-of-check-to-time-of-use (TOCTOU) race exists:

1. Transaction A reads `confirmed_count = 0`, capacity = 1 → "1 seat available"
2. Transaction B reads `confirmed_count = 0`, capacity = 1 → "1 seat available"
3. Both INSERT a booking → **2 bookings for 1-capacity session**

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **A: Application-level check only** | Simple | Race condition under concurrent load |
| **B: PostgreSQL advisory locks** | Flexible | Manual lock management, easy to misuse |
| **C: `SELECT ... FOR UPDATE`** | Row-level lock, PostgreSQL-native, well-understood | Holds lock for transaction duration |
| **D: Serializable isolation level** | Strongest guarantee | Performance overhead, retry logic needed |
| **E: Optimistic locking (version counter)** | No lock contention | Requires retry loops, more complex |

### Decision
**Option C: `SELECT ... FOR UPDATE`** on the session row inside an atomic transaction.

### Reason
- PostgreSQL-native row-level exclusive lock — the second transaction blocks until the first commits/rollbacks
- Well-understood semantics: the locked row is re-read after the lock is acquired
- Appropriate for this workload: short transactions, low contention expected
- No retry logic needed (unlike serializable isolation or optimistic locking)

### Trade-off
- Lock contention under extreme concurrent load could cause queuing. For a sessions marketplace, this is acceptable — booking contention is inherently sequential.
- Advisory locks would allow finer-grained control but add complexity without benefit at this scale.

### Transaction Boundary
```python
with transaction.atomic():
    session = Session.objects.select_for_update().get(pk=session_id)
    # All checks happen while row is locked
    # Booking is created inside the same transaction
    # Lock is released on COMMIT
```

### Verification
- `bookings/tests/test_concurrency.py`: TransactionTestCase with threading.Barrier
- `scripts/concurrency_test.py`: Standalone script testing 6 scenarios
- Both verify **final database state**, not just application responses

---

## Decision 2: Duplicate Booking Strategy — Application + Database

### Problem
The same user must not have two CONFIRMED bookings for the same session. This must hold even under concurrent requests.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **A: Application check only** | Simple, friendly error messages | Race condition: two concurrent requests can both pass the check |
| **B: Database unique constraint only** | Bulletproof | Raw IntegrityError exposed to user |
| **C: Application check + database constraint** | Friendly errors + safety net | Two layers to maintain |

### Decision
**Option C: Both layers.**

- **Application layer** (inside the locked transaction): `Booking.objects.filter(user=user, session=session, status="CONFIRMED").exists()` — provides friendly "You already have an active booking" error message.
- **Database layer**: PostgreSQL partial unique index: `UNIQUE (user_id, session_id) WHERE status = 'CONFIRMED'` — catches any race condition that slips through.

### Reason
Application validation alone is insufficient because two concurrent transactions can both check "no existing booking" before either creates one. The database constraint is the final safety net.

The partial unique index (instead of a plain unique constraint) allows cancelled bookings — a user can cancel and rebook.

### Trade-off
Two layers means the IntegrityError catch path must produce a clean error, not expose raw PostgreSQL details. This is handled in `services.py`.

### Verification
- `test_duplicate_booking_rejection`: Application-level check
- `test_scenario_f_same_user_concurrent`: Race condition verification
- Database constraint exists in migration

---

## Decision 3: Role Assignment — Controlled Mechanism

### Problem
The assignment specifies User and Creator roles but doesn't define how a user becomes a Creator. An unrestricted "Switch to Creator" toggle would be a security concern — any user could self-promote and gain Creator privileges.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **A: Unrestricted toggle** | Simple UX | Security risk, not specified by assignment |
| **B: Admin-only assignment** | Secure, controlled | Requires admin access |
| **C: Email-based auto-promotion** | Zero-touch for demo | Requires knowing email in advance |
| **D: Registration choice** | User decides at signup | Hard to change later, role confusion |

### Decision
**Options B + C combined:**
1. `CREATOR_EMAILS` environment variable: emails listed here are auto-promoted to Creator on first OAuth login
2. `python manage.py promote_to_creator <username>` management command
3. Django Admin direct edit

### Reason
- Assignment doesn't specify public role promotion → we shouldn't assume it
- Controlled mechanism is demo-safe: evaluator sets their email in `CREATOR_EMAILS`
- Management command covers all other cases
- Role field is read-only in the profile API — cannot be changed by the user

### Trade-off
Slightly more setup friction for the evaluator, but documented clearly in README.

### Verification
- `test_profile_update_cannot_change_role`: Confirms role is not editable via API
- `test_user_cannot_create_session`: Confirms role enforcement on Creator endpoints

---

## Decision 4: Idempotency Keys

### Problem
Network failures, double-clicks, and client retries can cause the same logical booking request to arrive multiple times. Without idempotency, each retry could create a separate booking (or trigger confusing duplicate errors).

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **A: No idempotency** | Simplest | Retries cause confusion |
| **B: Client-generated Idempotency-Key header** | Standard pattern, lightweight | Extra header, storage needed |
| **C: Server-generated dedup based on (user, session)** | No client changes | Already handled by unique constraint |

### Decision
**Option B: Client-generated `Idempotency-Key` header** stored in `IdempotencyRecord` table.

### Reason
- The duplicate booking constraint handles the most common case, but idempotency goes further: it returns the *original response* instead of a "duplicate" error on retry
- Standard HTTP pattern (`Idempotency-Key` header)
- Scoped to `(user, key)` so different users can use the same key string
- If the same key is used for a *different session*, it returns `IDEMPOTENCY_CONFLICT` instead of silently ignoring the mismatch

### Trade-off
- Extra database table and lookup on each booking request
- Keys are never cleaned up (a production system would expire them)

### Verification
- `test_same_idempotency_key_returns_same_booking`: Replay returns original result
- `test_different_session_with_same_key_returns_conflict`: Mismatch detected

---

## Decision 5: PostgreSQL-Specific Concurrency Testing

### Problem
Django's default `TestCase` wraps each test in a transaction and rolls it back. This means `SELECT FOR UPDATE` cannot be tested — the outer transaction holds the lock, and all operations happen on a single connection.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **A: Use `TestCase`** | Fast, auto-rollback | Defeats transaction/lock testing |
| **B: Use `TransactionTestCase`** | Real commits, multi-connection | Slower, no auto-rollback |
| **C: External HTTP test script** | Tests full stack | Requires running server |

### Decision
**Both B and C:**
- `TransactionTestCase` in `test_concurrency.py` for CI-friendly Django test runner
- Standalone `scripts/concurrency_test.py` for full-stack verification

### Reason
`TransactionTestCase` uses real commits, allowing multiple threads to open separate database connections and exercise `SELECT FOR UPDATE` as it would work in production. The standalone script provides an additional verification path that exercises the complete application stack.

### Trade-off
Concurrency tests are slower (no transaction rollback). This is acceptable — correctness of the concurrency guarantee is more important than test speed.

### Verification
Both test suites run 6 scenarios (A-F) and assert final database state.

---

## Decision 6: Why This Architecture Remains a Simple Monolith

### Problem
It's tempting to add Redis (caching), Celery (background tasks), separate microservices, or Kubernetes to demonstrate breadth. But the assignment is a 24-hour task with clear scope.

### Decision
Single Django monolith with PostgreSQL. No Redis, Celery, message queues, or microservices.

### Reason
- **Correctness > complexity**: Every additional component is a failure point
- **The assignment is small**: A monolith handles all requirements cleanly
- **PostgreSQL is sufficient**: `SELECT FOR UPDATE` handles concurrency without Redis distributed locks
- **No background processing needed**: All operations are synchronous and fast
- **A well-designed monolith demonstrates better judgment** than unnecessary distributed architecture

### Trade-off
No real-time seat updates (would need WebSocket + Redis pub/sub). Acceptable per assignment scope.

---

## Invariant Ownership

| Invariant | Database/Transaction | Application | Frontend |
|-----------|---------------------|-------------|----------|
| **Capacity** | SELECT FOR UPDATE + count check (authoritative) | Business validation | Display only |
| **Duplicate booking** | Partial unique index (safety net) | Friendly duplicate check | N/A |
| **Started session** | N/A (not a simple constraint) | Business rule in transaction | Disabled button (UX only) |
| **Ownership** | N/A | Queryset filtering (authoritative) | Hidden UI elements (UX only) |
| **Authentication** | N/A | JWT verification (authoritative) | Token presence (UX only) |

### Differentiator: Booking Integrity & Replay Console
**Problem:** Concurrency invariants (capacity limits, duplicate prevention) are historically difficult to prove to reviewers without requiring them to write custom scripts. Furthermore, idempotency responses (returning cached success for a replay) can appear opaque in a typical UI.
**Solution:** A bespoke **Booking Integrity & Replay Console** has been integrated into the Creator Dashboard. It fetches read-only event logs (`BookingEvent`) and live invariant calculations (`confirmed_bookings <= capacity`) from a dedicated backend endpoint (`GET /api/sessions/<id>/integrity/`).
**Trade-offs:** 
- *Pro*: Explicitly visualizes the `SELECT FOR UPDATE` locking mechanism without exposing sensitive PII. 
- *Con*: Requires exposing a new creator-only read-only endpoint, but it is heavily locked down (ownership checks) and ensures the 24-hour scope is respected (no new models, Redis, or architectural bloat).
