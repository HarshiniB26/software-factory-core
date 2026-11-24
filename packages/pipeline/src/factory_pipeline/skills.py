"""Deliver pinned upstream skill instructions, with receipts for the exact content."""

import hashlib
from typing import Any

from factory_contracts import ContractError, SkillSource

STAGE_SKILLS = {
    "discover": ("systematic-debugging", "principle-fix-root-causes"),
    "plan": ("writing-plans",),
    "implement": ("test-driven-development", "verification-before-completion"),
    "review": ("blast-radius", "verification-before-completion"),
    "reflect": ("principle-fix-root-causes", "technical-writing"),
}


async def instructions(
    source: SkillSource, stage: str, discovery_skills: tuple[str, ...] | None = None
) -> tuple[str, list[dict[str, Any]]]:
    catalog = await source.list()
    blocks: list[str] = []
    receipts: list[dict[str, Any]] = []
    names = discovery_skills if stage == "discover" and discovery_skills else STAGE_SKILLS[stage]
    for name in names:
        matches = [item for item in catalog if item.ref.split("@", 1)[0].endswith("/" + name)]
        if len(matches) != 1:
            raise ContractError(f"Required skill {name} is missing or ambiguous")
        ref = matches[0].ref
        verified = await source.verify(ref)
        if not verified.ok:
            raise ContractError(f"Skill verification failed: {ref}")
        bundle = await source.fetch(ref)
        if bundle.ref != ref or not bundle.content.strip():
            raise ContractError(f"Skill content mismatch: {ref}")
        digest = hashlib.sha256(bundle.content.encode()).hexdigest()
        receipts.append({"ref": ref, "sha256": digest, "stage": stage})
        blocks.append(f"<skill ref={ref!r}>\n{bundle.content}\n</skill>")
    return "\n\n".join(blocks), receipts
