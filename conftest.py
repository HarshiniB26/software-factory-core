"""Legacy integration fixtures explicitly exercise the demo, never live providers."""

import pytest


@pytest.fixture(autouse=True)
def explicit_demo_mode(monkeypatch):
    monkeypatch.setenv("FACTORY_EXECUTION_MODE", "demo")
    monkeypatch.setenv(
        "FACTORY_SESSION_SECRET", "test-only-session-secret-not-for-production-123456"
    )
