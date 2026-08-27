from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime settings. Secrets are read from environment variables only."""

    model_config = SettingsConfigDict(
        env_prefix="SOGAVKG_",
        extra="ignore",
        frozen=True,
    )

    database_path: Path = PROJECT_ROOT / "backend" / "data" / "lab.db"
    mapping_dir: Path = PROJECT_ROOT / "semantic" / "mappings"
    public_default_fields: tuple[str, ...] = (
        "asset_code",
        "name",
        "quantity",
        "status",
        "category",
        "location",
    )
    default_limit: int = Field(default=20, ge=1)
    maximum_limit: int = Field(default=100, ge=1)
    planning_max_calls: int = Field(default=2, ge=1, le=2)
    planning_deadline_seconds: float = Field(default=15.0, gt=0, le=120)
    answer_max_calls: int = Field(default=2, ge=1, le=2)
    answer_deadline_seconds: float = Field(default=15.0, gt=0, le=120)
    model_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4.1-mini"
    model_api_key: SecretStr | None = None
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("database_path", "mapping_dir", mode="after")
    @classmethod
    def resolve_project_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (PROJECT_ROOT / value).resolve()

    @model_validator(mode="after")
    def validate_limits(self) -> "Settings":
        if self.default_limit > self.maximum_limit:
            raise ValueError("default_limit must not exceed maximum_limit")
        if not self.public_default_fields:
            raise ValueError("public_default_fields must not be empty")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
