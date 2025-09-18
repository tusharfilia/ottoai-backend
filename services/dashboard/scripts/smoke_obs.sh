#!/bin/bash

# OttoAI Backend Observability Smoke Test
# This script validates that observability features are working correctly

set -e  # Exit on any error

# Configuration
BASE_URL="${BASE:-http://localhost:8080}"
TOKEN="${TOKEN:-}"
VERBOSE="${VERBOSE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_verbose() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "${GREEN}[VERBOSE]${NC} $1"
    fi
}

# Check if required tools are available
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_warn "jq is not installed - JSON parsing will be limited"
    fi
    
    log_info "Dependencies check passed"
}

# Test 1: Health endpoint with trace ID
test_health_endpoint() {
    log_info "Testing health endpoint..."
    
    response=$(curl -s -w "\n%{http_code}\n%{header_json}" "$BASE_URL/health")
    http_code=$(echo "$response" | tail -n 2 | head -n 1)
    headers=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -2)
    
    if [ "$http_code" != "200" ]; then
        log_error "Health endpoint returned HTTP $http_code"
        return 1
    fi
    
    # Check for X-Request-Id header
    if ! echo "$headers" | grep -q "X-Request-Id"; then
        log_error "Health endpoint missing X-Request-Id header"
        return 1
    fi
    
    # Extract trace ID
    trace_id=$(echo "$headers" | jq -r '.["X-Request-Id"]' 2>/dev/null || echo "unknown")
    log_verbose "Health endpoint trace ID: $trace_id"
    
    log_info "Health endpoint test passed"
    return 0
}

# Test 2: Error endpoint with RFC-7807 format
test_error_endpoint() {
    log_info "Testing error endpoint..."
    
    # Create a test error endpoint by hitting a non-existent route
    response=$(curl -s -w "\n%{http_code}\n%{header_json}" "$BASE_URL/non-existent-route")
    http_code=$(echo "$response" | tail -n 2 | head -n 1)
    headers=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -2)
    
    if [ "$http_code" != "404" ]; then
        log_error "Error endpoint returned HTTP $http_code (expected 404)"
        return 1
    fi
    
    # Check for X-Request-Id header
    if ! echo "$headers" | grep -q "X-Request-Id"; then
        log_error "Error endpoint missing X-Request-Id header"
        return 1
    fi
    
    # Extract trace ID
    trace_id=$(echo "$headers" | jq -r '.["X-Request-Id"]' 2>/dev/null || echo "unknown")
    log_verbose "Error endpoint trace ID: $trace_id"
    
    # Check for RFC-7807 format in response body
    if command -v jq &> /dev/null; then
        if ! echo "$body" | jq -e '.type' &> /dev/null; then
            log_error "Error response missing 'type' field (RFC-7807)"
            return 1
        fi
        
        if ! echo "$body" | jq -e '.title' &> /dev/null; then
            log_error "Error response missing 'title' field (RFC-7807)"
            return 1
        fi
        
        if ! echo "$body" | jq -e '.detail' &> /dev/null; then
            log_error "Error response missing 'detail' field (RFC-7807)"
            return 1
        fi
        
        if ! echo "$body" | jq -e '.status' &> /dev/null; then
            log_error "Error response missing 'status' field (RFC-7807)"
            return 1
        fi
        
        if ! echo "$body" | jq -e '.trace_id' &> /dev/null; then
            log_error "Error response missing 'trace_id' field (RFC-7807)"
            return 1
        fi
        
        # Verify trace_id matches header
        body_trace_id=$(echo "$body" | jq -r '.trace_id')
        if [ "$body_trace_id" != "$trace_id" ]; then
            log_error "Trace ID mismatch: header=$trace_id, body=$body_trace_id"
            return 1
        fi
    else
        log_warn "Skipping RFC-7807 validation (jq not available)"
    fi
    
    log_info "Error endpoint test passed"
    return 0
}

