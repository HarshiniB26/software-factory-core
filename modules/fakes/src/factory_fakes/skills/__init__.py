"""One pinned example skill. No network fetch."""

from factory_contracts import ContractError, SkillBundle, SkillRef, VerifyResult

_REF = "example/tdd@0.1.0"


class FakeSkillSource:
    async def list(self) -> list[SkillRef]:
        return [SkillRef(ref=_REF, license="MIT", description="Write a failing test first.")]

    async def fetch(self, ref: str) -> SkillBundle:
        if ref != _REF:
            raise ContractError(f"unknown skill {ref}")
        return SkillBundle(ref=ref, content="# tdd\nWrite a failing test first.\n")

    async def verify(self, ref: str) -> VerifyResult:
        if ref != _REF:
            raise ContractError(f"unknown skill {ref}")
        return VerifyResult(ref=ref, ok=True, license="MIT")
