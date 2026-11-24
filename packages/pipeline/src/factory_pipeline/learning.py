"""Measured prompt improvement. Outcomes -> candidate -> paired eval -> approval -> activation."""

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from factory_contracts import ContractError, RequestCreate
from pydantic import BaseModel, ConfigDict, Field

from factory_pipeline.workspace import command, git


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)
    instructions: str = Field(min_length=1, max_length=4000)
    evidence: list[str] = Field(min_length=1)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["functional", "security", "recovery"] = "functional"
    repository: str
    branch: str = "main"
    request: str
    project_type: str = Field(pattern="^(brownfield|greenfield|modernization)$")
    checks: list[list[str]] = Field(min_length=1)
    answers: list[str] = Field(default_factory=list)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


async def outcome(database: Any, request: Any, state: dict[str, Any]) -> None:
    if state.get("is_evaluation"):
        return
    events = await database.read(request.id)
    suffix = f"{state.get('ci_repairs', 0)}:{state.get('outcome', 'failed')}"
    await database.insert_state(
        f"learning:outcome:{request.id}:{suffix}",
        {
            "request_id": str(request.id),
            "profile": state.get("project_type", "brownfield"),
            "outcome": state.get("outcome", "failed"),
            "failure": state.get("failure"),
            "active_seconds": state.get("active_seconds", 0),
            "repairs": state.get("fix_round", 0),
            "provider": state.get("provider"),
            "model": state.get("model"),
            "verified_sha": state.get("verified_sha"),
            "verification": state.get("verification", []),
            "candidate": state.get("learning_candidate"),
            "skills": [item.payload for item in events if item.type == "skills.applied"],
        },
    )


async def propose(database: Any, request_id: str, profile: str, proposal: Proposal) -> str:
    candidate = {**proposal.model_dump(), "profile": profile, "request_id": request_id}
    candidate_id = fingerprint(candidate)
    candidate["id"] = candidate_id
    candidate.update({"hash": fingerprint(candidate), "created_at": time.time()})
    await database.insert_state(f"learning:candidate:{candidate_id}", candidate)
    return candidate_id


async def enhancement(
    database: Any, profile: str, candidate_id: str | None
) -> dict[str, Any] | None:
    if not candidate_id:
        return None
    candidate = await database.get_state(f"learning:candidate:{candidate_id}")
    if not candidate or candidate["profile"] != profile:
        raise ContractError("Learning candidate not found for this profile")
    payload = {key: value for key, value in candidate.items() if key not in {"hash", "created_at"}}
    if fingerprint(payload) != candidate["hash"]:
        raise ContractError("Learning candidate integrity mismatch")
    return candidate


async def evaluate(database: Any, candidate_id: str) -> dict[str, Any]:
    """Only a server-configured held-out suite supplies grades; never accept client scores."""
    from factory_pipeline.service import tick

    suite_path = os.environ.get("FACTORY_EVAL_SUITE")
    if not suite_path:
        raise ContractError("Configure a trusted FACTORY_EVAL_SUITE before evaluating candidates")
    raw = await asyncio.to_thread(Path(suite_path).read_text)
    cases = [Case.model_validate(item) for item in json.loads(raw)]
    if len({fingerprint(case.model_dump(exclude={"id"})) for case in cases}) != len(cases):
        raise ContractError("Held-out cases must be distinct tasks, not repeated IDs")
    if len({case.id for case in cases}) != len(cases):
        raise ContractError("Evaluation case IDs must be unique")
    candidate = await database.get_state(f"learning:candidate:{candidate_id}")
    if not candidate:
        raise ContractError("Unknown learning candidate")
    cases = [case for case in cases if case.project_type == candidate["profile"]]
    if len(cases) < 3:
        raise ContractError(
            "At least three distinct held-out cases are required to run an evaluation"
        )
    active = await database.get_state(f"learning:active:{candidate['profile']}") or {}
    baseline_id = active.get("candidate_id")
    runtime_snapshot = await database.get_state("runtime.settings") or {
        "provider": os.environ.get("FACTORY_T3_PROVIDER"),
        "model": os.environ.get("FACTORY_T3_MODEL"),
    }
    results = []
    source_trees: dict[str, str] = {}
    for case in cases:
        for variant, chosen in (("baseline", baseline_id), ("candidate", candidate_id)):
            request = await database.create_request(
                RequestCreate(
                    title=f"Evaluation {case.id} {variant}",
                    body=case.request,
                    target=case.repository,
                    requester="factory-evaluator",
                )
            )
            await database.put_state(
                f"run:{request.id}",
                {
                    "execution_mode": "live",
                    "is_evaluation": True,
                    "project_type": "auto",
                    "expected_profile": case.project_type,
                    "delivery_target": "verified",
                    "learning_candidate": chosen,
                    "learning_frozen": True,
                    "runtime_snapshot": runtime_snapshot,
                    "connected_repo": {"branch": case.branch},
                },
            )
            hint: dict[str, Any] = {}
            answers = iter(case.answers)
            verdict = "fail"
            try:
                for _stage in range(40):
                    result = await tick(request.id, hint)
                    hint = {}
                    status = result["status"]
                    if status == "parked":
                        hint = {"answer": next(answers)}
                    elif status == "awaiting_approval":
                        hint = {"decision": "approve"}
                    elif status in {"failed", "killed"}:
                        break
                    elif status == "completed":
                        state = await database.get_state(f"run:{request.id}") or {}
                        workspace, head = state["workspace"], state["verified_sha"]
                        source_tree = await git(
                            workspace, "rev-parse", state["base_sha"] + "^{tree}"
                        )
                        if variant == "baseline":
                            source_trees[case.id] = source_tree
                        elif case.id in source_trees and source_tree != source_trees[case.id]:
                            raise ContractError("Source baseline changed during paired evaluation")
                        for check in case.checks:
                            await command(check, workspace, deadline=300)
                        if await git(workspace, "rev-parse", "HEAD") != head:
                            raise ContractError("Held-out grader modified the evaluated commit")
                        verdict = "pass"
                        break
            except (ContractError, StopIteration, TimeoutError, KeyError):
                verdict = "fail"
            state = await database.get_state(f"run:{request.id}") or {}
            results.append(
                {
                    "case": case.id,
                    "kind": case.kind,
                    "variant": variant,
                    "verdict": verdict,
                    "request_id": str(request.id),
                    "graded_sha": state.get("verified_sha"),
                    "skills": state.get("skill_versions", {}),
                    "active_seconds": state.get("active_seconds", 0),
                }
            )
    evaluation = {
        "id": str(uuid4()),
        "candidate_id": candidate_id,
        "candidate_hash": candidate["hash"],
        "baseline_id": baseline_id,
        "suite_hash": hashlib.sha256(raw.encode()).hexdigest(),
        "runtime_snapshot": runtime_snapshot,
        "results": results,
        "created_at": time.time(),
    }
    await database.insert_state(f"learning:evaluation:{evaluation['id']}", evaluation)
    return evaluation


