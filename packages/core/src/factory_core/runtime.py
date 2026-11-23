"""Process-wide handle to the database.

Activities and the API run in separate processes. Each process calls set_database
once at startup. Week 1 keeps this explicit; a later week can inject it per worker.
"""

from factory_core.db import Database

_database: Database | None = None


def set_database(database: Database) -> None:
    global _database
    _database = database


def get_database() -> Database:
    if _database is None:
        raise RuntimeError("factory database is not configured")
    return _database
