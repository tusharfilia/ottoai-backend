#!/bin/bash

# OttoAI Backend - Foundations Verification Pack
# Comprehensive verification of all foundational features

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
VERIFICATION_RESULTS=()

# Helper functions
log_header() {
    echo -e "\n${BOLD}${BLUE}================================================${NC}"
    echo -e "${BOLD}${BLUE} $1${NC}"
    echo -e "${BOLD}${BLUE}================================================${NC}"
}

log_test() {
    echo -e "\n${YELLOW}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_TESTS++))
    VERIFICATION_RESULTS+=("✅ $1")
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_TESTS++))
    VERIFICATION_RESULTS+=("❌ $1")
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

run_test() {
    local test_name="$1"
    local command="$2"
    
    log_test "$test_name"
    ((TOTAL_TESTS++))
    
    if eval "$command" >/dev/null 2>&1; then
        log_pass "$test_name"
        return 0
    else
        log_fail "$test_name"
        return 1
    fi
}

# Test 1: Secrets Hygiene
test_secrets_hygiene() {
    log_header "SECRETS HYGIENE VERIFICATION"
    
    run_test "No hardcoded secrets in codebase" "make verify:secrets"
    
    # Additional secret checks
    if run_test "Environment configuration validation" "python -c 'from app.config import settings; print(\"Config loaded successfully\")'"; then
        log_info "Configuration validation passed"
    fi
}

# Test 2: CORS & Tenant Context
test_cors_tenant() {
    log_header "CORS & TENANT CONTEXT VERIFICATION"
    
    run_test "CORS middleware configuration" "pytest -q tests/test_cors_tenant.py::TestCORSMiddleware"
    run_test "Tenant context validation" "pytest -q tests/test_cors_tenant.py::TestTenantContext"
    run_test "Database scoping enforcement" "pytest -q tests/test_cors_tenant.py::TestDatabaseScoping"
}

# Test 3: Rate Limiting
test_rate_limiting() {
    log_header "RATE LIMITING VERIFICATION"
    
    run_test "Rate limiting middleware" "pytest -q tests/test_rate_limiting.py::TestRateLimitingMiddleware"
    run_test "Per-user rate limits" "pytest -q tests/test_rate_limiting.py::TestUserRateLimiting"
    run_test "Per-tenant rate limits" "pytest -q tests/test_rate_limiting.py::TestTenantRateLimiting"
    run_test "Redis connectivity" "pytest -q tests/test_rate_limiting.py::TestRedisIntegration"
}

# Test 4: Webhook Idempotency
test_webhook_idempotency() {
    log_header "WEBHOOK IDEMPOTENCY VERIFICATION"
    
    run_test "Idempotency service logic" "pytest -q tests/test_idempotency.py::TestIdempotencyService"
    run_test "CallRail webhook idempotency" "pytest -q tests/test_idempotency.py::TestCallRailIdempotency"
    run_test "Twilio webhook idempotency" "pytest -q tests/test_idempotency.py::TestTwilioIdempotency"
    run_test "Clerk webhook idempotency" "pytest -q tests/test_idempotency.py::TestClerkIdempotency"
    run_test "Bland AI webhook idempotency" "pytest -q tests/test_idempotency.py::TestBlandIdempotency"
    run_test "Database migration applied" "alembic current | grep -q '001_add_idempotency_keys'"
}

# Test 5: Observability
test_observability() {
    log_header "OBSERVABILITY VERIFICATION"
    
    run_test "Structured logging format" "pytest -q tests/test_logging_tracing.py::TestLogging"
    run_test "Distributed tracing setup" "pytest -q tests/test_logging_tracing.py::TestTracing"
    run_test "RFC-7807 error handling" "pytest -q tests/test_logging_tracing.py::TestErrorHandling"
    run_test "HTTP metrics collection" "pytest -q tests/test_metrics.py::TestHTTPMetrics"
    run_test "Worker task metrics" "pytest -q tests/test_metrics.py::TestWorkerMetrics"
    run_test "Webhook processing metrics" "pytest -q tests/test_metrics.py::TestWebhookMetrics"
    run_test "Prometheus metrics endpoint" "pytest -q tests/test_metrics.py::TestMetricsEndpoint"
}

# Test 6: Real-Time Transport
test_realtime_transport() {
    log_header "REAL-TIME TRANSPORT VERIFICATION"
    
    run_test "WebSocket authentication" "pytest -q tests/test_ws_basic.py::TestWebSocketAuthentication"
    run_test "Channel validation" "pytest -q tests/test_ws_basic.py::TestWebSocketChannelValidation"
    run_test "WebSocket hub management" "pytest -q tests/test_ws_basic.py::TestWebSocketHub"
    run_test "Event bus functionality" "pytest -q tests/test_ws_basic.py::TestEventBus"
    run_test "Event emission" "pytest -q tests/test_ws_events.py::TestEventEmission"
    run_test "Message envelope format" "pytest -q tests/test_ws_events.py::TestMessageEnvelope"
    run_test "Event catalog coverage" "pytest -q tests/test_ws_events.py::TestEventCatalog"
}

