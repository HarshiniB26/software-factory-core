from pathlib import Path

from factory_contract_tests.suites import assert_storage_contract
from factory_core import connect


async def test_sql_storage_passes_the_storage_contract(tmp_path: Path) -> None:
    database = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db",
        blob_root=tmp_path / "blobs",
    )
    try:
        await assert_storage_contract(database)
    finally:
        await database.dispose()
