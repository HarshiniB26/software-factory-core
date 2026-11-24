# Software factory lifecycle coverage

## What capabilities should cover the SDLC across project types?

### Takeaway
A request-to-PR engine covers only part of the SDLC. A credible SDLC factory needs requirements and acceptance evidence, design/context, implementation, continuous quality/security, build artifacts, controlled release, deployment checks and operational feedback; one generic coding prompt is insufficient.

### Cited Findings
- DORA defines continuous delivery around safely releasing changes and keeping software deployable; it identifies test automation, CI, deployment automation, pervasive security and version control as supporting capabilities. This applies to existing systems, schema changes and new applications, not only greenfield web apps. — [DORA continuous delivery](https://dora.dev/capabilities/continuous-delivery/)
- DORA recommends continuous testing and automated unit/acceptance checks. For brownfield systems it recommends beginning with a small number of high-value acceptance tests and adding tests around changed functionality, rather than blocking delivery on retrofitting comprehensive coverage. — [DORA test automation](https://dora.dev/capabilities/test-automation/)
- Deployment automation needs versioned packages, configuration, environment preparation and deployment smoke tests; reliable steps should support safe repetition and environment recovery. — [DORA deployment automation](https://dora.dev/capabilities/deployment-automation/)
- Small, testable, independently useful changes shorten feedback and help counter AI-driven delivery instability. End-to-end feedback extends beyond generated code into deployed behavior. — [DORA small batches](https://dora.dev/capabilities/working-in-small-batches/)
- GitHub recommends project-specific instructions describing build/test/validation and retaining secure development and review practices for coding agents. Its documentation describes security constraints as execution-environment capabilities, not something prompts alone provide. — [GitHub agent application card](https://docs.github.com/en/copilot/responsible-use/agents)

### Inferences
- Recommended shared lifecycle contract: request/outcomes → acceptance criteria → project context/baseline → design/risk → plan → implement → verify/review → versioned artifact/PR → approved release → deployment verification → runtime feedback → maintenance.
- Use explicit workflow profiles, not different products: greenfield/bootstrap; brownfield feature/bug/refactor; modernization/migration. A single persistent coding session can execute each profile; neither DORA guidance nor these patterns require agent fan-out.
- MVP boundaries should be explicit. Supporting feature/bug requests through PR is a valid first slice, but calling it full SDLC support would obscure absent release and operations capabilities.
- Greenfield profile should establish requirements, architectural decisions, approved scaffold/dependencies, first build/test/CI path, deployment shape and observability baseline. Brownfield profile should establish relevant behavior, dependency/contract impact and baseline failures before planning.

### Gaps
- These sources are engineering guidance and vendor documentation, not a universal software-factory certification standard. No exhaustive claim about researching “everything” is warranted.

## What does modernization require beyond ordinary brownfield coding?

### Takeaway
Modernization is a program of behavior-preserving or deliberately behavior-changing increments with coexistence and cutover, not simply rewriting files in a newer language. Source inspection is necessary but runtime and business context are also needed.

### Cited Findings
- Strangler Fig modernization identifies desired outcomes, decomposition and seams, then replaces behavior incrementally while legacy/new components coexist. It reduces risk and permits earlier feedback; preserving all legacy behavior blindly is not necessarily desirable. — [Martin Fowler, Strangler Fig](https://martinfowler.com/bliki/StranglerFigApplication.html)
- Branch by Abstraction introduces an interface that allows old/new suppliers to coexist, progressively moves consumers, compares implementations where useful, and keeps the system buildable and releasable during replacement. — [Martin Fowler, Branch by Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html)
- Legacy seams enable test substitution, observability probes and routing to replacement modules. — [Martin Fowler, Legacy Seam](https://martinfowler.com/bliki/LegacySeam.html)
- Thoughtworks' reported modernization work emphasizes reverse engineering to understand existing requirements and distinguish behavior to retain, remove or introduce. It combines static understanding with runtime information, since source analysis alone cannot establish whether whole endpoints or batch jobs are actually used. — [Thoughtworks authors, Legacy Modernization meets GenAI](https://martinfowler.com/articles/legacy-modernization-gen-ai.html)

### Inferences
- A modernization profile should produce: estate/dependency inventory; business outcomes; current behavior and data contracts; target design; incremental migration units; old/new compatibility tests; coexistence strategy; backfill/cutover checks; rollback/recovery plan; retirement criteria.
- Do not default to microservices, a full rewrite, or copying every legacy behavior. Select a strategy from evidence and business goals.
- Program state must persist across PRs and releases, tracking which capabilities/data/consumers migrated and what remains. One plan and one PR cannot represent a long migration safely.
- Database modernization needs separate application rollback versus data-recovery reasoning; reverting code alone may not reverse data transformations.

### Gaps
- No repository-specific modernization scenario, legacy target system, data estate or deployment platform was supplied, so strategy suitability cannot be proven for a concrete modernization job.

## How does the current implementation compare, and what is a defensible MVP?

### Takeaway
Current source implements a request-to-PR control path primarily for an existing Git repository. It is not yet a full SDLC system and lacks explicit greenfield and modernization workflows. Implemented code must be distinguished from real credentialed end-to-end qualification.

### Cited Findings
- The live state machine prepares a selected existing branch, starts one T3 session, performs discovery before planning, handles clarification/approval, then implementation, self-review, verification and GitHub publication. — [autonomous.py](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py)
- Discovery checks that named files exist and that the working tree/HEAD are unchanged. Its schema accepts findings, file names and questions; it does not require independent file-read receipts, a repository map, baseline test results, dependency inventory or acceptance-criterion evidence. — [autonomous.py](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py)
- Skills are selected from a static stage mapping: debugging/root-cause for all discovery, planning guidance for planning, TDD/verification for implementation, blast-radius/verification for review. There is no project-type-aware discovery or modernization selection. — [skills.py](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/skills.py)
- Live setup clones an existing selected branch and the discovery schema requires at least one real file. The live guide explicitly states repository creation/greenfield bootstrapping is absent and local-only runs cannot publish a GitHub PR. — [live runtime guide](/Users/Harshini.Battula/software-factory-core/docs/live-runtime.md)
- Verification executes approved argv commands and binds exit-code/output-hash records to HEAD, with bounded repair feedback. It does not automatically watch PR CI or supply deployment/release/production-feedback stages. — [autonomous.py](/Users/Harshini.Battula/software-factory-core/packages/pipeline/src/factory_pipeline/autonomous.py)
- The guide identifies single-host trust, self-review, no hard live dollar budget, manual crash reconciliation and incomplete live qualification as limitations. T3 being installed/reachable (per the conversation) removes only an availability blocker, not the need for live coding/GitHub validation. — [live runtime guide](/Users/Harshini.Battula/software-factory-core/docs/live-runtime.md)

### Inferences
- Priority 1: prove one live brownfield change on a dedicated repo; include wrong branch, existing failure, agent failure, test failure, human rejection, duplicate publication and interruption cases.
- Priority 2: introduce versioned project/workflow profiles and a persisted context/baseline/acceptance evidence contract. Add a true greenfield bootstrap path and small-batch migration program model.
- Priority 3: extend lifecycle past PR creation through CI/review monitoring, artifact production, environment promotion, smoke tests and rollback planning, preserving human production authority.
- Priority 4: integrate runtime feedback into new maintenance requests, with scoped, evidence-driven remediation. Distinguish healing the factory infrastructure, repairing generated code, and recovering deployed applications.
- A strong MVP can support a narrow representative case for all three project types without claiming arbitrary language/framework/estate coverage. A declared support matrix and repeatable scenario suite are more credible than a universal promise.

### Gaps
- I did not run a credentialed T3/GitHub task. Findings about behavior are source inspection, not live qualification.
- This research does not independently assess monitoring/recovery/security modules beyond lifecycle boundaries; those are adjacent research scopes.
