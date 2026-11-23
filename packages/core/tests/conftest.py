from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from factory_core import Database, connect


@pytest.fixture
async def database(tmp_path: Path) -> AsyncIterator[Database]:
    store = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db",
        blob_root=tmp_path / "blobs",
    )
    try:
        yield store
    finally:
        await store.dispose()
