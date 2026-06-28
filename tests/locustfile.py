"""Locust stress test for Komodo.

Drives the three real load shapes: agents beating, a dashboard user reading, and
health checks. Point it at a LOCAL instance, not a deployment that is watching a
real fleet.

Setup (see scripts/locust-setup.sh, which prints the env for you):
    export KOMODO_HOST=http://localhost
    export KOMODO_EMAIL=owner@example.com
    export KOMODO_PASSWORD=...
    export KOMODO_AGENT_TOKEN=...     # from creating a host
    locust -f tests/locustfile.py --host "$KOMODO_HOST" --headless -u 50 -r 10 -t 1m
"""
import os

from locust import HttpUser, between, task

EMAIL = os.getenv("KOMODO_EMAIL", "owner@example.com")
PASSWORD = os.getenv("KOMODO_PASSWORD", "")
AGENT_TOKEN = os.getenv("KOMODO_AGENT_TOKEN", "")

_BEAT_BODY = {
    "containers": [
        {"name": "demo-web", "id": "c0ffee", "image": "nginx:latest",
         "state": "running", "health": "", "status": "healthy"},
        {"name": "demo-db", "id": "deadbeef", "image": "postgres:16",
         "state": "running", "health": "", "status": "healthy"},
    ]
}


class AgentUser(HttpUser):
    """An agent reporting container status. The beat path verifies the token
    against every host's bcrypt hash, so this is the heaviest endpoint."""
    weight = 3
    wait_time = between(3, 8)

    @task
    def beat(self):
        if not AGENT_TOKEN:
            return
        self.client.post(
            "/api/v1/agent/beat",
            json=_BEAT_BODY,
            headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
            name="POST /agent/beat",
        )


class DashboardUser(HttpUser):
    """A logged-in operator reading the fleet."""
    weight = 1
    wait_time = between(1, 3)

    def on_start(self):
        if PASSWORD:
            self.client.post(
                "/api/v1/auth/login",
                json={"email": EMAIL, "password": PASSWORD},
                name="POST /auth/login",
            )

    @task(3)
    def services(self):
        self.client.get("/api/v1/services", name="GET /services")

    @task(2)
    def incidents(self):
        self.client.get("/api/v1/incidents?limit=20", name="GET /incidents")

    @task(1)
    def me(self):
        self.client.get("/api/v1/me", name="GET /me")


class HealthUser(HttpUser):
    """Cheap baseline: the load balancer health check."""
    weight = 1
    wait_time = between(1, 2)

    @task
    def health(self):
        self.client.get("/health", name="GET /health")
