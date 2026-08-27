#!/bin/bash
# ==========================================================
# Sessions Marketplace — Verification Script
# ==========================================================
# Runs all critical checks in sequence.
# Exit code 0 = all passed, non-zero = failure detected.
#
# Usage:
#   docker compose exec backend bash /app/scripts/verify.sh
# ==========================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

check() {
    local name="$1"
    shift
    printf "  [%d] %-35s" $((PASS_COUNT + FAIL_COUNT + 1)) "$name"
    if "$@" > /tmp/verify_output.txt 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "${RED}FAIL${NC}"
        echo "      Output:"
        head -20 /tmp/verify_output.txt | sed 's/^/      /'
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo ""
echo "=========================================="
echo "  SESSIONS MARKETPLACE VERIFICATION"
echo "=========================================="
echo ""

# 1. Backend tests — authentication
check "Auth tests" python manage.py test accounts.tests.test_auth --verbosity=0 --no-input

# 2. Session CRUD tests
check "Session tests" python manage.py test sessions_app.tests.test_sessions --verbosity=0 --no-input

# 3. Booking edge cases
check "Booking edge cases" python manage.py test bookings.tests.test_bookings --verbosity=0 --no-input

# 4. Concurrency tests (TransactionTestCase)
check "Concurrency tests" python manage.py test bookings.tests.test_concurrency --verbosity=0 --no-input

# 5. Concurrency script
check "Concurrency script" python /app/scripts/concurrency_test.py

# 6. Health endpoint
check "Health endpoint" python -c "
from django.test.utils import setup_test_environment
import django; django.setup()
from django.test import RequestFactory
from health.views import health
rf = RequestFactory()
r = rf.get('/api/health/')
resp = health(r)
assert resp.status_code == 200, f'Expected 200, got {resp.status_code}'
"

# 7. Configuration check
check "No secrets in repo" bash -c '! grep -r "CHANGE_ME\|real_secret\|actual_password" --include="*.py" --include="*.yml" --include="*.yaml" . 2>/dev/null | grep -v ".env.example" | grep -v "node_modules" | grep -q .'

echo ""
echo "=========================================="
printf "  RESULT: ${GREEN}%d PASSED${NC}" "$PASS_COUNT"
if [ "$FAIL_COUNT" -gt 0 ]; then
    printf ", ${RED}%d FAILED${NC}" "$FAIL_COUNT"
fi
echo ""
echo "=========================================="
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi
exit 0
