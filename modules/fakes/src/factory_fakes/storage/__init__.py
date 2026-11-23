"""Process-local storage used by the contract suite."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from factory_contracts import ContractError, EventDraft, FactoryEvent


class FakeStorage:
    def __init__(self) -> None:
        self._events: dict[UUID, list[FactoryEvent]] = {}
        self._state: dict[str, dict[str, Any]] = {}
        self._blobs: dict[str, bytes] = {}

    async def append(self, event: EventDraft) -> FactoryEvent:
        rows = self._events.setdefault(event.request_id, [])
        written = FactoryEvent(
            id=uuid4(),
            request_id=event.request_id,
            seq=len(rows) + 1,
            type=event.type,
            module=event.module,
            config_hash=event.config_hash,
            payload=dict(event.payload),
            created_at=datetime.now(UTC),
        )
        rows.append(written)
        return written

    async def read(self, request_id: UUID, after_seq: int = 0) -> list[FactoryEvent]:
        return [item for item in self._events.get(request_id, []) if item.seq > after_seq]

    async def subscribe(self, request_id: UUID, after_seq: int = 0) -> AsyncIterator[FactoryEvent]:
        seq = after_seq
        while True:
            events = await self.read(request_id, after_seq=seq)
            if not events:
                await asyncio.sleep(0.05)
                continue
            for item in events:
                seq = item.seq
                yield item

    async def put_state(self, key: str, value: dict[str, Any]) -> None:
        self._state[key] = dict(value)

    async def get_state(self, key: str) -> dict[str, Any] | None:
        found = self._state.get(key)
        return None if found is None else dict(found)

    async def put_blob(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        if not key or ".." in key:
            raise ContractError(f"invalid blob key {key!r}")
        self._blobs[key] = data
        return key

    async def get_blob(self, key: str) -> bytes:
        try:
            return self._blobs[key]
        except KeyError as exc:
            raise ContractError(f"unknown blob {key}") from exc