async def promote(
    database: Any, candidate_id: str, evaluation_id: str, approver: str
) -> dict[str, Any]:
    evaluation = await database.get_state(f"learning:evaluation:{evaluation_id}")
    candidate = await database.get_state(f"learning:candidate:{candidate_id}")
    if not evaluation or not candidate or evaluation["candidate_id"] != candidate_id:
        raise ContractError("Candidate has no matching measured evaluation")
    await enhancement(database, candidate["profile"], candidate_id)
    active_key = f"learning:active:{candidate['profile']}"
    previous_state = await database.get_state(active_key)
    current = previous_state or {}
    if evaluation["baseline_id"] != current.get("candidate_id"):
        raise ContractError("Evaluation baseline is stale; re-evaluate")
    if evaluation["candidate_hash"] != candidate["hash"]:
        raise ContractError("Evaluation is not bound to this candidate content")
    suite_path = os.environ.get("FACTORY_EVAL_SUITE")
    if suite_path:
        raw = await asyncio.to_thread(Path(suite_path).read_text)
        if hashlib.sha256(raw.encode()).hexdigest() != evaluation.get("suite_hash"):
            raise ContractError("Held-out suite changed; re-evaluate")
    if evaluation.get("runtime_snapshot"):
        runtime = await database.get_state("runtime.settings") or {
            "provider": os.environ.get("FACTORY_T3_PROVIDER"),
            "model": os.environ.get("FACTORY_T3_MODEL"),
        }
        if runtime != evaluation["runtime_snapshot"]:
            raise ContractError("Runtime selection changed; re-evaluate")
    results = evaluation["results"]
    baseline = {row["case"]: row for row in results if row["variant"] == "baseline"}
    proposed = {row["case"]: row for row in results if row["variant"] == "candidate"}
    if len(proposed) < 30 or proposed.keys() != baseline.keys():
        raise ContractError("Promotion requires at least 30 paired held-out cases")
    if any(row.get("skills") != baseline[case].get("skills") for case, row in proposed.items()):
        raise ContractError("Skill versions changed during paired evaluation")
    for kind in ("security", "recovery"):
        if sum(row.get("kind") == kind for row in proposed.values()) < 3:
            raise ContractError(f"Promotion requires at least three {kind} cases")
    if any(row["verdict"] != "pass" for row in proposed.values()):
        raise ContractError("All candidate held-out cases must pass")
    if not any(row["verdict"] == "fail" for row in baseline.values()):
        raise ContractError("No measured improvement over baseline")
    baseline_time = sum(row["active_seconds"] for row in baseline.values())
    candidate_time = sum(row["active_seconds"] for row in proposed.values())
    if baseline_time and candidate_time > baseline_time * 1.2:
        raise ContractError("Candidate execution time regressed by more than 20 percent")
    revision = {
        "candidate_id": candidate_id,
        "evaluation_id": evaluation_id,
        "previous": current.get("candidate_id"),
        "approved_by": approver,
        "activated_at": time.time(),
    }
    if not await database.compare_state(active_key, previous_state, revision):
        raise ContractError("Active candidate changed concurrently; re-evaluate")
    await database.insert_state(f"learning:activation:{uuid4()}", revision)
    return revision
