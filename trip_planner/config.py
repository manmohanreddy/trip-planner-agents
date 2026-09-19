"""Typed application settings, loaded from environment / .env.

ANTHROPIC_API_KEY is read as-is (no TRIP_PLANNER_ prefix) since it's the
SDK/CLI's own convention, not this app's. Every other setting is prefixed
TRIP_PLANNER_ to avoid collisions. anthropic_api_key is a SecretStr, whose
repr/str always mask the value, even via `repr(settings)` or `str(settings)`
-- never log a raw Settings field for the key, use `.get_secret_value()`
only at the point the SDK actually needs it (and never print/log that).
"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # allows Settings(retry_attempts=2, ...) by field name, not just alias
        populate_by_name=True,
    )

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    model: str = Field(default="sonnet", alias="TRIP_PLANNER_MODEL")
    request_timeout_seconds: float = Field(
        default=90.0, alias="TRIP_PLANNER_REQUEST_TIMEOUT_SECONDS"
    )
    retry_attempts: int = Field(default=3, alias="TRIP_PLANNER_RETRY_ATTEMPTS")
    retry_backoff_base_seconds: float = Field(
        default=2.0, alias="TRIP_PLANNER_RETRY_BACKOFF_BASE_SECONDS"
    )
    stage_budget_usd: float | None = Field(default=None, alias="TRIP_PLANNER_STAGE_BUDGET_USD")
    run_budget_usd: float | None = Field(default=None, alias="TRIP_PLANNER_RUN_BUDGET_USD")
    log_level: str = Field(default="INFO", alias="TRIP_PLANNER_LOG_LEVEL")
    output_dir: Path = Field(default=Path("output"), alias="TRIP_PLANNER_OUTPUT_DIR")
    intake_max_repair_attempts: int = Field(
        default=2, alias="TRIP_PLANNER_INTAKE_MAX_REPAIR_ATTEMPTS"
    )
