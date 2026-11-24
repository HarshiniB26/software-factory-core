# Autonomous factory runtime

The product interaction is chat-first: connect a repository, describe the desired outcome, and answer only unresolved product questions. The agent inspects repository evidence and determines the work type internally. There is no workflow selector. Routine work proceeds under the high-risk approval policy; administrators may choose to review every plan. High-risk changes, sensitive paths and creation of a new base branch require approval. The factory never merges or deploys implicitly.

## Start and configure

Install and start T3 Code on the worker host, sign a provider into T3, and run `uv sync --all-packages --group dev`. Use Settings → Execution runtime to choose an available provider/model. Selections are validated against T3's configured provider instances and current model manifest. Alternatively export `FACTORY_T3_PROVIDER`, `FACTORY_T3_MODEL` and optionally `T3CODE_CLI_PATH`.

Live is the default. `FACTORY_EXECUTION_MODE=demo` explicitly enables the historical simulated module pipeline; fake output is not evidence of live execution. `.factory/config.yaml` selects those legacy demo modules. Live requires `harness-t3` and `skills-git` directly.

`make up` launches the Temporal worker, API, independent monitor and console. The monitor can also run separately with `uv run factory-monitor`. The API binds loopback by default; configure exposure deliberately. Production requires `FACTORY_AUTH_MODE=github`, a strong `FACTORY_SESSION_SECRET` of at least 32 characters, an encryption secret, GitHub App/OAuth credentials, and explicit administrator/approver accounts. Production rejects unsigned bearer strings and expired sessions. Request ownership is enforced server-side; connected repositories are scoped by user. These are single-organization controls, not a completed multi-tenant IAM system.

Configure the existing GitHub settings, sign in, connect a granted repository, and select its base branch. The API freezes that selection into each request. Short-lived installation tokens authenticate clones/pushes/PR calls; tokens are not written into remote URLs or run state. Local repositories support `delivery_target=verified` for qualification without GitHub publication.

## Lifecycle

1. Clone the selected branch and record the starting SHA. Clone failures stop execution; they never silently become an empty repository. An actually empty repository can be initialized for new application work. The plan explicitly discloses creation of its initial base branch; publication creates that branch only if absent, or verifies that its prior initialization succeeded.
2. Start one T3 thread/worktree with explicit provider/model. The same session retains context through subsequent stages. No dynamically created crew or task fan-out is used.
3. Supply verified discovery instructions. The agent reads project guidance, relevant source/tests/configuration, infers the work type and returns structured findings, real file paths, baseline command arrays and any unresolved product questions. Baseline commands are required for existing applications. Discovery is checked for edits. Incomplete structured output gets one bounded correction request; no guessed fallback is substituted.
4. Continue in the same session after answers. Human waiting does not consume active execution budget. Clarification and approval expire after three days without invented answers.
5. Produce an acceptance-driven plan grounded in findings. Existing changes require baseline evidence; new applications require a buildable vertical slice and test/CI/deployment configuration; modernization requires preservation invariants, incremental migration steps and rollback criteria. These are workflow contracts, not proof of compatibility with every language or legacy estate.
6. Apply the approval policy. High-risk plans, sensitive paths and empty-repository base initialization pause. Administrators may require approval of every plan. Routine requests otherwise proceed automatically. Baseline and verification commands appear with the plan.
7. Execute baseline checks, record failures separately, and implement with TDD/verification guidance. Commands use a reduced environment rather than inheriting factory service secrets. Process-group cancellation stops child verification processes too.
8. Review the full change in the same session. Review/test failures feed evidence back into implementation, sharing a two-round repair cap. This is self-review, not independent security review.
9. Commit and execute verification outside the agent's narrative. Require a nonempty actual diff, stable commit and clean worktree. Record command outcomes and output hashes against the exact SHA. Newly discovered sensitive changes require approval before delivery.
10. Push the verified SHA, create/reuse a real GitHub PR, and confirm its head matches. Never merge. Local verification delivery skips publication explicitly.
11. Reflect in the same session and propose a reusable instruction improvement. Reflection is optional and cannot invalidate already delivered work. Proposals do not edit source, skills or policy.

## Skills and improvement

The source loads approved local pins, not arbitrary internet instructions on each run. `registry/skills/pins/integrity.json` binds all assets to hashes. Loading rejects wrong refs, missing assets and changed content. Stage messages include full skill instructions and supporting Markdown references. `skills.applied` events record upstream refs, content hashes and stage.

