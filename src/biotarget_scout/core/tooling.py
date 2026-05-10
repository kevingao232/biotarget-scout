"""
Per-tool telemetry: short human sentences (agent + outcome + timing).

Heavy HTTP detail lives at DEBUG in the ``tools`` modules.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")

_TOOL_AGENT: dict[str, str] = {
    "pubmed_search": "LITERATURE",
    "literature_delta_upsert": "LITERATURE",
    "literature_full_index": "LITERATURE",
    "hybrid_retrieve": "LITERATURE",
    "uniprot_lookup": "KG",
    "omim_lookup": "KG",
    "string_interactions": "KG",
    "gtex_expression": "OMICS",
    "alphafold_check": "OMICS",
}

_TOOL_VERB: dict[str, str] = {
    "pubmed_search": "PubMed search",
    "literature_delta_upsert": "Index delta upsert",
    "literature_full_index": "Full index build",
    "hybrid_retrieve": "Hybrid retrieve",
    "uniprot_lookup": "UniProt lookup",
    "omim_lookup": "OMIM lookup",
    "string_interactions": "STRING network",
    "gtex_expression": "GTEx expression",
    "alphafold_check": "AlphaFold check",
}


def _extra_sentence(extra: dict[str, Any] | None) -> str:
    if not extra:
        return ""
    parts: list[str] = []
    for k, v in extra.items():
        if k in ("query",) and isinstance(v, str) and len(v) > 80:
            v = v[:77] + "..."
        parts.append(f"{k}={v!r}")
    return " (" + ", ".join(parts) + ")" if parts else ""


def traced_call(
    tool_name: str,
    fn: Callable[[], T],
    *,
    extra: dict[str, Any] | None = None,
) -> T:
    """Run ``fn`` and log one readable line; re-raise after logging on error."""
    agent = _TOOL_AGENT.get(tool_name, "TOOL")
    verb = _TOOL_VERB.get(tool_name, tool_name.replace("_", " "))
    start = time.perf_counter()
    try:
        out = fn()
        ms = (time.perf_counter() - start) * 1000.0
        tail = _extra_sentence(extra)
        logger.info("{}: {} finished in {:.0f} ms — ok.{}", agent, verb, ms, tail)
        return out
    except Exception:
        ms = (time.perf_counter() - start) * 1000.0
        tail = _extra_sentence(extra)
        logger.exception("{}: {} failed after {:.0f} ms.{}", agent, verb, ms, tail)
        raise
