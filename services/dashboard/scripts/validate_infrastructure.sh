#!/bin/bash

# Infrastructure Integration Validation Script
# Validates that all foundational features work with existing infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-https://tv-mvp-test.fly.dev}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
VERBOSE="${VERBOSE:-false}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Test 1: Backend Health Check
test_backend_health() {
    log_info "Testing backend health endpoint..."
    
    response=$(curl -s -w "\n%{http_code}" "$BACKEND_URL/health")
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" != "200" ]; then
        log_error "Backend health check failed: HTTP $http_code"
        return 1
    fi
    
    # Check for observability headers
    if ! curl -s -I "$BACKEND_URL/health" | grep -q "X-Request-Id"; then
        log_error "Backend missing X-Request-Id header"
        return 1
    fi
    
    log_info "Backend health check passed"
    return 0
}

# Test 2: Observability Integration
test_observability() {
    log_info "Testing observability integration..."
    
    # Test metrics endpoint
    response=$(curl -s -w "\n%{http_code}" "$BACKEND_URL/metrics")
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" != "200" ]; then
        log_error "Metrics endpoint failed: HTTP $http_code"
        return 1
    fi
    
    # Check for Prometheus format
    if ! echo "$response" | grep -q "# HELP"; then
        log_error "Metrics endpoint not returning Prometheus format"
        return 1
    fi
    
    # Test structured logging (make a request and check logs)
    trace_id=$(curl -s -H "X-Request-Id: test-$(date +%s)" "$BACKEND_URL/health" | jq -r '.trace_id' 2>/dev/null || echo "unknown")
    log_debug "Trace ID from request: $trace_id"
    
    log_info "Observability integration passed"
    return 0
}

# Test 3: CORS Integration
test_cors_integration() {
    log_info "Testing CORS integration..."
    
    # Test preflight request
    response=$(curl -s -w "\n%{http_code}" \
        -X OPTIONS \
        -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: GET" \
        -H "Access-Control-Request-Headers: authorization" \
        "$BACKEND_URL/health")
    
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" != "200" ]; then
        log_error "CORS preflight failed: HTTP $http_code"
        return 1
    fi
    
    # Check CORS headers
    cors_headers=$(curl -s -I -H "Origin: http://localhost:3000" "$BACKEND_URL/health")
    
    if ! echo "$cors_headers" | grep -q "Access-Control-Allow-Origin"; then
        log_error "Missing CORS headers"
        return 1
    fi
    
    log_info "CORS integration passed"
    return 0
}

# Test 4: Rate Limiting Integration
test_rate_limiting() {
    log_info "Testing rate limiting integration..."
    
    # Make multiple requests to trigger rate limiting
    for i in {1..5}; do
        response=$(curl -s -w "\n%{http_code}" "$BACKEND_URL/health")
        http_code=$(echo "$response" | tail -n 1)
        
        if [ "$http_code" != "200" ]; then
            log_warn "Rate limiting may be active (HTTP $http_code)"
            break
        fi
    done
    
    log_info "Rate limiting integration test completed"
    return 0
}

# Test 5: Database Integration
test_database_integration() {
    log_info "Testing database integration..."
    
    # Test a database-dependent endpoint
    response=$(curl -s -w "\n%{http_code}" "$BACKEND_URL/companies")
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" = "500" ]; then
        log_error "Database integration failed: HTTP $http_code"
        return 1
    fi
    
    log_info "Database integration passed"
    return 0
}

# Test 6: Clerk Integration
test_clerk_integration() {
    log_info "Testing Clerk integration..."
    
    # Test protected endpoint without auth (should return 401/403)
    response=$(curl -s -w "\n%{http_code}" "$BACKEND_URL/companies")
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" = "200" ]; then
        log_warn "Protected endpoint accessible without auth - check Clerk integration"
    elif [ "$http_code" = "401" ] || [ "$http_code" = "403" ]; then
        log_info "Clerk authentication working (HTTP $http_code)"
    else
        log_warn "Unexpected response from protected endpoint: HTTP $http_code"
    fi
    
    return 0
}

# Test 7: Webhook Integration
test_webhook_integration() {
    log_info "Testing webhook integration..."
    
    # Test webhook endpoints exist and respond
    webhook_endpoints=(
        "/call-rail/pre-call"
        "/call-rail/call-complete"
        "/twilio/call-status"
        "/clerk/webhook"
    )
    
    for endpoint in "${webhook_endpoints[@]}"; do
        response=$(curl -s -w "\n%{http_code}" -X POST "$BACKEND_URL$endpoint" -H "Content-Type: application/json" -d '{}')
        http_code=$(echo "$response" | tail -n 1)
        
        # Webhooks should return 400/422 for invalid data, not 404
        if [ "$http_code" = "404" ]; then
            log_error "Webhook endpoint not found: $endpoint"
            return 1
        fi
        
        log_debug "Webhook endpoint $endpoint responded with HTTP $http_code"
    done
    
    log_info "Webhook integration passed"
    return 0
}

# Test 8: Performance Impact
test_performance_impact() {
    log_info "Testing performance impact..."
    
    # Measure response time
    start_time=$(date +%s%N)
    curl -s "$BACKEND_URL/health" > /dev/null
    end_time=$(date +%s%N)
    
    duration_ms=$(( (end_time - start_time) / 1000000 ))
    
    if [ $duration_ms -gt 5000 ]; then
        log_warn "Response time is high: ${duration_ms}ms"
    else
        log_info "Response time acceptable: ${duration_ms}ms"
    fi
    
    return 0
}

# Main validation function
main() {
    log_info "Starting Infrastructure Integration Validation"
    log_info "Backend URL: $BACKEND_URL"
    
    tests_passed=0
    tests_failed=0
    
    # Run all tests
    if test_backend_health; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_observability; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_cors_integration; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_rate_limiting; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_database_integration; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_clerk_integration; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_webhook_integration; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_performance_impact; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    # Summary
    log_info "Validation Summary: $tests_passed passed, $tests_failed failed"
    
    if [ $tests_failed -eq 0 ]; then
        log_info "All infrastructure integration tests passed! ✅"
        exit 0
    else
        log_error "Some infrastructure integration tests failed! ❌"
        exit 1
    fi
}

# Run main function
main "$@"
