# Runtime qualification record

Date: 2026-11-24. These are bounded qualification cases, not an enterprise certification or a general agent success-rate estimate.

## Real T3 execution

T3 Code 0.1.11 with the installed Personal Codex provider and `gpt-6-luna` completed a disposable-repository task. The adapter created a worktree, the model read README.md and wrote result.txt, and the coordinator independently verified its exact contents. No project source or GitHub repository was changed by this test.

## Real chat-first factory run

Request `5f556659-9c92-42ea-bb2b-c333c8d5e65f` described a change to a tiny standard-library Python application: update a function's return value and its unittest, preserving its signature. No workflow category was selected. The agent inferred brownfield work from the request and code.

The same T3 thread completed discovery, planning, implementation, self-review, coordinator verification and reflection. No product questions or manual plan approval were needed for this routine request. Recorded active execution was about 56 seconds. The verified commit was `db3f05f66dd6d00820517a9f197a4810f4232776`. An independent acceptance command confirmed the requested function behavior after the factory completed.

The run produced workflow improvement candidate `9cd8cdc477895468b0a55cbb3cfec1b9a350f89d745fc22fd845bce4169fb057`. It was proposed, not activated: no claim of measured improvement is made before held-out evaluation and approval.

An earlier automatic-discovery attempt omitted baseline command evidence and correctly failed closed. The schema now requires that evidence for existing repositories and permits one same-session structured-response correction. Test report output written to stderr is now included in new verification evidence hashes; the original qualification stored exit status but its stdout-only hash was empty.

## UI qualification

Playwright exercised the live run approval/evidence screen, runtime provider/model selection, Operations health/improvement view, and chat composer without a workflow selector. The browser tests use controlled API fixtures; they establish UI behavior, not external GitHub correctness. Screenshots were inspected for the live run and Operations views. Production build and frontend unit tests also ran.

## External qualification remaining

A dedicated GitHub repository and working App credentials are required to qualify real clone/PR/check-run/recovery behavior end to end. A deployment environment is required before release, production health and rollback integration can be implemented and tested. Greenfield and modernization contracts/bootstrap have controlled tests; representative real applications and held-out suites remain necessary before broad support claims.

Execution remains on a trusted host. OS isolation, complete tenant IAM, hard dollar limits and statistically meaningful multi-trial agent benchmarks are separate unresolved rollout requirements.