# Test 7: Production Readiness
test_production_readiness() {
    log_header "PRODUCTION READINESS VERIFICATION"
    
    run_test "Health endpoint functionality" "pytest -q tests/test_readiness.py::TestHealthEndpoint"
    run_test "Readiness checks (all components)" "pytest -q tests/test_readiness.py::TestReadinessEndpoint"
    run_test "Worker heartbeat endpoint" "pytest -q tests/test_readiness.py::TestWorkerHeartbeat"
    run_test "Redis configuration validation" "python -c 'from app.config import settings; assert settings.REDIS_URL or settings.UPSTASH_REDIS_URL, \"Redis URL required\"'"
    run_test "Celery configuration validation" "python -c 'from app.services.celery_tasks import celery_app; print(\"Celery configured\")'"
}

# Test 8: Integration Tests
test_integration() {
    log_header "INTEGRATION VERIFICATION"
    
    # Test that all components work together
    run_test "Database + Redis integration" "pytest -q tests/test_readiness.py::TestReadinessIntegration"
    run_test "Observability + WebSocket integration" "python -c 'from app.obs.metrics import record_ws_connection; record_ws_connection(\"test\", 1); print(\"Integration OK\")'"
    run_test "Event bus + metrics integration" "python -c 'from app.realtime.bus import emit; emit(\"test.event\", {\"test\": True}, tenant_id=\"test\"); print(\"Event bus OK\")'"
}

# Main verification function
main() {
    log_header "OTTOAI BACKEND FOUNDATIONS VERIFICATION PACK"
    log_info "Comprehensive verification of all foundational features"
    log_info "Started at: $(date)"
    
    # Check if we're in the right directory
    if [ ! -f "app/main.py" ]; then
        log_fail "Must be run from ottoai-backend/services/dashboard directory"
        exit 1
    fi
    
    # Check if virtual environment is active
    if [ -z "$VIRTUAL_ENV" ]; then
        log_warn "No virtual environment detected - some tests may fail"
    fi
    
    # Run all verification tests
    test_secrets_hygiene
    test_cors_tenant
    test_rate_limiting
    test_webhook_idempotency
    test_observability
    test_realtime_transport
    test_production_readiness
    test_integration
    
    # Summary
    log_header "VERIFICATION SUMMARY"
    
    echo -e "\n${BOLD}Test Results:${NC}"
    echo -e "  Total Tests: ${TOTAL_TESTS}"
    echo -e "  Passed: ${GREEN}${PASSED_TESTS}${NC}"
    echo -e "  Failed: ${RED}${FAILED_TESTS}${NC}"
    
    echo -e "\n${BOLD}Detailed Results:${NC}"
    for result in "${VERIFICATION_RESULTS[@]}"; do
        echo -e "  $result"
    done
    
    # Calculate success rate
    if [ $TOTAL_TESTS -gt 0 ]; then
        SUCCESS_RATE=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
        echo -e "\n${BOLD}Success Rate: ${SUCCESS_RATE}%${NC}"
    fi
    
    # Final status
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}${BOLD}🎉 ALL FOUNDATIONS VERIFIED SUCCESSFULLY! 🎉${NC}"
        echo -e "${GREEN}The OttoAI backend is ready for production deployment.${NC}"
        exit 0
    else
        echo -e "\n${RED}${BOLD}❌ FOUNDATIONS VERIFICATION FAILED ❌${NC}"
        echo -e "${RED}Fix the failed tests before proceeding to production.${NC}"
        exit 1
    fi
}

# Show help if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "OttoAI Backend Foundations Verification Pack"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --help, -h    Show this help message"
    echo "  --verbose     Enable verbose output"
    echo ""
    echo "Environment Variables:"
    echo "  VERBOSE=true  Enable verbose test output"
    echo ""
    echo "This script runs comprehensive verification of all foundational features:"
    echo "  - Secrets hygiene"
    echo "  - CORS + tenant context"
    echo "  - Rate limiting"
    echo "  - Webhook idempotency"
    echo "  - Observability (logging, tracing, metrics)"
    echo "  - Real-time transport (WebSocket, pub/sub)"
    echo "  - Production readiness"
    echo "  - Integration testing"
    echo ""
    echo "Example:"
    echo "  $0"
    echo "  VERBOSE=true $0"
    exit 0
fi

# Set verbose mode if requested
if [ "$1" = "--verbose" ] || [ "$VERBOSE" = "true" ]; then
    set -x
fi

# Run main verification
main "$@"
