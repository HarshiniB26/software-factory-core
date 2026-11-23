"""Postgres migration check. Skipped unless FACTORY_TEST_POSTGRES=1."""

import os
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("FACTORY_TEST_POSTGRES") != "1",
    reason="set FACTORY_TEST_POSTGRES=1 and FACTORY_DATABASE_URL to run",
)


def test_migration_installs_pgvector_and_rejects_updates() -> None:
    import psycopg
    from factory_core.migrate import alembic_config, upgrade

    upgrade()
    raw_url = alembic_config().get_main_option("sqlalchemy.url")
    assert raw_url is not None
    url = raw_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        assert cursor.fetchone() == ("vector",)
        request_id = uuid4()
        event_id = uuid4()
        cursor.execute(
            """
                INSERT INTO events (id, request_id, seq, type, payload, created_at)
                VALUES (%s, %s, 1, 'request.created', '{}'::jsonb, NOW())
                """,
            (event_id, request_id),
        )
        with pytest.raises(psycopg.Error, match="append-only"):
            cursor.execute("UPDATE events SET type = 'tampered' WHERE id = %s", (event_id,))
        conn.rollback()
