"""Quality gates. Real scanners run inside the sandbox; patterns are only a fallback."""

import json
import shutil
import subprocess
from typing import Any

from factory_contracts import GateContext, GateResult
from factory_sandboxes.runtime import run_command


class ToolGate:
    name = "tool"
    binary = ""
    needles: tuple[str, ...] = ()

    def command(self) -> list[str]:
        return [self.binary, "--version"]

    def applies_to(self, repo: str, diff: str) -> bool:
        return True

    async def run(self, sandbox_id: str, context: GateContext) -> GateResult:
        ran = run_command(sandbox_id, self.command())
        if ran is not None:
            parsed = self.parse(ran.stdout, ran.stderr, ran.exit_code)
            parsed.findings.insert(0, f"{self.name}: scanned inside sandbox")
            return parsed
        if self.binary and shutil.which(self.binary) and context.workspace:
            parsed = self._scan_host(context.workspace)
            parsed.findings.insert(0, f"{self.name}: scanned on host workspace")
            return parsed
        return self.fallback(context)

    def parse(self, stdout: str, stderr: str, code: int) -> GateResult:
        if code == 0:
            return GateResult(verdict="pass")
        text = (stdout or stderr or "scanner failed").strip()
        return GateResult(verdict="fail", findings=[f"{self.name}: {text[:500]}"])

    def fallback(self, context: GateContext) -> GateResult:
        hits = [needle for needle in self.needles if needle in context.diff]
        note = f"{self.name}: tool unavailable, pattern fallback"
        if hits:
            named = [f"{self.name}: {hit}" for hit in hits]
            return GateResult(verdict="fail", findings=[note, *named])
        if context.diff.strip():
            return GateResult(verdict="pass", findings=[note])
        return GateResult(verdict="pass")

    def _scan_host(self, workspace: str) -> GateResult:
        completed = subprocess.run(
            self.command(),
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        return self.parse(completed.stdout, completed.stderr, completed.returncode)


def _json(stdout: str) -> Any:
    start = stdout.find("{")
    start_list = stdout.find("[")
    if start_list != -1 and (start == -1 or start_list < start):
        start = start_list
    if start == -1:
        return None
    try:
        return json.loads(stdout[start:])
    except json.JSONDecodeError:
        return None
