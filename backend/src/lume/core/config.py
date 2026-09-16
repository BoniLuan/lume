from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LUME_", case_sensitive=False)

    env: Literal["development", "test", "production"] = "development"
    database_host: str = "127.0.0.1"
    database_port: int = 3306
    database_name: str = "lume_dev"
    database_user: str = "lume_dev"
    database_password: str | None = None
    database_password_file: Path | None = None
    allowed_origins: list[str] = Field(default_factory=list)
    secure_cookies: bool = True
    log_level: str = "INFO"

    @field_validator("database_name")
    @classmethod
    def protect_production_data(cls, value: str, info: object) -> str:
        del info
        if not value:
            raise ValueError("database name cannot be empty")
        return value

    @property
    def resolved_database_password(self) -> str:
        if self.database_password_file is not None:
            return self.database_password_file.read_text(encoding="utf-8").strip()
        if self.database_password is None:
            raise ValueError("database password or password file is required")
        return self.database_password

    @property
    def database_url(self) -> URL:
        if self.env == "test" and "test" not in self.database_name.casefold():
            raise ValueError("test environment requires a test database name")
        return URL.create(
            "mariadb+pymysql",
            username=self.database_user,
            password=self.resolved_database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
