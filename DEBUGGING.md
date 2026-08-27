# Debugging Log

This document records real issues encountered during development, not fabricated examples.

---

## Issue 1: Django `sessions` App Name Collision

### Symptom
When initially creating the Django app for session management, naming it `sessions` caused import conflicts with Django's built-in `django.contrib.sessions` middleware.

### Diagnosis
Django's session middleware (`django.contrib.sessions.middleware.SessionMiddleware`) uses the `sessions` app internally. Creating a project app also named `sessions` caused ambiguous imports:

```
ImportError: cannot import name 'Session' from 'sessions.models'
```

The Python import system resolved `sessions` to Django's built-in session framework instead of our project's session model.

### Root Cause
Python's import resolution doesn't distinguish between `django.contrib.sessions` and a project-level `sessions` app when both are in `INSTALLED_APPS`. The conflict is at the module name level.

### Fix
Renamed the app to `sessions_app` to avoid the collision:

```python
# config/settings.py
INSTALLED_APPS = [
    ...
    "sessions_app",  # Not "sessions"
]
```

Updated all imports, URLs, and references accordingly.

### Verification
- `python manage.py check` passes without import errors
- Django session middleware continues to function for admin
- All session-related tests pass

---

## Issue 2: TransactionTestCase Required for Concurrency Testing

### Symptom
Initial concurrency tests using Django's `TestCase` all passed with exactly 1 booking, even with 10 concurrent threads. This seemed correct but was suspicious — the test might not be exercising real concurrency.

### Diagnosis
Added logging inside the booking service to trace lock acquisition timing. Discovered all 10 threads were executing sequentially, not concurrently. The `SELECT FOR UPDATE` never actually blocked any thread.

Investigation revealed that Django's `TestCase` wraps the entire test in a transaction. All threads share the same database connection through Django's connection pool. Since they're all in the same outer transaction:
1. `SELECT FOR UPDATE` doesn't block because there's no competing transaction
2. All reads see the same (pre-test) state
3. The unique constraint fires immediately on the second INSERT within the same transaction

The test was "passing" but not actually testing concurrent transaction behavior.

### Root Cause
Django's `TestCase` is designed for isolation (rollback after each test), not for testing cross-transaction behavior. `SELECT FOR UPDATE` only blocks between *separate transactions on separate connections*, which `TestCase` doesn't provide.

### Fix
Switched to `TransactionTestCase`:

```python
class ConcurrencyTestCase(TransactionTestCase):
    # Real commits, separate connections per thread
```

Key differences:
- Each thread gets its own database connection
- Operations are committed immediately (no wrapping transaction)
- `SELECT FOR UPDATE` actually blocks competing transactions
- Tests are slower (no rollback cleanup) but correct

### Verification
- With `TransactionTestCase`, thread execution timing shows actual blocking
- Scenario B (capacity=1, 10 attempts): exactly 1 booking, 9 rejections
- Scenario F (same user, 5 attempts): exactly 1 booking confirmed
- Added `threading.Barrier` to synchronize thread start for maximum contention

---

## Issue 3: Frontend OAuth Callback State Validation

### Symptom
During OAuth testing, the callback page occasionally showed "OAuth state mismatch" even after a successful GitHub authorization.

### Diagnosis
The OAuth state parameter was being stored in `localStorage`. When the user had multiple tabs open or when the browser restored a previous session, the state could be stale or from a different OAuth attempt.

### Root Cause
`localStorage` persists across tabs and sessions. If a user:
1. Clicks "Sign in" (state stored in localStorage)
2. Opens a new tab, clicks "Sign in" again (state overwritten)
3. Completes OAuth in the first tab → state mismatch

### Fix
Changed from `localStorage` to `sessionStorage` for the OAuth state parameter:

```javascript
// Before (persists across tabs):
localStorage.setItem('oauth_state', state);

// After (tab-scoped):
sessionStorage.setItem('oauth_state', state);
```

`sessionStorage` is scoped to the tab/window, so each OAuth attempt has its own isolated state.

### Verification
- Opened multiple tabs, initiated OAuth in each — no cross-tab state leakage
- Single tab flow works correctly
- State mismatch correctly rejected when state is tampered with
