import pytest
from pydantic import ValidationError

from documind.config import Settings, get_settings

ENV_VARS = (
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "DATABASE_CONNECT_TIMEOUT_SECONDS",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    # Each test starts without the variables a developer may have exported.
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_point_to_the_local_compose_database():
    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://documind:documind@127.0.0.1:5433/documind"
    assert settings.test_database_url == (
        "postgresql+psycopg://documind:documind@127.0.0.1:5433/documind_test"
    )
    assert settings.database_connect_timeout_seconds == 3
    assert settings.log_level == "INFO"


def test_environment_variables_override_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/other")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/other"
    assert settings.log_level == "DEBUG"


def test_env_file_is_read_and_unknown_keys_are_ignored(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=WARNING\nNOT_A_SETTING=1\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "WARNING"


def test_environment_variable_wins_over_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "ERROR"


def test_invalid_log_level_is_rejected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_connect_timeout_must_be_positive(monkeypatch):
    # The driver reads 0 as "wait forever", which is exactly what the timeout exists to prevent.
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_returns_the_same_cached_instance():
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
