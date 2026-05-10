"""FastAPI HTTP layer (thin): maps JSON ↔ run_pipeline."""

from biotarget_scout.api.app import app, create_app

__all__ = ["app", "create_app"]
