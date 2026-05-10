"""Readable, multi-line log blocks for terminals (Loguru)."""

from __future__ import annotations

from loguru import logger

WIDTH = 56
SEP = "*" * WIDTH


def block(title: str, lines: list[str]) -> None:
    """One titled section with star lines above and below."""
    body = "\n".join(lines)
    logger.info(f"\n{SEP}\n{title}\n{SEP}\n{body}\n{SEP}")


def line(prefix: str, message: str) -> None:
    """Single sentence with a clear prefix (e.g. LITERATURE, KG, OMICS, ORCH)."""
    logger.info("{} {}", prefix, message)
