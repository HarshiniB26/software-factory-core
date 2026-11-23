from factory_contracts import GateResult

from factory_gates import ToolGate, _json


class GitleaksGate(ToolGate):
    name = "gitleaks"
    binary = "gitleaks"
    needles = ("AKIA", "-----BEGIN", "sk_live_", "ghp_")

    def command(self) -> list[str]:
        return [
            "sh",
            "-c",
            "gitleaks detect --source . --report-format json --report-path /tmp/gitleaks.json "
            "--no-banner --exit-code 0; cat /tmp/gitleaks.json",
        ]

    def parse(self, stdout: str, stderr: str, code: int) -> GateResult:
        payload = _json(stdout)
        leaks = payload if isinstance(payload, list) else []
        if leaks:
            findings = [
                f"gitleaks: {item.get('RuleID')} {item.get('File')}"
                for item in leaks
                if isinstance(item, dict)
            ]
            return GateResult(verdict="fail", findings=findings or ["gitleaks: secret found"])
        return GateResult(verdict="pass")