Superpowers pins/supporting files were checked against `22f0b463e7a5e579904dd6211a520321035526f7` of https://github.com/obra/superpowers. Existing attributed PStack pins supply root-cause and blast-radius guidance. Skill suggestions cannot override factory stage restrictions, permissions or publication boundaries.

Terminal outcomes preserve model/provider, active duration, repairs, verification, skill receipts and applied candidate identity. Reflection creates immutable, hash-bound candidates. Operations displays their evidence and evaluation history. New requests freeze the active candidate for the inferred work type; in-flight requests do not change when a new candidate is activated.

Configure a trusted local JSON suite through `FACTORY_EVAL_SUITE`. Each case contains `id`, `kind` (`functional`, `security`, `recovery`), `repository`, `branch`, `request`, `project_type`, independent `checks` argv arrays, and optional known product `answers`. The suite is operator-controlled, never supplied by candidate prose or client scores. Do not place private graders in the agent worktree. The current trusted-host architecture does not cryptographically isolate graders from the agent.

An administrator queues evaluation from Operations. The monitor executes paired baseline/candidate runs through the actual factory with local verification delivery, then executes the suite's independent checks. At least three cases are required to evaluate. Activation requires at least 30 paired distinct cases, all candidate cases passing, at least three security and three recovery cases, an actual improvement over baseline, no >20% active-duration regression, content/suite binding, and an unchanged baseline. Atomic compare-and-swap prevents conflicting activations. Only an administrator activates or rolls back a candidate. No automatic source/policy self-modification occurs. Hard spending caps and statistical confidence across repeated stochastic trials are not implemented by this gate.

## Monitoring and recovery

Every tick owns an atomic expiring lease. Heartbeats renew ownership, and state writes verify the lease in the same database transaction. A stale worker cannot overwrite a replacement's run state. Temporal activities heartbeat and retry at most three times. Workflow query/return values preserve failed/killed/completed status.

The independent monitor records stale execution, uncertain side effects and unchanged session snapshots. A changing T3 snapshot indicates activity, not necessarily useful progress. Alerts are deduplicated, shown in Operations, can be acknowledged, and resolve when their condition clears. `/monitor/metrics` exposes authenticated Prometheus text metrics. The monitor also detects lost evaluator heartbeats. External notification delivery and SLO policies require deployment-specific configuration.

Operation intents and unique instruction markers are persisted before launch/send/publication. A retry with a known thread resumes only after proving the pending instruction reached that thread. It does not blindly send a second copy. Unidentified launches require manual reconciliation. PR/base-branch publication checks actual GitHub/Git state. Operations provides an administrator-only reconcile/resume action for known operations after the run lease is free.

The one-hour budget counts active tick execution, excluding human waits. T3 turns also have `FACTORY_HARNESS_TIMEOUT` (default 600 seconds). Kill checks run between stages and during session progress. Interruption uses short-lived scoped T3 MCP sessions and waits for inactivity. If it cannot confirm interruption, the operator must inspect T3. Leases fence database writes; they do not fence every external side effect or isolate the remote coding process.

## CI feedback

The independent monitor observes check runs and commit statuses on the exact verified SHA after PR delivery. Incomplete or truncated reports are not treated as passing. Failed checks can resume the existing thread through the normal review/verification/publication path, at most twice. Unknown infrastructure results are retried with cooldown rather than reported as success. Exhausted repairs create an actionable CI alert. No merge is performed. CI integration has controlled API tests; live GitHub qualification still needs a dedicated test repository.

## Qualification and remaining boundaries

A real T3 `0.1.11` / `gpt-6-luna` task was qualified in a disposable repository: correct worktree, actual file edit and independent file verification. A complete local brownfield run also passed discovery, planning, implementation, self-review, coordinator verification and reflection, producing a verified commit and a real improvement proposal. Chat-first automatic classification is separately exercised by live qualification and contract tests; see [the qualification record](qualification.md) for the latest result. This does not establish success across arbitrary projects.

Execution remains a trusted single-host pilot. OS/container isolation, full tenant/IAM separation, verified billing/hard dollar caps, broad held-out benchmarks, independent reviews, GitHub credentialed end-to-end publication/CI qualification, release/artifact adapters, production deployment/health/rollback, data recovery and organization-specific compliance remain rollout requirements. A deployment target and dedicated GitHub test repository are required before those external paths can be completed and qualified. Factory recovery and code repair are different from healing a deployed product.
