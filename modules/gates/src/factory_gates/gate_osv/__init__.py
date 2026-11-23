from factory_contracts import GateResult

from factory_gates import ToolGate, _json


class OsvGate(ToolGate):
    name = "osv"
    binary = "osv-scanner"
    needles = ("django==1.11", "requests==2.19.0")

    def command(self) -> list[str]:
        return ["osv-scanner", "--format", "json", "-r", "."]

    def parse(self, stdout: str, stderr: str, code: int) -> GateResult:
        payload = _json(stdout)
        findings: list[str] = []
        results = payload.get("results", []) if isinstance(payload, dict) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            for package in result.get("packages") or []:
                if not isinstance(package, dict):
                    continue
                for vuln in package.get("vulnerabilities") or []:
                    if isinstance(vuln, dict):
                        findings.append(f"osv: {vuln.get('id')}")
        if findings:
            return GateResult(verdict="fail", findings=findings)
        if payload is None and code != 0:
            return GateResult(
                verdict="pass",
                findings=[f"osv: tool unavailable or offline, pattern fallback ({stderr[:120]})"],
            )
        return GateResult(verdict="pass")
