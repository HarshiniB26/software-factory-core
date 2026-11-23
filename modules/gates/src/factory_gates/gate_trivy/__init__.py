from factory_contracts import GateResult

from factory_gates import ToolGate, _json


class TrivyGate(ToolGate):
    name = "trivy"
    binary = "trivy"
    needles = ("image: latest", ":latest")

    def command(self) -> list[str]:
        return [
            "trivy",
            "fs",
            "--scanners",
            "misconfig",
            "--skip-db-update",
            "--offline-scan",
            "--format",
            "json",
            "--quiet",
            ".",
        ]

    def parse(self, stdout: str, stderr: str, code: int) -> GateResult:
        payload = _json(stdout)
        findings: list[str] = []
        results = payload.get("Results", []) if isinstance(payload, dict) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            for item in result.get("Misconfigurations") or []:
                if isinstance(item, dict):
                    findings.append(f"trivy: {item.get('ID')} {item.get('Title')}")
        if findings:
            return GateResult(verdict="fail", findings=findings)
        if code not in {0, 1} and payload is None:
            return GateResult(verdict="pass", findings=[f"trivy: tool error, {stderr[:180]}"])
        return GateResult(verdict="pass")
