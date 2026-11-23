from uuid import uuid4

import pytest
from factory_contracts import EventDraft
from factory_core import Database
from factory_core.db import EventRow


async def test_append_assigns_independent_sequences(database: Database) -> None:
    first = uuid4()
    second = uuid4()
    one = await database.append(
        EventDraft(request_id=first, type="request.created", payload={"n": 1})
    )
    two = await database.append(
        EventDraft(request_id=first, type="workflow.started", payload={"n": 2})
    )
    other = await database.append(EventDraft(request_id=second, type="request.created", payload={}))
    assert (one.seq, two.seq, other.seq) == (1, 2, 1)
    replay = await database.read(first)
    assert [item.type for item in replay] == ["request.created", "workflow.started"]
    assert await database.read(first, after_seq=1) == [two]


async def test_orm_rejects_event_updates(database: Database) -> None:
    written = await database.append(EventDraft(request_id=uuid4(), type="request.created"))
    async with database.session() as session:
        row = await session.get(EventRow, written.id)
        assert row is not None
        row.type = "tampered"
        with pytest.raises(RuntimeError, match="append-only"):
            await session.commit()
    assert (await database.read(written.request_id))[0].type == "request.created"


def test_repository_has_no_event_mutation_methods() -> None:
    assert not hasattr(Database, "update_event")
    assert not hasattr(Database, "delete_event")
