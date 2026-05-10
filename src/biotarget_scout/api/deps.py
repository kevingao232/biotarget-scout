"""Shared FastAPI dependencies (extend for DB sessions, auth, shared_index, etc.)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from biotarget_scout.agents.orchestrator import run_pipeline


def get_run_pipeline() -> Callable[..., Awaitable]:
    """Inject orchestrator entrypoint (override in tests via app.dependency_overrides)."""
    return run_pipeline
