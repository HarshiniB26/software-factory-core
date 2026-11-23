from pathlib import Path

from factory_api.demo_seed import seed_demo
from factory_core import connect, set_database


async def test_seed_creates_varied_runs(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path}/factory.db"
    database = await connect(url, blob_root=tmp_path / "blobs")
    set_database(database)
    await seed_demo(database)
    await seed_demo(database)
    rows = await database.list_requests()
    titles = {row.title for row in rows}
    assert len(rows) >= 16
    assert len(titles) == len(rows)
    assert any(row.status == "parked" for row in rows)
    assert any(row.status == "failed" for row in rows)
    assert any(row.status == "awaiting_approval" for row in rows)
    await database.dispose()
