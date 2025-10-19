"""
Locust load testing scenarios for Otto Backend API.

Usage:
    # Local testing
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Staging testing
    locust -f tests/load/locustfile.py --host=https://otto-backend-staging.fly.dev

    # Web UI
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --web-port=8089
    # Then open: http://localhost:8089

    # Headless (automated)
    locust -f tests/load/locustfile.py \
        --host=http://localhost:8000 \
        --users=100 \
        --spawn-rate=10 \
        --run-time=5m \
        --headless

Performance Targets:
    - P95 latency < 500ms
    - Error rate < 1%
    - Throughput: 100 req/sec sustained
    - Max users: 100 concurrent
"""

from locust import HttpUser, task, between, tag
import random
import json


class OttoUser(HttpUser):
    """
    Simulates a typical Otto user making API calls.
    
    Wait time: 1-3 seconds between requests (realistic user behavior)
    """
    wait_time = between(1, 3)
    
    # Sample data for testing
    company_ids = ["org_test_123", "org_test_456", "org_test_789"]
    call_ids = list(range(1, 101))  # Calls 1-100
    user_ids = ["user_001", "user_002", "user_003"]
    
    def on_start(self):
        """
        Called when user starts. Set up authentication.
        
        Note: In real load test, you'd fetch JWT token from Clerk.
        For now, use a long-lived test token.
        """
        # In production, get real JWT token from Clerk
        # For testing, use mock token or long-lived test token
        self.token = "test_jwt_token_here"  # Replace with real token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.company_id = random.choice(self.company_ids)
    
    @task(5)
    @tag("health")
    def health_check(self):
        """Health check endpoint (no auth needed)."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(10)
    @tag("rag")
    def ask_otto_query(self):
        """
        Ask Otto query - Most frequently used endpoint.
        
        Weight: 10 (10x more frequent than health check)
        """
        queries = [
            "What are the most common objections this week?",
            "Show me my pending follow-ups",
            "What should I improve?",
            "Which rep has the highest close rate?",
            "What coaching tips do I need?"
        ]
        
        payload = {
            "query": random.choice(queries),
            "context_scope": ["calls", "appointments"],
            "filters": {}
        }
        
        with self.client.post(
            "/api/v1/rag/query",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/api/v1/rag/query"
        ) as response:
            if response.status_code == 200:
                # Validate response structure
                data = response.json()
                if "answer" in data and "citations" in data:
                    response.success()
                else:
                    response.failure("Invalid response structure")
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(8)
    @tag("calls")
    def get_call_details(self):
        """
        Fetch call details - Common operation for managers reviewing calls.
        
        Weight: 8 (frequently used)
        """
        call_id = random.choice(self.call_ids)
        
        with self.client.get(
            f"/call/{call_id}",
            headers=self.headers,
            catch_response=True,
            name="/call/{id}"
        ) as response:
            if response.status_code in [200, 404]:
                # 404 is acceptable (call might not exist)
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(6)
    @tag("analysis")
    def trigger_call_analysis(self):
        """
        Trigger AI analysis on call - Used by managers and reps.
        
        Weight: 6 (moderately frequent)
        """
        call_id = random.choice(self.call_ids)
        
        with self.client.post(
            f"/api/v1/calls/{call_id}/analyze",
            headers=self.headers,
            catch_response=True,
            name="/api/v1/calls/{id}/analyze"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(6)
    @tag("analysis")
    def get_call_analysis(self):
        """
        Fetch analysis results - Used after triggering analysis.
        
        Weight: 6 (moderately frequent)
        """
        call_id = random.choice(self.call_ids)
        
        with self.client.get(
            f"/api/v1/calls/{call_id}/analysis",
            headers=self.headers,
            catch_response=True,
            name="/api/v1/calls/{id}/analysis"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(4)
    @tag("followups")
    def generate_followup_draft(self):
        """
        Generate follow-up draft - Used by reps for lead nurturing.
        
        Weight: 4 (regular usage)
        """
        call_id = random.choice(self.call_ids)
        
        payload = {
            "call_id": call_id,
            "draft_type": random.choice(["sms", "email"]),
            "tone": random.choice(["professional", "friendly"])
        }
        
        with self.client.post(
            "/api/v1/followups/draft",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/api/v1/followups/draft"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(3)
    @tag("followups")
    def list_followup_drafts(self):
        """
        List follow-up drafts - Used by reps to see pending drafts.
        
        Weight: 3 (regular usage)
        """
        with self.client.get(
            "/api/v1/followups/drafts?limit=20",
            headers=self.headers,
            catch_response=True,
            name="/api/v1/followups/drafts"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(2)
    @tag("objections")
    def get_objection_analytics(self):
        """
        Get objection analytics - Used by managers for coaching insights.
        
        Weight: 2 (periodic usage)
        """
        with self.client.get(
            "/api/v1/analytics/objections",
            headers=self.headers,
            catch_response=True,
            name="/api/v1/analytics/objections"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(2)
    @tag("documents")
    def list_documents(self):
        """
        List RAG documents - Used by execs to see uploaded SOPs.
        
        Weight: 2 (periodic usage)
        """
        with self.client.get(
            "/api/v1/rag/documents",
            headers=self.headers,
            catch_response=True,
            name="/api/v1/rag/documents"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")
    
    @task(1)
    @tag("clone")
    def get_clone_status(self):
        """
        Check personal clone training status - Used by reps.
        
        Weight: 1 (infrequent usage)
        """
        rep_id = f"rep_{random.randint(1, 10):03d}"
        
        with self.client.get(
            f"/api/v1/clone/{rep_id}/status",
            headers=self.headers,
            catch_response=True,
            name="/api/v1/clone/{rep_id}/status"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")


class ManagerUser(HttpUser):
    """
    Simulates a manager reviewing team performance.
    
    Heavy on analytics and ridealong endpoints.
    """
    wait_time = between(2, 5)
    weight = 3  # 30% of users are managers
    
    def on_start(self):
        self.token = "manager_test_token"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    @task(10)
    def review_calls(self):
        """Managers review calls frequently."""
        call_id = random.randint(1, 100)
        self.client.get(f"/call/{call_id}", headers=self.headers, name="/call/{id}")
    
    @task(8)
    def check_analysis_results(self):
        """Check if analysis is complete."""
        call_id = random.randint(1, 100)
        self.client.get(f"/api/v1/calls/{call_id}/analysis", headers=self.headers, name="/api/v1/calls/{id}/analysis")
    
    @task(5)
    def ask_otto_team_questions(self):
        """Ask questions about team performance."""
        queries = [
            "Which rep needs coaching on objection handling?",
            "What's the team's win rate this week?",
            "Show me today's appointments"
        ]
        payload = {"query": random.choice(queries)}
        self.client.post("/api/v1/rag/query", json=payload, headers=self.headers, name="/api/v1/rag/query")
    
    @task(3)
    def get_objection_analytics(self):
        """View objection dashboard."""
        self.client.get("/api/v1/analytics/objections", headers=self.headers, name="/api/v1/analytics/objections")


class RepUser(HttpUser):
    """
    Simulates a sales rep using mobile app.
    
    Heavy on personal stats, follow-ups, and Ask Otto.
    """
    wait_time = between(3, 10)
    weight = 7  # 70% of users are reps
    
    def on_start(self):
        self.token = "rep_test_token"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.rep_id = f"rep_{random.randint(1, 20):03d}"
    
    @task(10)
    def ask_otto_personal(self):
        """Reps ask about their own performance."""
        queries = [
            "What should I improve?",
            "Show me my pending follow-ups",
            "What did I do well in my last appointment?"
        ]
        payload = {"query": random.choice(queries)}
        self.client.post("/api/v1/rag/query", json=payload, headers=self.headers, name="/api/v1/rag/query")
    
    @task(8)
    def generate_followup(self):
        """Generate follow-up messages for leads."""
        payload = {
            "call_id": random.randint(1, 100),
            "draft_type": "sms",
            "tone": "friendly"
        }
        self.client.post("/api/v1/followups/draft", json=payload, headers=self.headers, name="/api/v1/followups/draft")
    
    @task(5)
    def check_followup_drafts(self):
        """Check pending follow-up drafts."""
        self.client.get("/api/v1/followups/drafts", headers=self.headers, name="/api/v1/followups/drafts")
    
    @task(2)
    def check_clone_status(self):
        """Check personal clone training status."""
        self.client.get(f"/api/v1/clone/{self.rep_id}/status", headers=self.headers, name="/api/v1/clone/{rep_id}/status")
    
    @task(1)
    def trigger_analysis(self):
        """Trigger analysis on own calls."""
        call_id = random.randint(1, 100)
        self.client.post(f"/api/v1/calls/{call_id}/analyze", headers=self.headers, name="/api/v1/calls/{id}/analyze")


# Additional test scenarios

class StressTestUser(HttpUser):
    """
    Aggressive user for stress testing.
    
    No wait time between requests - tests max throughput.
    """
    wait_time = between(0.1, 0.5)  # Very aggressive
    
    def on_start(self):
        self.token = "stress_test_token"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task
    def rapid_health_checks(self):
        """Rapid-fire health checks."""
        self.client.get("/health")
    
    @task
    def rapid_rag_queries(self):
        """Rapid-fire RAG queries to test rate limiting."""
        payload = {"query": "Test query"}
        self.client.post("/api/v1/rag/query", json=payload, headers=self.headers, name="/api/v1/rag/query")


class WebSocketUser(HttpUser):
    """
    Tests WebSocket connections for real-time features.
    
    Maintains persistent connection and listens for events.
    """
    wait_time = between(5, 15)
    
    # TODO: Implement WebSocket testing when websockets library is available
    # from locust.contrib.fasthttp import FastHttpUser
    # Use websocket library for connection testing
    
    @task
    def placeholder(self):
        """Placeholder - implement WebSocket testing."""
        pass


# Custom shapes for specific test scenarios

from locust import LoadTestShape

class StepLoadShape(LoadTestShape):
    """
    Step load pattern - Gradually increase load to find breaking point.
    
    Step 1: 10 users for 1 min
    Step 2: 25 users for 1 min
    Step 3: 50 users for 1 min
    Step 4: 100 users for 2 min
    Step 5: 150 users for 1 min (stress test)
    """
    
    step_time = 60  # 1 minute per step
    step_load = [10, 25, 50, 100, 150]
    step_spawn_rate = [5, 10, 15, 20, 25]
    
    def tick(self):
        run_time = self.get_run_time()
        
        # Calculate current step
        step = int(run_time // self.step_time)
        
        if step >= len(self.step_load):
            return None  # End test
        
        return (self.step_load[step], self.step_spawn_rate[step])


class SpikeTestShape(LoadTestShape):
    """
    Spike test - Sudden traffic surge to test elasticity.
    
    Simulates: Normal load → Sudden spike → Back to normal
    """
    
    def tick(self):
        run_time = self.get_run_time()
        
        if run_time < 60:
            # Minute 1: Normal load (20 users)
            return (20, 5)
        elif run_time < 120:
            # Minute 2: Spike! (200 users)
            return (200, 50)
        elif run_time < 180:
            # Minute 3: Back to normal (20 users)
            return (20, 10)
        else:
            return None  # End test


# Usage examples in comments
"""
# Example 1: Basic load test (100 users, 5 minutes)
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless

# Example 2: Step load test (find breaking point)
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --shape=StepLoadShape \
    --headless

# Example 3: Spike test (test elasticity)
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --shape=SpikeTestShape \
    --headless

# Example 4: Web UI (interactive)
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000
# Open: http://localhost:8089

# Example 5: Test specific tags only
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --tags rag analysis \
    --users=50 \
    --run-time=3m \
    --headless

# Example 6: Export results
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --run-time=5m \
    --headless \
    --csv=results \
    --html=report.html
"""


