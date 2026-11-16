from functools import lru_cache
from pathlib import Path

from platformdirs import user_data_path
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Override with env vars, e.g. AUTOINPUT_LOG_LEVEL=DEBUG."""

    model_config = SettingsConfigDict(env_prefix="AUTOINPUT_", env_file=".env", extra="ignore")

    log_level: str = "INFO"
    data_dir: Path = user_data_path("AutoInput", appauthor=False)
    profiles_dir: Path = Path("profiles")
    mappings_dir: Path = Path("mappings")
    kill_switch: str = "<ctrl>+<alt>+q"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def screenshots_dir(self) -> Path:
        return self.data_dir / "screenshots"

    @property
    def journal_path(self) -> Path:
        return self.data_dir / "journal.sqlite3"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