# Test 3: Metrics endpoint
test_metrics_endpoint() {
    log_info "Testing metrics endpoint..."
    
    response=$(curl -s -w "\n%{http_code}\n%{header_json}" "$BASE_URL/metrics")
    http_code=$(echo "$response" | tail -n 2 | head -n 1)
    headers=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -2)
    
    if [ "$http_code" != "200" ]; then
        log_error "Metrics endpoint returned HTTP $http_code"
        return 1
    fi
    
    # Check for X-Request-Id header
    if ! echo "$headers" | grep -q "X-Request-Id"; then
        log_error "Metrics endpoint missing X-Request-Id header"
        return 1
    fi
    
    # Check for Prometheus format
    if ! echo "$body" | grep -q "# HELP"; then
        log_error "Metrics endpoint missing Prometheus HELP comments"
        return 1
    fi
    
    if ! echo "$body" | grep -q "# TYPE"; then
        log_error "Metrics endpoint missing Prometheus TYPE comments"
        return 1
    fi
    
    # Check for our custom metrics
    if ! echo "$body" | grep -q "http_requests_total"; then
        log_error "Metrics endpoint missing http_requests_total metric"
        return 1
    fi
    
    if ! echo "$body" | grep -q "http_request_duration_ms"; then
        log_error "Metrics endpoint missing http_request_duration_ms metric"
        return 1
    fi
    
    if ! echo "$body" | grep -q "worker_task_total"; then
        log_error "Metrics endpoint missing worker_task_total metric"
        return 1
    fi
    
    log_info "Metrics endpoint test passed"
    return 0
}

# Test 4: Multiple requests to verify metrics increment
test_metrics_increment() {
    log_info "Testing metrics increment..."
    
    # Get initial metrics
    initial_response=$(curl -s "$BASE_URL/metrics")
    initial_requests=$(echo "$initial_response" | grep "http_requests_total" | wc -l)
    
    # Make several requests
    for i in {1..3}; do
        curl -s "$BASE_URL/health" > /dev/null
        curl -s "$BASE_URL/metrics" > /dev/null
    done
    
    # Get final metrics
    final_response=$(curl -s "$BASE_URL/metrics")
    final_requests=$(echo "$final_response" | grep "http_requests_total" | wc -l)
    
    log_verbose "Initial requests: $initial_requests, Final requests: $final_requests"
    
    if [ "$final_requests" -le "$initial_requests" ]; then
        log_error "Metrics did not increment after making requests"
        return 1
    fi
    
    log_info "Metrics increment test passed"
    return 0
}

# Test 5: Celery task metrics (if available)
test_celery_metrics() {
    log_info "Testing Celery task metrics..."
    
    # This test would require a running Celery worker
    # For now, we'll just check that the metrics are available
    response=$(curl -s "$BASE_URL/metrics")
    
    if ! echo "$response" | grep -q "worker_task_total"; then
        log_error "Celery task metrics not available"
        return 1
    fi
    
    if ! echo "$response" | grep -q "worker_task_duration_ms"; then
        log_error "Celery task duration metrics not available"
        return 1
    fi
    
    log_info "Celery metrics test passed"
    return 1
}

# Main test runner
main() {
    log_info "Starting OttoAI Backend Observability Smoke Test"
    log_info "Base URL: $BASE_URL"
    
    # Check dependencies
    check_dependencies
    
    # Run tests
    tests_passed=0
    tests_failed=0
    
    if test_health_endpoint; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_error_endpoint; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_metrics_endpoint; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_metrics_increment; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    if test_celery_metrics; then
        ((tests_passed++))
    else
        ((tests_failed++))
    fi
    
    # Summary
    log_info "Test Summary: $tests_passed passed, $tests_failed failed"
    
    if [ $tests_failed -eq 0 ]; then
        log_info "All observability tests passed! ✅"
        exit 0
    else
        log_error "Some observability tests failed! ❌"
        exit 1
    fi
}

# Run main function
main "$@"
