"""Docker sandbox. Uses a real container when the daemon is up, otherwise a host workspace."""

import os

from factory_contracts import SandboxHandle, SandboxSpec

from factory_sandboxes.docker_engine import DockerEngine, docker_ready
from factory_sandboxes.host import HostSandbox


class DockerSandbox:
    """One clone per step. Secrets are not copied into the container environment."""

    def __init__(self) -> None:
        forced = os.environ.get("FACTORY_DOCKER_SANDBOX", "auto")
        use_docker = forced == "docker" or (forced == "auto" and docker_ready())
        self._impl: DockerEngine | HostSandbox
        if use_docker:
            self._impl = DockerEngine()
        else:
            self._impl = HostSandbox(backend="docker")
        self.backend = "docker" if use_docker else "host-fallback"

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        return await self._impl.create(spec)

    async def exec(self, sandbox_id: str, command: list[str]):
        return await self._impl.exec(sandbox_id, command)

    async def fetch_branch(self, sandbox_id: str, branch: str) -> str:
        return await self._impl.fetch_branch(sandbox_id, branch)

    async def snapshot(self, sandbox_id: str):
        return await self._impl.snapshot(sandbox_id)

    async def pause(self, sandbox_id: str) -> None:
        await self._impl.pause(sandbox_id)

    async def destroy(self, sandbox_id: str) -> None:
        await self._impl.destroy(sandbox_id)

    async def usage(self, sandbox_id: str):
        return await self._impl.usage(sandbox_id)
