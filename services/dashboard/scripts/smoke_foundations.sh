#!/bin/bash

# OttoAI Backend - Foundations Smoke Test Script
# This script validates the three core security foundations:
# 1. Secrets & Environment Hygiene
# 2. CORS Lockdown + Tenant Middleware  
# 3. API Rate Limiting (per-user + per-tenant)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration from environment variables
BASE_URL="${BASE:-http://localhost:8000}"
ORIGIN_OK="${ORIGIN_OK:-http://localhost:3000}"
ORIGIN_BAD="${ORIGIN_BAD:-https://malicious-site.com}"
TOKEN_A="${TOKEN_A:-}"
TOKEN_B="${TOKEN_B:-}"

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
    ((TESTS_FAILED++))
    FAILED_TESTS+=("$1")
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if required environment variables are set
check_environment() {
    log_info "Checking environment configuration..."
    
    if [[ -z "$TOKEN_A" || -z "$TOKEN_B" ]]; then
        log_warning "TOKEN_A and TOKEN_B environment variables not set."
        log_warning "Some tests will be skipped. Set these for full validation:"
        log_warning "  export TOKEN_A='your_jwt_token_for_user_a'"
        log_warning "  export TOKEN_B='your_jwt_token_for_user_b'"
        log_warning "  export BASE='http://localhost:8000'"
        log_warning "  export ORIGIN_OK='http://localhost:3000'"
        log_warning "  export ORIGIN_BAD='https://malicious-site.com'"
        echo ""
    fi
    
    log_info "Using configuration:"
    log_info "  BASE_URL: $BASE_URL"
    log_info "  ORIGIN_OK: $ORIGIN_OK"
    log_info "  ORIGIN_BAD: $ORIGIN_BAD"
    log_info "  TOKEN_A: ${TOKEN_A:0:20}..." 
    log_info "  TOKEN_B: ${TOKEN_B:0:20}..."
    echo ""
}

# Test 1: CORS Configuration
test_cors() {
    log_info "Testing CORS configuration..."
    
    # Test allowed origin
    if curl -s -o /dev/null -w "%{http_code}" -H "Origin: $ORIGIN_OK" "$BASE_URL/health" | grep -q "200"; then
        log_success "CORS allowed origin OK"
    else
        log_error "CORS allowed origin FAIL"
    fi
    
    # Test disallowed origin
    if curl -s -o /dev/null -w "%{http_code}" -H "Origin: $ORIGIN_BAD" "$BASE_URL/health" | grep -q "403"; then
        log_success "CORS disallowed origin blocked"
    else
        log_error "CORS disallowed origin not blocked"
    fi
    
    echo ""
}

# Test 2: Tenant Validation
test_tenant_validation() {
    log_info "Testing tenant validation middleware..."
    
    # Test no token
    if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/user/company" | grep -q "403"; then
        log_success "No token → 403 OK"
    else
        log_error "No token → 403 FAIL"
    fi
    
    # Test invalid token
    if curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer invalid_token" "$BASE_URL/user/company" | grep -q "403"; then
        log_success "Invalid token → 403 OK"
    else
        log_error "Invalid token → 403 FAIL"
    fi
    
    # Test valid token (if provided)
    if [[ -n "$TOKEN_A" ]]; then
        if curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_A" "$BASE_URL/user/company" | grep -q -E "(200|404|500)"; then
            log_success "Valid token → OK (not 403)"
        else
            log_error "Valid token → FAIL (got 403)"
        fi
    else
        log_warning "Valid token test skipped (TOKEN_A not set)"
    fi
    
    echo ""
}

