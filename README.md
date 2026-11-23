# Software factory

An autonomous software factory. A small Python core records what happened, resolves config, and calls modules through stable interfaces. Modules own every vendor. You describe the change in the console. The pipeline clarifies, plans, runs the steps, and opens a pull request. It does not merge.

The default configuration uses in-process fakes, so the whole path runs with no GitHub App and no model keys. Real modules turn on when their environment variables are set. See `.env.example`, `docs/setup.md`, `docs/operator.md`, and `docs/modules.md`.

## Architecture

```text
console / CLI  -->  FastAPI  -->  core (event log, registry, policy, config)
                         |              |
                         |              +--> module loader (entry points + module.yaml)
                         v
                    Temporal workflow
                         |
                         +--> activities append events, which the SSE stream replays
```

The core (`factory_core`) imports `factory_contracts` and the database stack. It does not import Temporal, LiteLLM, GitHub, or a harness SDK. `import-linter` fails CI if it does. Modules are discovered from the `factory.modules` entry-point group. Each one ships a `module.yaml` manifest (`implements: Interface@1`). Nothing imports a module package from the core; the loader imports the class the entry point names.

Config layers, highest priority first:

1. Run override (the `overrides` object on `POST /requests`)
2. Repo file `.factory/config.yaml`
3. Org file (`FACTORY_ORG_CONFIG`, or `.factory/org.yaml` when present)
4. Built-in defaults

Mappings merge. Lists and scalars in a higher layer replace the lower layer. Policy checks the result against each selected module's JSON schema.

Agent and skill records are versioned and immutable. Putting the same `id@version` twice is an error. The planner that creates or upgrades agents is not in this week; the registry only stores specs. See `registry/agents/backend-api.yaml`.

### Module interfaces

| Interface | Week 1 implementation |
| --- | --- |
| Orchestrator | `orchestrator-temporal` (Temporal OSS). Contract tests use `orchestrator-fake`. |
| Storage | SQLAlchemy in the core (Postgres + Alembic, SQLite for tests). `storage-fake` passes the same suite. |
| IntakeSource, Notifier, Clarifier, Planner | Fakes |
| HarnessAdapter, ModelProvider, SandboxProvider, VcsProvider | Fakes |
| QualityGate, SkillSource, EvalRunner | Fakes |
| ObservabilityExporter, AuthProvider, SecretsProvider | Fakes |

The console is a client, not a module interface. Its directory is a placeholder.

## Layout

```text
apps/api          FastAPI
apps/worker       Temporal worker and the no-op workflow
apps/cli          Typer client; HTTP only
packages/core     Event log, registry, policy, loader, config
packages/contracts
packages/contract-tests
packages/sdk
modules/fakes
modules/orchestrator-temporal
frontend/console  placeholder
deploy/compose    Postgres + pgvector, Temporal
registry          example agent and skill YAML
examples/.factory/config.yaml
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 0.13 or newer
- Docker, when you want Postgres and Temporal rather than the SQLite demo path

## Setup

```bash
uv sync --all-packages --group dev
docker compose -f deploy/compose/docker-compose.yml up -d
export FACTORY_DATABASE_URL=postgresql+asyncpg://factory:factory@127.0.0.1:54329/factory
uv run alembic -c packages/core/alembic.ini upgrade head
```

The migration creates the tables, the append-only trigger on `events`, and the `vector` extension. SQLite tests skip that migration and create tables from the models. The ORM also refuses updates to event rows, so the append-only rule holds in both databases.

## Run

```bash
make sandbox-image   # once, when you want real scanner gates
make doctor
make up
```

`make up` is compose, migrations (Postgres only), the worker, the API on port 43123, and the console on port 43124. Without Docker, export `FACTORY_DATABASE_URL=sqlite+aiosqlite:///./.factory/local.db` and start Temporal yourself. Details and the go-live checklist are in `docs/setup.md`. Live harness checks are `scripts/smoke_claude.py`, `scripts/smoke_codex.py`, and `scripts/smoke_litellm.py`.

## Run by hand

Terminal A, after Postgres and Temporal are up:

```bash
uv run factory-worker
```

Terminal B:

```bash
uv run factory-api
```

The API listens on `http://127.0.0.1:43123`. OpenAPI is at `/docs`.

```bash
curl -s http://127.0.0.1:43123/health
curl -s -X POST http://127.0.0.1:43123/requests \
  -H 'content-type: application/json' \
  -d '{"title":"Add health","body":"Add GET /health"}'
# then, with the id from the response:
curl -N http://127.0.0.1:43123/requests/<id>/events
uv run factory requests list
```

`POST /requests` writes `request.created`, starts `NoOpRequestWorkflow`, and the worker appends `workflow.started` and `workflow.completed`. The SSE endpoint replays the log and then waits for new rows, so a reload shows the same history.

Without Docker, point both processes at SQLite:

```bash
export FACTORY_DATABASE_URL=sqlite+aiosqlite:///./.factory/local.db
```

The workflow still needs Temporal at `localhost:7233` (the default `FACTORY_TEMPORAL_ADDRESS`).

## Tests and lint

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run lint-imports
uv run pytest
```

`make lint` and `make test` run the same commands. Postgres coverage is the Alembic test, enabled with `FACTORY_TEST_POSTGRES=1` and `FACTORY_DATABASE_URL` pointing at a migrated database. The default suite uses SQLite plus Temporal's test server, so it does not need Docker.

## Week 1 choices

- Pyright is the type checker, in strict mode. Reports about unknown types from untyped libraries are turned off; the rest of strict mode stays on.
- The event log and registry live in `factory_core` and use SQLAlchemy, because this week puts persistence in the core. `Storage` is still a protocol, and `storage-fake` passes its contract suite. A `storage-postgres` module can take the SQLAlchemy code later without an API change.
- Fakes stay the default. Docker, GitHub, Claude, Codex, and LiteLLM are installed and selected from config when their credentials are present. The pipeline never merges a pull request.
- The Temporal module is marked `testing: external`, so the in-process contract suite does not try to open a server. The API test starts Temporal's test environment, runs the worker, and reads the SSE stream.
- Feature flags are fields in the resolved config. A Postgres flag table is later.
- Blobs are files under `.factory/blobs`.
- Lists in config replace, they do not concatenate.
- Routes are unauthenticated. Sign-in is a later week; `AuthProvider` exists so that week has a contract to implement.
- The factory never merges. This week never opens a pull request either; the no-op workflow only proves the path from request to events.
