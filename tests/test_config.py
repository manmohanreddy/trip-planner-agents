from pathlib import Path

from trip_planner.config import Settings


def test_defaults_with_no_env(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("TRIP_PLANNER_RETRY_ATTEMPTS", raising=False)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.model == "sonnet"
    assert settings.retry_attempts == 3
    assert settings.output_dir == Path("output")
    assert settings.anthropic_api_key is None


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_PLANNER_MODEL", "opus")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.model == "opus"


def test_api_key_never_appears_in_repr_or_str(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-test-secret"
    assert "sk-ant-test-secret" not in repr(settings)
    assert "sk-ant-test-secret" not in str(settings)
    assert "sk-ant-test-secret" not in repr(settings.anthropic_api_key)
