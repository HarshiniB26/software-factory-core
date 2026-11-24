# Enterprise controls and evaluations

## What makes an enterprise SDLC factory more than a coding loop?

### Takeaway
Security, evidence and operational response must cover the lifecycle, not only PR generation. The repository presently implements part of a change-to-PR workflow; its own live-runtime guide explicitly excludes multi-tenant isolation and greenfield bootstrap.

### Cited Findings
- NIST SSDF 1.1 is final; its practice groups cover organizational preparation, software protection, secure production and vulnerability response. NIST's publication inventory lists SSDF 1.2 as a draft, so do not claim draft requirements are a finalized compliance baseline. [SSDF overview](https://csrc.nist.gov/projects/ssdf); [publication inventory](https://csrc.nist.gov/Projects/ssdf/publications).
- NIST identifies secure development environments, component provenance and tracking security requirements/risks/design decisions among SSDF practices. [SSDF project](https://csrc.nist.gov/projects/ssdf).
- Current code supplies pinned skills, captures stage events and verifies a commit before publication. Its documentation explicitly says local host execution, no hard dollar cap, no automatic reconciliation, self-review, and no repository creation/greenfield bootstrap. [Local runtime guide](/Users/Harshini.Battula/software-factory-core/docs/live-runtime.md); [live implementation](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py).

### Inferences
- Define requirements-to-evidence traceability: request, acceptance criteria, risk decisions, inspected commit, plan approval, actual changes, independent verification, PR, release and incident records. A single request loop cannot establish full SDLC coverage.
- Greenfield needs architecture/security decisions, approved templates, repository bootstrap and CI before feature work. Brownfield needs baseline tests, dependency/ownership mapping and compatibility evidence. Modernization needs behavior-preservation contracts, incremental migration slices, data validation, rollback/reversibility and performance checks. These are proposed product requirements, not capabilities established by the current code.
- Keep deployment and production intervention as separate policy-gated extensions; creating a PR is not a release, and bounded code repair is not production self-healing.

### Gaps
- No audit or deployment evidence establishes conformance to any enterprise standard; use “aligned with selected practices” only after implementing and verifying mappings.

## Which controls belong in executable policy rather than skills?

### Takeaway
Skills are useful work instructions; enforced permissions must bound what the agent can reach even when instructions are bypassed.

### Cited Findings
- OWASP's current agentic risk set includes goal hijack, tool misuse, privilege abuse, agentic supply-chain vulnerabilities, unexpected execution, context poisoning and cascading failures. [Agentic Top 10](https://genai.owasp.org/top-10-for-agentic-applications-2026/).
- OWASP advises treating natural-language inputs as untrusted, least privilege, approval for high-impact changes, runtime intent checks, auditable goals, monitoring and periodic adversarial tests. [Goal hijack guidance](https://genai.owasp.org/agentic-applications-2026/asi01-agent-goal-hijack/).
- OWASP describes inherited credentials and insufficiently governed agent identity as privilege risks. [Identity and privilege](https://genai.owasp.org/agentic-applications-2026/asi03-identity-and-privilege-abuse/).
- SLSA v1.2 separates provenance authenticity from isolation strength. Its stronger build isolation requirements address cross-run interference, secrets, ephemeral environments and cache poisoning. Provenance must describe the artifact and build, and stronger levels protect its generation from tenant tampering. [SLSA build requirements](https://slsa.dev/spec/v1.2/build-requirements). Source and build provenance are separate concepts. [SLSA provenance](https://slsa.dev/spec/v1.2/provenance).

### Inferences
- Before a team pilot: isolate execution from the control plane, scope filesystem/network access, remove host-wide credentials, issue expiring run-scoped tokens, bind authorization to user/org/repository, and enforce protected-branch/merge boundaries outside prompts.
- Before multiple teams: namespace every request, repository selection, setting, secret, blob and event by tenant; add server-side ownership checks and adversarial cross-tenant tests. A worktree is not an OS security boundary.
- Add enforceable token/dollar/time/concurrency quotas with admission control and reserved spend. If T3 cannot expose/enforce billing, label spend unknown and require a provider-account cap; never present the existing configured budget as a guaranteed ceiling.
- Preserve independent evidence of tested SHA, tool versions, skill/model/runtime versions, commands, outcomes and artifact digests. Do not call simple local content hashes signed provenance, or claim a SLSA level without assessment.
- Skill updates should arrive as reviewed versioned changes, evaluated before promotion. Failure-driven learning must not silently rewrite its own security rules.

### Gaps
- Exact isolation and billing options depend on deployed T3/provider/runtime capabilities; these were not live-tested in this research.

## How should the factory itself be evaluated before expanding scope?

### Takeaway
The Python regression suite verifies orchestration contracts; it does not measure whether the deployed model+harness reliably solves real engineering work.

### Cited Findings
- Anthropic defines agent evaluations around tasks, repeated trials, graders, traces and final environment outcomes. It distinguishes what an agent claims from the actual resulting state, and evaluates the model and harness together. [Agent evaluations](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).
- The repository explicitly labels its T3/GitHub boundaries in controlled tests simulated and says live compatibility remains unqualified. [Runtime qualification limits](/Users/Harshini.Battula/software-factory-core/docs/live-runtime.md).

### Inferences
- Create separate held-out suites: greenfield bootstrap/build; brownfield bugfix/regression; modernization behavior preservation; security adversarial tasks; and operational fault injection. Include representative languages, monorepos and weak-test repositories before claiming broad support.
- Grade working behavior, acceptance criteria, prohibited changes, relevant tests, changed-file scope, regressions, interruption/recovery, resource usage and evidence accuracy. Use independent checks that the agent cannot weaken, with repeated trials and human calibration of subjective graders.
- Measure completion rate alongside false-success rate, unnecessary human interventions, repair rounds, latency, actual cost when known, and unsafe-action attempts. Promote new models, harnesses, prompts and skills against a versioned baseline.
- Suggested ordering: (1) qualify one brownfield test repository end to end; (2) isolation/authorization/evidence/fault recovery; (3) explicit greenfield and modernization playbooks with dedicated evaluations; (4) CI/release/deploy/observe/rollback integrations under separate permission policies.

### Gaps
- There are no measured real-task success rates for this deployment. Passing 103 contract/regression tests must not be translated into a coding-agent success percentage.
