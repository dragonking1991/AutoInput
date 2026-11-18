import shutil
import sys
from functools import lru_cache
from pathlib import Path

from platformdirs import user_data_path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Read-only files shipped with the app: repo root in dev, the bundle dir when packaged."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[3]


class AppSettings(BaseSettings):
    """Override with env vars, e.g. AUTOINPUT_LOG_LEVEL=DEBUG."""

    model_config = SettingsConfigDict(env_prefix="AUTOINPUT_", env_file=".env", extra="ignore")

    log_level: str = "INFO"
    data_dir: Path = user_data_path("AutoInput", appauthor=False)
    # None = auto: ./profiles when it exists (dev), else <data_dir>/profiles (installed app).
    profiles_dir: Path | None = None
    mappings_dir: Path | None = None
    kill_switch: str = "<ctrl>+<alt>+q"

    @model_validator(mode="after")
    def _resolve_config_dirs(self) -> "AppSettings":
        for name in ("profiles", "mappings"):
            if getattr(self, f"{name}_dir") is None:
                local = Path(name)
                use_local = not is_frozen() and local.is_dir()
                setattr(self, f"{name}_dir", local if use_local else self.data_dir / name)
        return self

    @property
    def profiles_path(self) -> Path:
        assert self.profiles_dir is not None
        return self.profiles_dir

    @property
    def mappings_path(self) -> Path:
        assert self.mappings_dir is not None
        return self.mappings_dir

    def seed_config(self) -> None:
        """Copy bundled profiles/mappings into the user's folders without overwriting edits."""
        for name, target in (("profiles", self.profiles_path), ("mappings", self.mappings_path)):
            bundled = resource_dir() / name
            if not bundled.is_dir():
                continue
            target.mkdir(parents=True, exist_ok=True)
            if bundled.resolve() == target.resolve():
                continue
            for src in bundled.glob("*.y*ml"):
                dest = target / src.name
                if not dest.exists():
                    shutil.copy2(src, dest)

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
