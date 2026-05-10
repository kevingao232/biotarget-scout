import os
import sys

from loguru import logger


def configure_logging(level: str | None = None) -> None:
    """
    Configure Loguru for the process (call once from FastAPI lifespan or CLI).

    - Default: human-readable lines on stderr (good for local dev + uvicorn).
    - Set ``LOG_JSON=1`` for one JSON object per line (log aggregators).
    """
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    use_json = os.getenv("LOG_JSON", "").lower() in ("1", "true", "yes")

    logger.remove()
    if use_json:
        logger.add(sys.stderr, level=level, serialize=True, backtrace=False, diagnose=False)
    else:
        logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
        )


def get_logger():
    return logger
