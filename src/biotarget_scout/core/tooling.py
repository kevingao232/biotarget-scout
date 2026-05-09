"""
Per-tool telemetry: latency, success/failure, and optional structured extras.

Use this around external I/O so logs pinpoint PubMed vs UniProt vs Chroma failures.
LangSmith: when agents use LangChain tools, enable callbacks; this module covers
direct function calls until then.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def traced_call(
    tool_name: str,
    fn: Callable[[], T],
    *,
    extra: dict[str, Any] | None = None,
) -> T:
    """Run ``fn`` and log duration; re-raise exceptions after logging."""
    start = time.perf_counter()
    try:
        out = fn()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        payload = {"tool": tool_name, "elapsed_ms": round(elapsed_ms, 2), "status": "ok"}
        if extra:
            payload.update(extra)
        logger.info("%s", payload)
        return out
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.warning(
            "tool_error tool=%s elapsed_ms=%.2f err=%s",
            tool_name,
            elapsed_ms,
            exc,
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        raise
