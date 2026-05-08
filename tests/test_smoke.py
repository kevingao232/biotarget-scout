from biotarget_scout.core.config import get_settings


def test_smoke_settings() -> None:
    settings = get_settings()
    assert settings.biotarget_env == "test"
