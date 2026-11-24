"""Process settings. Run, repo, and org config are resolved separately."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FACTORY_", extra="ignore")

    execution_mode: Literal["live", "demo"] = "live"
    database_url: str = "postgresql+asyncpg://factory:factory@127.0.0.1:54329/factory"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "factory"
    repo_root: Path = Path(".")
    blob_root: Path = Path(".factory/blobs")
    org_config: Path | None = None
