"""Apply Alembic migrations. Postgres only; SQLite tests use metadata.create_all."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def alembic_config(url: str | None = None) -> Config:
    ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini))
    chosen = url or os.environ.get(
        "FACTORY_DATABASE_URL",
        "postgresql+asyncpg://factory:factory@127.0.0.1:54329/factory",
    )
    sync_url = chosen.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def upgrade(url: str | None = None) -> None:
    command.upgrade(alembic_config(url), "head")


def main() -> None:
    upgrade()
