from factory_contracts import GateResult

from factory_gates import ToolGate, _json


class SemgrepGate(ToolGate):
    name = "semgrep"
    binary = "semgrep"
    needles = ("eval(", "exec(", "pickle.loads(")

    def command(self) -> list[str]:
        return ["semgrep", "--config", "/opt/factory/semgrep.yml", "--json", "--quiet", "."]

    def parse(self, stdout: str, stderr: str, code: int) -> GateResult:
        payload = _json(stdout)
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if results:
            findings = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                line = item.get("start", {}).get("line")
                findings.append(f"semgrep: {item.get('check_id')} {path}:{line}")
            return GateResult(verdict="fail", findings=findings or ["semgrep: findings"])
        if code not in {0, 1} and not isinstance(payload, dict):
            return GateResult(verdict="fail", findings=[f"semgrep: {stderr[:300] or 'failed'}"])
        return GateResult(verdict="pass")
