#!/usr/bin/env python3
"""
Quick validation script to test foundational features against live infrastructure.
Tests integration with Fly.io, Clerk, and existing services.
"""

import requests
import json
import time
import sys
from typing import Dict, Any, Optional

class InfrastructureValidator:
    def __init__(self, backend_url: str = "https://tv-mvp-test.fly.dev"):
        self.backend_url = backend_url
        self.session = requests.Session()
        self.results = []
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def test_health_endpoint(self) -> bool:
        """Test basic health endpoint functionality."""
        try:
            self.log("Testing health endpoint...")
            response = self.session.get(f"{self.backend_url}/health", timeout=10)
            
            if response.status_code != 200:
                self.log(f"Health endpoint failed: {response.status_code}", "ERROR")
                return False
            
            # Check for observability headers
            if "X-Request-Id" not in response.headers:
                self.log("Missing X-Request-Id header", "WARN")
            
            self.log("Health endpoint working", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Health endpoint error: {e}", "ERROR")
            return False
    
    def test_observability_headers(self) -> bool:
        """Test that observability headers are present."""
        try:
            self.log("Testing observability headers...")
            response = self.session.get(f"{self.backend_url}/health", timeout=10)
            
            required_headers = ["X-Request-Id"]
            missing_headers = []
            
            for header in required_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if missing_headers:
                self.log(f"Missing headers: {missing_headers}", "ERROR")
                return False
            
            self.log("Observability headers present", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Observability headers error: {e}", "ERROR")
            return False
    
    def test_metrics_endpoint(self) -> bool:
        """Test Prometheus metrics endpoint."""
        try:
            self.log("Testing metrics endpoint...")
            response = self.session.get(f"{self.backend_url}/metrics", timeout=10)
            
            if response.status_code != 200:
                self.log(f"Metrics endpoint failed: {response.status_code}", "ERROR")
                return False
            
            # Check for Prometheus format
            if "# HELP" not in response.text:
                self.log("Metrics not in Prometheus format", "ERROR")
                return False
            
            # Check for our custom metrics
            required_metrics = ["http_requests_total", "http_request_duration_ms"]
            missing_metrics = []
            
            for metric in required_metrics:
                if metric not in response.text:
                    missing_metrics.append(metric)
            
            if missing_metrics:
                self.log(f"Missing metrics: {missing_metrics}", "WARN")
            
            self.log("Metrics endpoint working", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Metrics endpoint error: {e}", "ERROR")
            return False
    
    def test_cors_headers(self) -> bool:
        """Test CORS headers for frontend integration."""
        try:
            self.log("Testing CORS headers...")
            
            # Test preflight request
            headers = {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization"
            }
            
            response = self.session.options(f"{self.backend_url}/health", headers=headers, timeout=10)
            
            if response.status_code != 200:
                self.log(f"CORS preflight failed: {response.status_code}", "ERROR")
                return False
            
            # Check CORS headers
            cors_headers = [
                "Access-Control-Allow-Origin",
                "Access-Control-Allow-Methods",
                "Access-Control-Allow-Headers"
            ]
            
            missing_cors = []
            for header in cors_headers:
                if header not in response.headers:
                    missing_cors.append(header)
            
            if missing_cors:
                self.log(f"Missing CORS headers: {missing_cors}", "WARN")
            
            self.log("CORS headers present", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"CORS test error: {e}", "ERROR")
            return False
    
    def test_rate_limiting(self) -> bool:
        """Test rate limiting functionality."""
        try:
            self.log("Testing rate limiting...")
            
            # Make multiple requests quickly
            responses = []
            for i in range(5):
                response = self.session.get(f"{self.backend_url}/health", timeout=5)
                responses.append(response.status_code)
                time.sleep(0.1)  # Small delay between requests
            
            # Check if any requests were rate limited
            rate_limited = any(status == 429 for status in responses)
            
            if rate_limited:
                self.log("Rate limiting is active", "SUCCESS")
            else:
                self.log("Rate limiting not triggered (may be configured for higher limits)", "INFO")
            
            return True
            
        except Exception as e:
            self.log(f"Rate limiting test error: {e}", "ERROR")
            return False
    
    def test_error_handling(self) -> bool:
        """Test RFC-7807 error handling."""
        try:
            self.log("Testing error handling...")
            
            # Test 404 endpoint
            response = self.session.get(f"{self.backend_url}/non-existent-endpoint", timeout=10)
            
            if response.status_code != 404:
                self.log(f"Expected 404, got {response.status_code}", "WARN")
            
            # Check for RFC-7807 format
            try:
                error_data = response.json()
                required_fields = ["type", "title", "detail", "status", "trace_id"]
                
                missing_fields = []
                for field in required_fields:
                    if field not in error_data:
                        missing_fields.append(field)
                
                if missing_fields:
                    self.log(f"Missing RFC-7807 fields: {missing_fields}", "ERROR")
                    return False
                
                self.log("RFC-7807 error format working", "SUCCESS")
                return True
                
            except json.JSONDecodeError:
                self.log("Error response not in JSON format", "ERROR")
                return False
            
        except Exception as e:
            self.log(f"Error handling test error: {e}", "ERROR")
            return False
    
    def test_performance(self) -> bool:
        """Test performance impact of observability features."""
        try:
            self.log("Testing performance...")
            
            # Measure response time
            start_time = time.time()
            response = self.session.get(f"{self.backend_url}/health", timeout=10)
            end_time = time.time()
            
            duration_ms = (end_time - start_time) * 1000
            
            if duration_ms > 5000:
                self.log(f"Response time is high: {duration_ms:.2f}ms", "WARN")
            else:
                self.log(f"Response time acceptable: {duration_ms:.2f}ms", "SUCCESS")
            
            return True
            
        except Exception as e:
            self.log(f"Performance test error: {e}", "ERROR")
            return False
    
    def test_webhook_endpoints(self) -> bool:
        """Test webhook endpoints are accessible."""
        try:
            self.log("Testing webhook endpoints...")
            
            webhook_endpoints = [
                "/call-rail/pre-call",
                "/call-rail/call-complete", 
                "/twilio/call-status",
                "/clerk/webhook"
            ]
            
            for endpoint in webhook_endpoints:
                response = self.session.post(
                    f"{self.backend_url}{endpoint}",
                    json={},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                # Webhooks should return 400/422 for invalid data, not 404
                if response.status_code == 404:
                    self.log(f"Webhook endpoint not found: {endpoint}", "ERROR")
                    return False
                
                self.log(f"Webhook {endpoint}: {response.status_code}", "INFO")
            
            self.log("Webhook endpoints accessible", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Webhook test error: {e}", "ERROR")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all validation tests."""
        self.log("Starting infrastructure validation...")
        self.log(f"Backend URL: {self.backend_url}")
        
        tests = [
            ("Health Endpoint", self.test_health_endpoint),
            ("Observability Headers", self.test_observability_headers),
            ("Metrics Endpoint", self.test_metrics_endpoint),
            ("CORS Headers", self.test_cors_headers),
            ("Rate Limiting", self.test_rate_limiting),
            ("Error Handling", self.test_error_handling),
            ("Performance", self.test_performance),
            ("Webhook Endpoints", self.test_webhook_endpoints),
        ]
        
        results = {}
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            self.log(f"\n--- {test_name} ---")
            try:
                result = test_func()
                results[test_name] = result
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log(f"Test {test_name} crashed: {e}", "ERROR")
                results[test_name] = False
                failed += 1
        
        # Summary
        self.log(f"\n{'='*50}")
        self.log(f"VALIDATION SUMMARY: {passed} passed, {failed} failed")
        
        if failed == 0:
            self.log("All tests passed! ✅", "SUCCESS")
        else:
            self.log("Some tests failed! ❌", "ERROR")
        
        return results

def main():
    """Main function."""
    backend_url = sys.argv[1] if len(sys.argv) > 1 else "https://tv-mvp-test.fly.dev"
    
    validator = InfrastructureValidator(backend_url)
    results = validator.run_all_tests()
    
    # Exit with error code if any tests failed
    if not all(results.values()):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
