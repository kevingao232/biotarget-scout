"""Multi-agent orchestration (planner, specialists, synthesis, scoring)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["run_pipeline"]


def __getattr__(name: str) -> Any:
    if name == "run_pipeline":
        from biotarget_scout.agents.orchestrator import run_pipeline as _run_pipeline

        return _run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from biotarget_scout.agents.orchestrator import run_pipeline
