#!/usr/bin/env python3
"""
Load testing script for IntelliDocs API using Locust.
Tests authentication, document upload, and chat endpoints.

Usage:
    # Install locust
    pip install locust

    # Run headless (no web UI)
    python scripts/load_test.py --headless --host http://localhost:8000 -u 10 -r 2 -t 60s

    # Run with web UI
    locust -f scripts/load_test.py --host http://localhost:8000
    # Open http://localhost:8089
"""

import random
import string
from locust import HttpUser, task, between, events
from typing import Optional


class IntelliDocsUser(HttpUser):
    """Simulated user for load testing IntelliDocs."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    host = "http://localhost:8000"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token: Optional[str] = None
        self.email: Optional[str] = None
        self.password: str = "TestPassword123!"
    
    @task(3)
    def health_check(self):
        """Test health endpoint - most common operation."""
        self.client.get("/health", name="Health Check")
    
    @task(10)
    def chat_question(self):
        """Test chat endpoint with various questions."""
        questions = [
            "What is IntelliDocs?",
            "Summarize the key points",
            "What technologies are used?",
            "Explain the architecture",
            "What are the main features?",
        ]
        
        question = random.choice(questions)
        
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        with self.client.post(
            "/chat/",
            json={"message": question},
            headers=headers,
            name="Chat Question",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "answer" in data:
                    response.success()
                else:
                    response.failure("Missing answer in response")
            elif response.status_code == 429:
                response.success()  # Rate limiting is expected
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(5)
    def list_documents(self):
        """Test listing documents."""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        self.client.get(
            "/documents/",
            headers=headers,
            name="List Documents",
        )
    
    @task(1)
    def register_and_login(self):
        """Register a new user and login."""
        # Generate unique email
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"loadtest_{unique_id}@example.com"
        
        # Register
        with self.client.post(
            "/auth/register",
            json={
                "email": email,
                "password": self.password,
                "name": "Load Test User",
            },
            name="Register User",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 400]:  # 400 if email exists
                response.success()
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    self.email = email
            else:
                response.failure(f"Registration failed: {response.status_code}")
                return
        
        # Login
        if self.email:
            self.client.post(
                "/auth/login",
                json={
                    "email": self.email,
                    "password": self.password,
                },
                name="Login User",
            )
    
    @task(2)
    def list_workspaces(self):
        """Test listing workspaces."""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        self.client.get(
            "/workspaces/",
            headers=headers,
            name="List Workspaces",
        )
    
    @task(1)
    def deep_health(self):
        """Test deep health endpoint."""
        self.client.get("/health/deep", name="Deep Health Check")
    
    @task(3)
    def metrics(self):
        """Test metrics endpoint."""
        self.client.get("/metrics/", name="Get Metrics")


class IntelliDocsApiUser(HttpUser):
    """API-focused user for testing document operations."""
    
    wait_time = between(2, 5)
    host = "http://localhost:8000"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token: Optional[str] = None
    
    def on_start(self):
        """Login before running tasks."""
        # Use a test account
        response = self.client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!",
            },
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
    
    @task(5)
    def stream_chat(self):
        """Test streaming chat endpoint."""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        questions = [
            "What is RAG?",
            "Explain vector search",
            "How does caching work?",
        ]
        
        question = random.choice(questions)
        
        self.client.post(
            "/chat/stream",
            json={"message": question},
            headers=headers,
            name="Stream Chat",
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("\n" + "="*60)
    print("IntelliDocs Load Test Starting")
    print("="*60)
    print(f"Target Host: {environment.host}")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("\n" + "="*60)
    print("IntelliDocs Load Test Complete")
    print("="*60)
    
    # Print summary stats
    stats = environment.stats
    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Failure Rate: {stats.total.num_failures / max(stats.total.num_requests, 1) * 100:.2f}%")
    print(f"Avg Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Min Response Time: {stats.total.min_response_time:.2f}ms")
    print(f"Max Response Time: {stats.total.max_response_time:.2f}ms")
    print(f"Requests/sec: {stats.total.current_rps:.2f}")
    print("="*60 + "\n")


if __name__ == "__main__":
    import os
    os.system("locust -f " + __file__ + " --host http://localhost:8000")