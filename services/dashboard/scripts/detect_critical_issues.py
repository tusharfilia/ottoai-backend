#!/usr/bin/env python3
"""
Critical Issue Detection Script
Detects potential problems with our foundational features before they cause production issues.
"""

import os
import sys
import json
import requests
import time
from typing import List, Dict, Any, Optional

class CriticalIssueDetector:
    def __init__(self, backend_url: str = "https://tv-mvp-test.fly.dev"):
        self.backend_url = backend_url
        self.issues = []
        self.warnings = []
    
    def add_issue(self, category: str, issue: str, severity: str = "ERROR"):
        """Add a critical issue."""
        self.issues.append({
            "category": category,
            "issue": issue,
            "severity": severity,
            "timestamp": time.time()
        })
    
    def add_warning(self, category: str, warning: str):
        """Add a warning."""
        self.warnings.append({
            "category": category,
            "warning": warning,
            "timestamp": time.time()
        })
    
    def check_observability_conflicts(self):
        """Check for observability conflicts with infrastructure."""
        try:
            # Test if metrics endpoint is accessible
            response = requests.get(f"{self.backend_url}/metrics", timeout=10)
            if response.status_code != 200:
                self.add_issue("OBSERVABILITY", f"Metrics endpoint not accessible: {response.status_code}")
            
            # Check if trace IDs are being generated
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if "X-Request-Id" not in response.headers:
                self.add_issue("OBSERVABILITY", "X-Request-Id header missing")
            
            # Check if structured logging is working (by looking at response format)
            try:
                health_data = response.json()
                if "timestamp" not in health_data:
                    self.add_warning("OBSERVABILITY", "Health endpoint may not be using structured logging")
            except json.JSONDecodeError:
                self.add_warning("OBSERVABILITY", "Health endpoint not returning JSON")
                
        except requests.RequestException as e:
            self.add_issue("OBSERVABILITY", f"Observability test failed: {e}")
    
    def check_cors_issues(self):
        """Check for CORS configuration issues."""
        try:
            # Test preflight request
            headers = {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization"
            }
            
            response = requests.options(f"{self.backend_url}/health", headers=headers, timeout=10)
            
            if response.status_code != 200:
                self.add_issue("CORS", f"CORS preflight failed: {response.status_code}")
            
            # Check for required CORS headers
            required_headers = ["Access-Control-Allow-Origin", "Access-Control-Allow-Methods"]
            missing_headers = []
            
            for header in required_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if missing_headers:
                self.add_issue("CORS", f"Missing CORS headers: {missing_headers}")
            
            # Check if CORS allows frontend origin
            if "Access-Control-Allow-Origin" in response.headers:
                allowed_origin = response.headers["Access-Control-Allow-Origin"]
                if allowed_origin != "http://localhost:3000" and allowed_origin != "*":
                    self.add_warning("CORS", f"CORS may not allow frontend origin: {allowed_origin}")
                    
        except requests.RequestException as e:
            self.add_issue("CORS", f"CORS test failed: {e}")
    
    def check_rate_limiting_issues(self):
        """Check for rate limiting configuration issues."""
        try:
            # Make multiple requests to test rate limiting
            responses = []
            for i in range(10):
                response = requests.get(f"{self.backend_url}/health", timeout=5)
                responses.append(response.status_code)
                time.sleep(0.1)
            
            # Check for rate limiting
            rate_limited_count = sum(1 for status in responses if status == 429)
            
            if rate_limited_count > 5:
                self.add_issue("RATE_LIMITING", f"Rate limiting too aggressive: {rate_limited_count}/10 requests blocked")
            elif rate_limited_count > 0:
                self.add_warning("RATE_LIMITING", f"Rate limiting active: {rate_limited_count}/10 requests blocked")
            
            # Check response times
            start_time = time.time()
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000
            if response_time > 5000:
                self.add_issue("PERFORMANCE", f"Response time too high: {response_time:.2f}ms")
            elif response_time > 2000:
                self.add_warning("PERFORMANCE", f"Response time elevated: {response_time:.2f}ms")
                
        except requests.RequestException as e:
            self.add_issue("RATE_LIMITING", f"Rate limiting test failed: {e}")
    
    def check_webhook_issues(self):
        """Check for webhook processing issues."""
        webhook_endpoints = [
            ("/call-rail/pre-call", "CallRail"),
            ("/call-rail/call-complete", "CallRail"),
            ("/twilio/call-status", "Twilio"),
            ("/clerk/webhook", "Clerk")
        ]
        
        for endpoint, provider in webhook_endpoints:
            try:
                # Test webhook endpoint with minimal payload
                response = requests.post(
                    f"{self.backend_url}{endpoint}",
                    json={},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code == 404:
                    self.add_issue("WEBHOOKS", f"{provider} webhook endpoint not found: {endpoint}")
                elif response.status_code == 500:
                    self.add_issue("WEBHOOKS", f"{provider} webhook endpoint error: {endpoint}")
                elif response.status_code == 429:
                    self.add_warning("WEBHOOKS", f"{provider} webhook may be rate limited: {endpoint}")
                
            except requests.RequestException as e:
                self.add_issue("WEBHOOKS", f"{provider} webhook test failed: {e}")
    
    def check_error_handling_issues(self):
        """Check for error handling issues."""
        try:
            # Test 404 endpoint
            response = requests.get(f"{self.backend_url}/non-existent-endpoint", timeout=10)
            
            if response.status_code != 404:
                self.add_warning("ERROR_HANDLING", f"Expected 404, got {response.status_code}")
            
            # Check for RFC-7807 format
            try:
                error_data = response.json()
                required_fields = ["type", "title", "detail", "status"]
                missing_fields = [field for field in required_fields if field not in error_data]
                
                if missing_fields:
                    self.add_issue("ERROR_HANDLING", f"Missing RFC-7807 fields: {missing_fields}")
                
                # Check if trace_id is present
                if "trace_id" not in error_data:
                    self.add_warning("ERROR_HANDLING", "Error response missing trace_id")
                    
            except json.JSONDecodeError:
                self.add_issue("ERROR_HANDLING", "Error response not in JSON format")
                
        except requests.RequestException as e:
            self.add_issue("ERROR_HANDLING", f"Error handling test failed: {e}")
    
    def check_database_issues(self):
        """Check for database-related issues."""
        try:
            # Test database-dependent endpoint
            response = requests.get(f"{self.backend_url}/companies", timeout=10)
            
            if response.status_code == 500:
                self.add_issue("DATABASE", "Database connection or query error")
            elif response.status_code == 503:
                self.add_issue("DATABASE", "Database service unavailable")
            elif response.status_code == 200:
                # Check response time for database operations
                start_time = time.time()
                requests.get(f"{self.backend_url}/companies", timeout=10)
                end_time = time.time()
                
                db_response_time = (end_time - start_time) * 1000
                if db_response_time > 5000:
                    self.add_issue("DATABASE", f"Database query too slow: {db_response_time:.2f}ms")
                elif db_response_time > 2000:
                    self.add_warning("DATABASE", f"Database query slow: {db_response_time:.2f}ms")
                    
        except requests.RequestException as e:
            self.add_issue("DATABASE", f"Database test failed: {e}")
    
    def check_authentication_issues(self):
        """Check for authentication-related issues."""
        try:
            # Test protected endpoint without auth
            response = requests.get(f"{self.backend_url}/companies", timeout=10)
            
            if response.status_code == 200:
                self.add_warning("AUTHENTICATION", "Protected endpoint accessible without authentication")
            elif response.status_code not in [401, 403]:
                self.add_warning("AUTHENTICATION", f"Unexpected auth response: {response.status_code}")
                
        except requests.RequestException as e:
            self.add_issue("AUTHENTICATION", f"Authentication test failed: {e}")
    
    def run_all_checks(self):
        """Run all critical issue checks."""
        print("🔍 Running critical issue detection...")
        print(f"Backend URL: {self.backend_url}")
        print("=" * 50)
        
        checks = [
            ("Observability Conflicts", self.check_observability_conflicts),
            ("CORS Issues", self.check_cors_issues),
            ("Rate Limiting Issues", self.check_rate_limiting_issues),
            ("Webhook Issues", self.check_webhook_issues),
            ("Error Handling Issues", self.check_error_handling_issues),
            ("Database Issues", self.check_database_issues),
            ("Authentication Issues", self.check_authentication_issues),
        ]
        
        for check_name, check_func in checks:
            print(f"\n--- {check_name} ---")
            try:
                check_func()
                print("✅ Check completed")
            except Exception as e:
                print(f"❌ Check failed: {e}")
                self.add_issue("SYSTEM", f"{check_name} check crashed: {e}")
        
        # Summary
        print(f"\n{'='*50}")
        print(f"CRITICAL ISSUES: {len(self.issues)}")
        print(f"WARNINGS: {len(self.warnings)}")
        
        if self.issues:
            print("\n🚨 CRITICAL ISSUES FOUND:")
            for issue in self.issues:
                print(f"  [{issue['category']}] {issue['issue']}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  [{warning['category']}] {warning['warning']}")
        
        if not self.issues and not self.warnings:
            print("\n✅ No critical issues detected!")
        
        return len(self.issues) == 0

def main():
    """Main function."""
    backend_url = sys.argv[1] if len(sys.argv) > 1 else "https://tv-mvp-test.fly.dev"
    
    detector = CriticalIssueDetector(backend_url)
    success = detector.run_all_checks()
    
    # Exit with error code if critical issues found
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
