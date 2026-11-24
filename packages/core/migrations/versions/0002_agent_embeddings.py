"""Store agent need-vectors for registry search.

Revision ID: 0002_agent_embeddings
Revises: 0001_initial
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_agent_embeddings"
down_revision: str | None = "0002_messages_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_embeddings (
            agent_id VARCHAR(200) NOT NULL,
            version VARCHAR(64) NOT NULL,
            embedding vector(32) NOT NULL,
            PRIMARY KEY (agent_id, version)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_embeddings")
