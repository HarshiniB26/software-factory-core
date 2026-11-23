"""Read pinned SKILL.md files and reject secrets or disallowed licenses."""

from pathlib import Path

import yaml
from factory_contracts import ContractError, SkillBundle, SkillRef, VerifyResult

ALLOWLIST = {"MIT", "Apache-2.0", "BSD", "BSD-2-Clause", "BSD-3-Clause", "CC-BY-SA-4.0", "MPL-2.0"}
PINNED_SHA = {
    "superpowers": "22f0b463e7a5e579904dd6211a520321035526f7",
    "pstack": "7a583913eb1b8d1a0ee76753d1a2cf072e7b54f9",
}
SECRET_NEEDLES = ("AKIA", "-----BEGIN", "sk_live_", "ghp_")


class GitSkillSource:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or _default_root()

    async def list(self) -> list[SkillRef]:
        refs: list[SkillRef] = []
        if not self._root.is_dir():
            return [
                SkillRef(
                    ref="example/tdd@0.1.0",
                    license="MIT",
                    description="Write a failing test first.",
                )
            ]
        for path in sorted(self._root.glob("*/SKILL.md")):
            meta = _meta(path)
            skill_id = str(meta.get("id") or meta.get("name") or path.parent.name)
            source = "superpowers" if path.parent.name.startswith("superpowers-") else "pstack"
            sha = str(meta.get("sha") or PINNED_SHA.get(source, "unpinned"))
            refs.append(
                SkillRef(
                    ref=f"{source}/{skill_id}@{sha}",
                    license="MIT",
                    description=str(meta.get("description", "")),
                )
            )
        return refs or [
            SkillRef(
                ref="example/tdd@0.1.0", license="MIT", description="Write a failing test first."
            )
        ]

    async def fetch(self, ref: str) -> SkillBundle:
        path = self._find(ref)
        if path is None:
            if ref == "example/tdd@0.1.0":
                return SkillBundle(ref=ref, content="# tdd\nWrite a failing test first.\n")
            raise ContractError(f"unknown skill {ref}")
        return SkillBundle(ref=ref, content=path.read_text(encoding="utf-8"))

    async def verify(self, ref: str) -> VerifyResult:
        bundle = await self.fetch(ref)
        license_name = "MIT"
        findings: list[str] = []
        if bundle.content.startswith("---"):
            meta = _meta_text(bundle.content)
            license_name = str(meta.get("license", "MIT"))
        if license_name not in ALLOWLIST:
            findings.append(f"license {license_name} is not allowlisted")
        for needle in SECRET_NEEDLES:
            if needle in bundle.content:
                findings.append(f"secret pattern {needle}")
        return VerifyResult(ref=ref, ok=not findings, license=license_name, findings=findings)

    def _find(self, ref: str) -> Path | None:
        wanted = ref.split("@", 1)[0].split("/")[-1]
        for path in self._root.glob("*/SKILL.md"):
            meta = _meta(path)
            skill_id = str(meta.get("id") or meta.get("name") or path.parent.name)
            if skill_id == wanted or path.parent.name.endswith(wanted):
                return path
        return None


def _default_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "registry" / "skills" / "pins"
        if candidate.is_dir():
            return candidate
    return Path("registry/skills/pins")


def _meta(path: Path) -> dict[str, object]:
    return _meta_text(path.read_text(encoding="utf-8"))


def _meta_text(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    raw = yaml.safe_load(text[3:end]) if end != -1 else {}
    return raw if isinstance(raw, dict) else {}
