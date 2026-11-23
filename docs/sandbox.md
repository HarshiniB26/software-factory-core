# Docker sandbox

`sandbox-docker` runs each step in its own container from `factory-sandbox:local`. The image is `modules/sandboxes/image` and already contains Semgrep CE, gitleaks, Trivy, OSV-Scanner, pytest, and ruff.

```bash
make sandbox-image
```

What the container does:

- Clones the target (a local path or a bare repo mounted at `/origin`) into `/work/repo`.
- Runs as the host user, or as uid 1000 when the host user is root. Capabilities are dropped, `no-new-privileges` is set, memory is 1g, CPU is 1, and the pid limit is 256.
- Starts an allowlist proxy on `127.0.0.1:3128`. Allowed hosts are PyPI, GitHub, and `api.osv.dev`. Other egress is refused.
- Blanks environment variables whose names contain `KEY`, `TOKEN`, `SECRET`, `PASSWORD`, or `CREDENTIAL` before every command. Secrets stay on the host.
- Removes the container when the step's gates finish.

`FACTORY_SANDBOX_ENGINE=auto` uses the `sbx` CLI when it is on `PATH` (same `run` / `exec` / `rm` flags as Docker). Set `FACTORY_SANDBOX_ENGINE=docker` to force the Docker CLI. `FACTORY_DOCKER_SANDBOX=host` skips containers and records `host-fallback` on the pull request. Pattern checks run only when the scanner binary is missing, and the pull request says `tool unavailable, pattern fallback`.

## Docker Desktop

Install [Docker Desktop](https://docs.docker.com/desktop/) and leave the engine running.

- macOS: Docker Desktop, Apple silicon or Intel. The default socket is enough. Build the image with `make sandbox-image` from the repo root, then `make up`.
- Windows: Docker Desktop with the WSL 2 backend. Run the factory from the WSL distro, not from a mapped `C:` path, so the bind mounts the sandbox uses stay on the Linux filesystem. Put your user in the `docker` group inside that distro.
- Linux: Docker Desktop or Docker Engine. If you use Engine, add your user to the `docker` group and start the service (`sudo systemctl enable --now docker`). The factory does not need the daemon to run as root inside the sandbox container.

`factory doctor` reports whether the daemon answers and whether `factory-sandbox:local` is present. At large companies Docker Desktop may be a paid product. Docker Engine is the free alternative on Linux.
