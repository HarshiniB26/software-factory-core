# Self monitoring and bounded self healing

## What does a reliable autonomous factory need?

### Takeaway
The factory must observe its own workflow and external coding runtime, classify failures, and recover only operations that are safe to repeat. Durable orchestration is a foundation, not proof of exactly-once external side effects or correct generated code.

### Cited Findings
- Temporal recommends idempotent Activities because attempts can execute more than once; a worker may finish an external operation and crash before reporting completion. The documentation recommends smaller recovery units and heartbeat checkpoints for long work. — [Temporal Activities](https://docs.temporal.io/activities), [Activity definition](https://docs.temporal.io/activity-definition)
- Transient, rate-limit/intermittent and permanent failures require different treatment; Temporal supports explicit retry policies, non-retryable errors and compensation patterns. — [Temporal Python error handling](https://docs.temporal.io/develop/python/best-practices/error-handling)
- A heartbeat timeout does not create heartbeat calls, and activity timeout does not automatically stop an already-running external MCP request. — [Temporal MCP integration](https://docs.temporal.io/develop/python/integrations/mcp)
- Monitoring should distinguish latency, traffic, errors and saturation. Alerting should target actionable user-impacting conditions; SLO/error-budget alerts should balance precision, recall and detection/reset time. — [Google SRE monitoring](https://sre.google/sre-book/monitoring-distributed-systems/), [SLO alerting](https://sre.google/workbook/alerting-on-slos/)
- OpenTelemetry defines telemetry signals including traces, metrics and logs. Its Collector receives, processes and exports telemetry; naming a stdout JSON writer “OtelExporter” does not create an end-to-end observability pipeline. — [OTel signals](https://opentelemetry.io/docs/concepts/signals/), [Collector](https://opentelemetry.io/docs/collector/)

### Inferences
- Recommended monitoring dimensions: queue age; active and waiting runs; worker liveness; actual coding-session progress; stage latency; dependency failures; retries/repair rounds; CPU/memory/disk/workspace saturation; token/cost availability; and PR/verification outcomes. Correlate tenant/repository/request/workflow/activity/thread/commit IDs. These are proposed factory metrics, not implemented metrics.
- A progress poll returning “session running” is liveness evidence at best, not evidence that useful work advanced. Persist a last meaningful event/checkpoint plus timestamps and detect stale progress independently.
- Safe healing policy: backoff for transient infrastructure faults; bounded test/review repair with unchanged acceptance gates; reconciliation for unknown side effects; human escalation for missing permissions, unresolved product choices, unsafe migrations and exhausted attempts. Never silently reduce tests/security gates to obtain a pass.

### Gaps
- No universal numeric timeout/SLO is justified by the sources for this project; choose values after observing real workloads and failure drills.
- Provider charge enforcement/usage interfaces depend on the deployed T3/provider contract and have not been qualified here.

## What is implemented and what is missing in this repository?

### Takeaway
The live code has useful supervision and a bounded code-repair loop. It does not yet implement an independently monitored, automatically recoverable factory.

### Cited Findings
- Implemented in source: stage-state persistence; pending-operation intent before T3 start/send and PR publication; exact branch/SHA checks; PR reuse lookup; review/verification feedback into implementation with two total repair rounds; a one-hour run deadline; T3 turn timeout; kill-switch polling and attempted interruption. These are source-inspected capabilities, not a claim of credentialed live qualification. — [Live state machine](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py), [T3 adapter](/Users/Harshini.Battula/software-factory-core/modules/harnesses/src/factory_harnesses/t3/__init__.py)
- Unknown operations fail with a reconciliation-required error. There is no automated reconciling controller. Failed live calls generally become a failed result dictionary in `service.tick`; returning a dictionary is not a thrown Activity failure that Temporal will automatically retry. — [Service live branch](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/service.py:106), [Recovery limitations](/Users/Harshini.Battula/software-factory-core/docs/live-runtime.md)
- `pipeline_tick` has no `activity.heartbeat` calls. Workflow invocation configures a 15-minute start-to-close timeout but no heartbeat timeout or custom retry classification. T3 polling emits a generic progress message every two seconds, and the live state machine does not persist those generic progress events. — [Activities](/Users/Harshini.Battula/software-factory-core/apps/worker/src/factory_worker/activities.py), [Workflow](/Users/Harshini.Battula/software-factory-core/apps/worker/src/factory_worker/workflows.py), [Polling](/Users/Harshini.Battula/software-factory-core/modules/harnesses/src/factory_harnesses/t3/__init__.py:131)
- The observability module writes JSON lines to stdout and retains an in-process list. The live state machine records database events but does not call this exporter; the exporter call found in `service.py` belongs to the legacy module pipeline. — [Exporter](/Users/Harshini.Battula/software-factory-core/modules/obs-otel/src/factory_obs_otel/__init__.py), [Live state machine](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py)
- The workflow unconditionally assigns its query status and return value to `completed` after a terminal pipeline result. Database status preserves failed/killed, but Temporal query state loses that outcome. This discrepancy should be corrected before using workflow status for monitoring. — [FactoryRequestWorkflow](/Users/Harshini.Battula/software-factory-core/apps/worker/src/factory_worker/workflows.py)
- Wait semantics are inconsistent: Temporal permits questions/approval to wait three days, but the live state machine deadline is one hour including that wait; a later answer can fail as wall-clock budget exhausted. — [Workflow waits](/Users/Harshini.Battula/software-factory-core/apps/worker/src/factory_worker/workflows.py), [Run deadline](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py:174)

### Inferences
- Priority reliability slice: outcome truthfulness; distinct active-execution versus human-wait deadlines; activity heartbeats and worker-loss detection; typed retry classes; independent stale-run reconciler with leases/fencing; idempotent external operations; real telemetry export and actionable alerts.
- Recovery acceptance tests should crash the worker immediately before and after thread launch/send, commit/push and PR creation, then prove no duplicate coding session or PR, no double publication, retained verified SHA, and correct final status. Also test provider rate limiting, credential expiry, unavailable GitHub, stuck tools, disk exhaustion and unsuccessful interruption.

### Gaps
- No heartbeat dashboard, alert destination, runbook-driven recovery service, production backup/restore drill, saturation admission control or automatically exercised fault matrix was found in the reviewed live path.
- The existing test suite uses controlled T3/GitHub boundaries. A real end-to-end failure drill remains necessary before autonomy claims.

## Does factory self healing mean the generated applications self heal?

### Takeaway
No. Recovering a coding run is distinct from operating and healing the delivered product. Full SDLC scope needs explicit build/release/deploy/observe/rollback adapters and policies beyond the current PR boundary.

### Cited Findings
- The live factory intentionally stops at a PR and prohibits merge/deploy actions. There are no live deployment or postdeployment health/rollback stages in this state machine. — [Live runtime lifecycle](/Users/Harshini.Battula/software-factory-core/docs/live-runtime.md), [State machine](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py)
- Google SRE describes canaries as a partial, time-limited rollout evaluated against a control. Health evaluation can pause/roll back a bad release before broader exposure; reproducible builds and automated release artifacts form part of release engineering. — [Canarying releases](https://sre.google/workbook/canarying-releases/)
- Rollback must be safe and appropriate; rolling back a binary alone may not repair data corruption. — [Google SRE on-call](https://sre.google/workbook/on-call/)

### Inferences
- Recommended product-recovery scope: observe production signals, correlate them to release/commit, create a deduplicated incident, execute preapproved mitigation such as a feature-flag rollback or reversible canary rollback, then open a tested repair PR. Do not give a generic coding agent unrestricted production modification authority.
- For modernization, track behavior compatibility, migration checkpoints, expand/contract data transitions, shadow/canary comparison and tested rollback/roll-forward choices. Destructive schema/data changes need separate controls from ordinary code repair.
- Learning should propose versioned skill/policy changes and evaluate them against held-out regressions before promotion; “self-healing” must not silently rewrite its own safeguards.

### Gaps
- Neither product-level observability/deployment adapters nor migration rollback qualification are implemented here. Their design depends on the target hosting/data platforms and cannot be claimed universally from one coding pipeline.
