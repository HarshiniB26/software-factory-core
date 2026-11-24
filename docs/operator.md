# Operator guide

For live requests use [the live runtime guide](live-runtime.md). The legacy registry, role fan-out, clarification flags and dollar-budget descriptions below apply to the explicit demo/module pipeline, not the new single-session live runtime.

## Daily loop

The worker polls Temporal. The API accepts chat requests and signals the workflow when a person answers or approves. Watch `GET /audit` or the console Audit page. Every module call is an append-only event with `module@version`.

## GitHub in the composer

The new-issue box sends the connected repository as the request target. `GET /repos` includes `oauth`, which is true only when `FACTORY_GITHUB_CLIENT_ID` and `FACTORY_GITHUB_CLIENT_SECRET` are both set. Connect GitHub then goes to GitHub's authorize page. The user token is encrypted with `FACTORY_SECRET_KEY` or `FACTORY_SESSION_SECRET` and is not returned to the browser. Granted repos come from the GitHub App installation. `GET /repos/branches` lists branches for a granted repo, and the composer preselects the default branch. Without the OAuth app the popover tells the operator to use Settings → GitHub, and the local sample can still be selected.

## Kill switch

`POST /admin/kill` with an admin token sets `policy.kill_switch`. The next pipeline tick stops the run and marks it `killed`. `POST /admin/resume` clears the switch. Dev mode treats the unsigned local user as admin. Production (`FACTORY_AUTH_MODE=github`) requires a signed admin token.

## Budgets

`budgets.per_run_usd` in config is the cap the model module enforces. The default is 8. A completion past the cap raises and the run fails instead of spending more.

## Approvals

`flags.plan_approval` is `always`, `high_risk`, or `never`. High risk is the default. A high score comes from auth, secrets, migrations, billing, or deletes. Approvers call `POST /requests/{id}/decision`.

## Clarification

`flags.clarification` is `major` (default), `always`, or `assume`. Settings has the same control. `major` asks in the Inbox only when scope, data, API, security, or cost is ambiguous. `always` parks instead of guessing. `assume` records the open points and continues. The clarifier asks at most 3 questions, for at most 2 rounds. The factory never merges.

## Planner, registry, and harnesses

The planner asks the model module for a TaskDAG. Each step carries a role and free-text capabilities. The registry embeds that need and compares it with each agent's prompt, skills, tools, harness, model tier, and evals. The model then chooses REUSE, UPGRADE, or CREATE. The reason is stored on `agent.decision`. New agents stay draft until held-out evals pass. A step runs on the harness named for its role in Settings. A named harness that is not installed fails the step. The reviewer role has its own harness and model. Demo runs load only when `FACTORY_DEMO_SEED=1`.

## Backups

Nightly `pg_dump` of the factory database is the operator's job. The compose file keeps the data in the `factory-postgres` volume.

## Swap a module

Change `.factory/config.yaml` for one repo, for example `sandbox: sandbox-modal`. Restart the worker so it reloads entry points. The contract tests for that module must already be green.
