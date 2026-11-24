# Setup

## Machine

Python 3.12, uv, and Docker. Temporal and Postgres come from `deploy/compose/docker-compose.yml`. The console is a separate Vite app.

```bash
uv sync --all-packages --group dev
cp .env.example .env
docker compose -f deploy/compose/docker-compose.yml up -d
set -a && source .env && set +a
uv run alembic -c packages/core/alembic.ini upgrade head
uv run factory-worker
uv run factory-api
cd frontend/console && npm install && npm run dev
```

The API is `http://127.0.0.1:43123`. The console is `http://127.0.0.1:43124` and proxies `/api` to the API.

Without Docker:

```bash
export FACTORY_DATABASE_URL=sqlite+aiosqlite:///./.factory/local.db
```

You still need Temporal on `FACTORY_TEMPORAL_ADDRESS` (default `localhost:7233`).

## What runs with no keys

`FACTORY_AUTH_MODE=dev` signs in anyone who calls `/auth/dev-login`. Version control, harnesses, and the model gateway stay on their fixture paths. The pipeline still clarifies, plans, opens a pull request record, and stops. It does not merge.

## One command

`make up` starts compose, runs migrations when `FACTORY_DATABASE_URL` is Postgres, then starts the worker, the API, and the console. Process ids are in `.factory/pids`. `make doctor` checks Python, git, the Docker daemon, the sandbox image, and, when `FACTORY_AUTH_MODE=github`, the GitHub App id, private key, and OAuth client.

```bash
make sandbox-image
make doctor
make up
```

## Connect GitHub

1. On GitHub, create a GitHub App. Name the slug you want in the install URL, and set `FACTORY_GITHUB_APP_SLUG` to that slug.
2. Callback URL: `http://127.0.0.1:43123/auth/github/callback`.
3. Permissions, and nothing else: Metadata read, Contents write, Pull requests write, Checks read, Statuses read, Actions read. Do not grant Administration, Workflows, Secrets, or Members. The factory never merges.
4. Copy the App's client id and client secret into `FACTORY_GITHUB_CLIENT_ID` and `FACTORY_GITHUB_CLIENT_SECRET`. Copy the App id and the PEM private key into `FACTORY_GITHUB_APP_ID` and `FACTORY_GITHUB_APP_PRIVATE_KEY`. Set `FACTORY_SECRET_KEY` to a long random string. That key encrypts the GitHub user token at rest.
5. In the console, choose Connect GitHub. GitHub's login and authorize page opens. After you return, the picker lists the local sample and the repositories the App installation can access. Add repositories opens `https://github.com/apps/<slug>/installations/new`.

## Going live

1. Create one GitHub App. Use that App's client id and client secret for user login, so you do not create a second OAuth app. Set the callback to `http://127.0.0.1:43123/auth/github/callback` (or `FACTORY_GITHUB_REDIRECT_URI`). In the console, Connect GitHub opens GitHub's own authorize page. The callback stores the user token encrypted with `FACTORY_SECRET_KEY` (or `FACTORY_SESSION_SECRET` if that is unset). The token is not sent to the browser. The factory lists repos through `/user/installations` and `/user/installations/{id}/repositories`, so it only sees repositories the App is installed on. Set `FACTORY_GITHUB_APP_ID`, `FACTORY_GITHUB_APP_PRIVATE_KEY`, `FACTORY_GITHUB_APP_SLUG`, `FACTORY_GITHUB_CLIENT_ID`, and `FACTORY_GITHUB_CLIENT_SECRET`. The session redirect goes to `FACTORY_CONSOLE_URL` with `?token=`. Roles come from `FACTORY_ADMIN_USERS` and `FACTORY_APPROVER_USERS` (comma-separated GitHub logins). Everyone else is a requester.
2. Permissions, and nothing else:
   - Metadata: Read
   - Contents: Read and write
   - Pull requests: Read and write
   - Checks: Read
   - Commit statuses: Read
   - Actions: Read
   - Issues: Read and write, only if `intake-github-issues` is selected
   - Repository creation: only if you set `FACTORY_GITHUB_ALLOW_CREATE_REPO=1`
   - Do not grant Workflows, Administration, Secrets, or organization Members
3. Install the App on the pilot repositories only. Protect the default branch so the App cannot merge.
4. Put the App id, the PEM private key, and the webhook secret in the environment. Never commit them.
5. Point `FACTORY_LITELLM_URL` at a LiteLLM proxy and set `FACTORY_LITELLM_API_KEY`. Set `FACTORY_LITELLM_EMBEDDED=1` only if you want this process to call `litellm.acompletion` itself (`uv pip install litellm` first). Set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` for the live harnesses. Install the SDKs once with `uv pip install -e 'modules/harnesses[claude,codex]'`, then smoke them with `uv run python scripts/smoke_claude.py`, `scripts/smoke_codex.py`, and `scripts/smoke_litellm.py`. Each script exits 2 when its key is missing and does not call a provider.
6. In the target repo `.factory/config.yaml`, select `vcs-github`, `harness-claude-code`, `harness-codex`, `model-litellm`, `sandbox-docker`, and the scanner gates (`gate-semgrep`, `gate-gitleaks`, `gate-trivy`, `gate-osv`, `gate-tests`). Leave fakes in place until those variables are set. The modules detect missing keys and keep the fixture behavior. See `docs/sandbox.md` for Docker Desktop on Mac, Windows, and Linux.
7. Set `FACTORY_AUTH_MODE=github` before anyone else can reach the API. Dev login is rejected in that mode. Behind Cloudflare Access, set `FACTORY_CF_ACCESS_TEAM` and `FACTORY_CF_ACCESS_AUD`. The API verifies `Cf-Access-Jwt-Assertion` against the team JWKS. `FACTORY_CF_ACCESS_PEM` is the local-test public key.
8. Webhook URL for issues and checks: `POST /intake/github`, secret `FACTORY_GITHUB_WEBHOOK_SECRET`.
9. Build the sandbox image (`make sandbox-image`) so the gates run Semgrep, gitleaks, Trivy, OSV-Scanner, pytest, and ruff inside the container. If a binary is missing, the pull request says `tool unavailable, pattern fallback`.
