"""SQLAlchemy persistence.

The event log is append-only: rows are inserted, and both an ORM listener and a
Postgres trigger reject updates and deletes. Request status, registry rows, and
state are current records and may change. Blobs live on the local disk.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from factory_contracts import (
    AgentSpec,
    ContractError,
    EventDraft,
    FactoryEvent,
    FactoryRequest,
    RequestCreate,
    RequestStatus,
    SkillSpec,
    ThreadMessage,
)
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from factory_core.errors import RegistryError

_JSON = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _semver_key(value: str) -> tuple[int, int, int]:
    major, minor, patch = value.split(".")
    return (int(major), int(minor), int(patch))


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("request_id", "seq", name="uq_events_request_seq"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    seq: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[str] = mapped_column(String(200))
    module: Mapped[str | None] = mapped_column(String(200), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RequestRow(Base):
    __tablename__ = "requests"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text())
    target: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requester: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentRow(Base):
    __tablename__ = "agent_specs"

    agent_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    spec: Mapped[dict[str, Any]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SkillRow(Base):
    __tablename__ = "skill_pins"

    skill_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    spec: Mapped[dict[str, Any]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    role: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text())
    payload: Mapped[dict[str, Any]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserRow(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    roles: Mapped[list[str]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StateRow(Base):
    __tablename__ = "state"

    key: Mapped[str] = mapped_column(String(500), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(_JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@event.listens_for(EventRow, "before_update")
def _reject_event_update(_mapper: object, _connection: object, _target: object) -> None:
    raise RuntimeError("events are append-only")


@event.listens_for(EventRow, "before_delete")
def _reject_event_delete(_mapper: object, _connection: object, _target: object) -> None:
    raise RuntimeError("events are append-only")


def _event(row: EventRow) -> FactoryEvent:
    return FactoryEvent(
        id=row.id,
        request_id=row.request_id,
        seq=row.seq,
        type=row.type,
        module=row.module,
        config_hash=row.config_hash,
        payload=dict(row.payload),
        created_at=_aware(row.created_at),
    )


def _request(row: RequestRow) -> FactoryRequest:
    status = cast(RequestStatus, row.status)
    return FactoryRequest(
        id=row.id,
        title=row.title,
        body=row.body,
        target=row.target,
        requester=row.requester,
        status=status,
        created_at=_aware(row.created_at),
    )


class Database:
    """Storage implementation plus the request and registry records."""

    def __init__(self, engine: AsyncEngine, blob_root: Path) -> None:
        self.engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)
        self._blob_root = blob_root
        self._append_lock = asyncio.Lock()

    def session(self) -> AsyncSession:
        """Open a session. Prefer the repository methods for normal writes."""
        return self._sessions()

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def create_request(self, body: RequestCreate) -> FactoryRequest:
        row = RequestRow(
            id=uuid4(),
            title=body.title,
            body=body.body,
            target=body.target,
            requester=body.requester,
            status="created",
            created_at=utcnow(),
        )
        async with self._sessions() as session, session.begin():
            session.add(row)
        return _request(row)

    async def list_requests(self) -> list[FactoryRequest]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(RequestRow).order_by(RequestRow.created_at.desc())
            )
            return [_request(row) for row in result]

    async def get_request(self, request_id: UUID) -> FactoryRequest | None:
        async with self._sessions() as session:
            row = await session.get(RequestRow, request_id)
        if row is None:
            return None
        return _request(row)

    async def update_status(self, request_id: UUID, status: RequestStatus) -> None:
        async with self._sessions() as session, session.begin():
            row = await session.get(RequestRow, request_id)
            if row is None:
                raise ContractError(f"unknown request {request_id}")
            row.status = status

    async def append(self, event: EventDraft) -> FactoryEvent:
        async with self._append_lock, self._sessions() as session, session.begin():
            current = await session.scalar(
                select(func.max(EventRow.seq)).where(EventRow.request_id == event.request_id)
            )
            seq = 1 if current is None else int(current) + 1
            row = EventRow(
                id=uuid4(),
                request_id=event.request_id,
                seq=seq,
                type=event.type,
                module=event.module,
                config_hash=event.config_hash,
                payload=dict(event.payload),
                created_at=utcnow(),
            )
            session.add(row)
        return _event(row)

    async def list_events(self, limit: int = 100) -> list[FactoryEvent]:
        async with self._sessions() as session:
            rows = list(
                await session.scalars(
                    select(EventRow).order_by(EventRow.created_at.desc()).limit(limit)
                )
            )
        return [_event(row) for row in rows]

    async def read(self, request_id: UUID, after_seq: int = 0) -> list[FactoryEvent]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(EventRow)
                .where(EventRow.request_id == request_id, EventRow.seq > after_seq)
                .order_by(EventRow.seq.asc())
            )
            return [_event(row) for row in result]

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
        async with self._sessions() as session, session.begin():
            row = await session.get(StateRow, key)
            if row is None:
                session.add(StateRow(key=key, value=dict(value), updated_at=utcnow()))
            else:
                row.value = dict(value)
                row.updated_at = utcnow()

    async def get_state(self, key: str) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = await session.get(StateRow, key)
        if row is None:
            return None
        return dict(row.value)

    async def put_blob(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        path = self._blob_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_name(path.name + ".content-type").write_text(content_type, encoding="utf-8")
        return key

    async def get_blob(self, key: str) -> bytes:
        path = self._blob_path(key)
        if not path.is_file():
            raise ContractError(f"unknown blob {key}")
        return path.read_bytes()

    async def put_agent(self, spec: AgentSpec) -> AgentSpec:
        async with self._sessions() as session, session.begin():
            existing = await session.get(AgentRow, (spec.id, spec.version))
            if existing is not None:
                raise RegistryError(f"{spec.id}@{spec.version} already exists")
            session.add(
                AgentRow(
                    agent_id=spec.id,
                    version=spec.version,
                    spec=spec.model_dump(mode="json"),
                    created_at=utcnow(),
                )
            )
        return spec

    async def get_agent(self, agent_id: str, version: str | None = None) -> AgentSpec:
        async with self._sessions() as session:
            result = await session.scalars(select(AgentRow).where(AgentRow.agent_id == agent_id))
            rows = list(result)
        if not rows:
            raise RegistryError(f"unknown agent {agent_id}")
        if version is not None:
            for row in rows:
                if row.version == version:
                    return AgentSpec.model_validate(row.spec)
            raise RegistryError(f"unknown agent {agent_id}@{version}")
        latest = max(rows, key=lambda row: _semver_key(row.version))
        return AgentSpec.model_validate(latest.spec)

    async def list_agents(self, capability: str | None = None) -> list[AgentSpec]:
        async with self._sessions() as session:
            rows = list(await session.scalars(select(AgentRow)))
        grouped: dict[str, list[AgentRow]] = {}
        for row in rows:
            grouped.setdefault(row.agent_id, []).append(row)
        specs = [
            AgentSpec.model_validate(max(group, key=lambda row: _semver_key(row.version)).spec)
            for group in grouped.values()
        ]
        if capability is None:
            return specs
        return [spec for spec in specs if capability in spec.capabilities]

    async def put_skill(self, spec: SkillSpec) -> SkillSpec:
        async with self._sessions() as session, session.begin():
            existing = await session.get(SkillRow, (spec.id, spec.version))
            if existing is not None:
                raise RegistryError(f"{spec.id}@{spec.version} already exists")
            session.add(
                SkillRow(
                    skill_id=spec.id,
                    version=spec.version,
                    spec=spec.model_dump(mode="json"),
                    created_at=utcnow(),
                )
            )
        return spec

    async def get_skill(self, skill_id: str, version: str | None = None) -> SkillSpec:
        async with self._sessions() as session:
            result = await session.scalars(select(SkillRow).where(SkillRow.skill_id == skill_id))
            rows = list(result)
        if not rows:
            raise RegistryError(f"unknown skill {skill_id}")
        if version is not None:
            for row in rows:
                if row.version == version:
                    return SkillSpec.model_validate(row.spec)
            raise RegistryError(f"unknown skill {skill_id}@{version}")
        latest = max(rows, key=lambda row: _semver_key(row.version))
        return SkillSpec.model_validate(latest.spec)

    async def list_skills(self) -> list[SkillSpec]:
        async with self._sessions() as session:
            rows = list(await session.scalars(select(SkillRow)))
        grouped: dict[str, list[SkillRow]] = {}
        for row in rows:
            grouped.setdefault(row.skill_id, []).append(row)
        return [
            SkillSpec.model_validate(max(group, key=lambda row: _semver_key(row.version)).spec)
            for group in grouped.values()
        ]

    async def add_message(
        self,
        request_id: UUID,
        role: str,
        kind: str,
        body: str,
        payload: dict[str, Any] | None = None,
    ) -> ThreadMessage:
        row = MessageRow(
            id=uuid4(),
            request_id=request_id,
            role=role,
            kind=kind,
            body=body,
            payload=dict(payload or {}),
            created_at=utcnow(),
        )
        async with self._sessions() as session, session.begin():
            session.add(row)
        return ThreadMessage(
            id=row.id,
            request_id=row.request_id,
            role=row.role,  # type: ignore[arg-type]
            kind=row.kind,  # type: ignore[arg-type]
            body=row.body,
            payload=dict(row.payload),
            created_at=_aware(row.created_at),
        )

    async def list_messages(self, request_id: UUID) -> list[ThreadMessage]:
        async with self._sessions() as session:
            rows = list(
                await session.scalars(
                    select(MessageRow)
                    .where(MessageRow.request_id == request_id)
                    .order_by(MessageRow.created_at.asc())
                )
            )
        return [
            ThreadMessage(
                id=row.id,
                request_id=row.request_id,
                role=row.role,  # type: ignore[arg-type]
                kind=row.kind,  # type: ignore[arg-type]
                body=row.body,
                payload=dict(row.payload),
                created_at=_aware(row.created_at),
            )
            for row in rows
        ]

    async def upsert_user(self, user_id: str, roles: list[str]) -> None:
        async with self._sessions() as session, session.begin():
            row = await session.get(UserRow, user_id)
            if row is None:
                session.add(UserRow(user_id=user_id, roles=list(roles), created_at=utcnow()))
            else:
                row.roles = list(roles)

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = await session.get(UserRow, user_id)
        if row is None:
            return None
        return {"id": row.user_id, "roles": list(row.roles)}

    def _blob_path(self, key: str) -> Path:
        if not key or key.startswith(("/", "\\")) or ".." in Path(key).parts:
            raise ContractError(f"invalid blob key {key!r}")
        root = self._blob_root.resolve()
        path = (root / key).resolve()
        if path != root and root not in path.parents:
            raise ContractError(f"invalid blob key {key!r}")
        return path


def _enable_sqlite(engine: AsyncEngine) -> None:
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn: Any, _record: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


async def connect(
    url: str,
    blob_root: Path | None = None,
    *,
    create_schema: bool | None = None,
) -> Database:
    """Open a database.

    SQLite (tests and the offline demo) creates tables from the models.
    Postgres applies the Alembic migration, which also installs pgvector and
    the append-only trigger.
    """
    engine = create_async_engine(url)
    _enable_sqlite(engine)
    root = blob_root or Path(".factory/blobs")
    root.mkdir(parents=True, exist_ok=True)
    if create_schema is True or (create_schema is None and engine.dialect.name == "sqlite"):
        # Two processes can pass the existence check together on SQLite.
        for attempt in range(3):
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                break
            except OperationalError:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.2)
    elif create_schema is None and engine.dialect.name == "postgresql":
        from factory_core.migrate import upgrade

        await asyncio.to_thread(upgrade, url)
    return Database(engine, root)