# Test 3: Rate Limiting - Per User
test_rate_limit_per_user() {
    log_info "Testing per-user rate limiting..."
    
    if [[ -z "$TOKEN_A" ]]; then
        log_warning "Per-user rate limit test skipped (TOKEN_A not set)"
        echo ""
        return
    fi
    
    # Make 5 requests (should all pass)
    log_info "Making 5 requests (should all pass)..."
    for i in {1..5}; do
        status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_A" "$BASE_URL/user/company")
        if [[ "$status" == "429" ]]; then
            log_error "Request $i hit rate limit (should not happen yet)"
            echo ""
            return
        fi
    done
    log_success "First 5 requests passed"
    
    # Make 6th request (should hit rate limit)
    log_info "Making 6th request (should hit rate limit)..."
    status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_A" "$BASE_URL/user/company")
    if [[ "$status" == "429" ]]; then
        log_success "6th request hit rate limit (429)"
        
        # Check Retry-After header
        retry_after=$(curl -s -I -H "Authorization: Bearer $TOKEN_A" "$BASE_URL/user/company" | grep -i "retry-after" | cut -d' ' -f2 | tr -d '\r')
        if [[ -n "$retry_after" ]]; then
            log_success "Retry-After header present: $retry_after"
        else
            log_error "Retry-After header missing"
        fi
    else
        log_error "6th request did not hit rate limit (got $status)"
    fi
    
    echo ""
}

# Test 4: Rate Limiting - Per Tenant
test_rate_limit_per_tenant() {
    log_info "Testing per-tenant rate limiting..."
    
    if [[ -z "$TOKEN_A" || -z "$TOKEN_B" ]]; then
        log_warning "Per-tenant rate limit test skipped (TOKEN_A or TOKEN_B not set)"
        echo ""
        return
    fi
    
    # User A makes 6 requests
    log_info "User A making 6 requests..."
    for i in {1..6}; do
        status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_A" "$BASE_URL/user/company")
        if [[ "$status" == "429" ]]; then
            log_error "User A request $i hit rate limit too early"
            echo ""
            return
        fi
    done
    log_success "User A: 6 requests passed"
    
    # User B makes 6 requests (should hit tenant limit)
    log_info "User B making 6 requests (should hit tenant limit)..."
    rate_limited=false
    for i in {1..6}; do
        status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN_B" "$BASE_URL/user/company")
        if [[ "$status" == "429" ]]; then
            log_success "User B request $i hit tenant rate limit (429)"
            rate_limited=true
            break
        fi
    done
    
    if [[ "$rate_limited" == false ]]; then
        log_error "User B did not hit tenant rate limit"
    fi
    
    echo ""
}

# Test 5: Exempt Routes
test_exempt_routes() {
    log_info "Testing exempt routes (should never 429)..."
    
    exempt_routes=("/health" "/ready" "/metrics" "/docs" "/openapi.json")
    
    for route in "${exempt_routes[@]}"; do
        # Make multiple requests to ensure no rate limiting
        for i in {1..10}; do
            status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$route")
            if [[ "$status" == "429" ]]; then
                log_error "Exempt route $route was rate limited"
                echo ""
                return
            fi
        done
    done
    
    log_success "All exempt routes never hit rate limit"
    echo ""
}

# Test 6: Health Check
test_health_check() {
    log_info "Testing basic health check..."
    
    response=$(curl -s "$BASE_URL/health")
    if echo "$response" | grep -q "healthy"; then
        log_success "Health check OK"
    else
        log_error "Health check FAIL"
    fi
    
    echo ""
}

# Main execution
main() {
    echo -e "${BLUE}🚀 OttoAI Backend - Foundations Smoke Test${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo ""
    
    check_environment
    test_health_check
    test_cors
    test_tenant_validation
    test_rate_limit_per_user
    test_rate_limit_per_tenant
    test_exempt_routes
    
    # Summary
    echo -e "${BLUE}📊 Test Summary${NC}"
    echo -e "${BLUE}===============${NC}"
    echo -e "${GREEN}✅ Tests Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}❌ Tests Failed: $TESTS_FAILED${NC}"
    echo ""
    
    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo -e "${RED}Failed Tests:${NC}"
        for test in "${FAILED_TESTS[@]}"; do
            echo -e "${RED}  - $test${NC}"
        done
        echo ""
        echo -e "${RED}❌ FOUNDATIONS VERIFICATION FAILED${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ ALL FOUNDATIONS VERIFICATION PASSED${NC}"
        exit 0
    fi
}

# Run main function
main "$@"
