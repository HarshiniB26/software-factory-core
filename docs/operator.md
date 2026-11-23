# Operator guide

## Daily loop

The worker polls Temporal. The API accepts chat requests and signals the workflow when a person answers or approves. Watch `GET /audit` or the console Audit page. Every module call is an append-only event with `module@version`.

## Kill switch

`POST /admin/kill` with an admin token sets `policy.kill_switch`. The next pipeline tick stops the run and marks it `killed`. `POST /admin/resume` clears the switch. Dev mode treats the unsigned local user as admin. Production (`FACTORY_AUTH_MODE=github`) requires a signed admin token.

## Budgets

`budgets.per_run_usd` in config is the cap the model module enforces. The default is 8. A completion past the cap raises and the run fails instead of spending more.

## Approvals

`flags.plan_approval` is `always`, `high_risk`, or `never`. High risk is the default. A high score comes from auth, secrets, migrations, billing, or deletes. Approvers call `POST /requests/{id}/decision`.

## Clarification

The clarifier asks at most 3 questions. The workflow waits up to 3 days and at most 2 rounds, then records the chosen option or the default as an assumption on the pull request. The factory never merges.

## Backups

Nightly `pg_dump` of the factory database is the operator's job. The compose file keeps the data in the `factory-postgres` volume.

## Swap a module

Change `.factory/config.yaml` for one repo, for example `sandbox: sandbox-modal`. Restart the worker so it reloads entry points. The contract tests for that module must already be green.
