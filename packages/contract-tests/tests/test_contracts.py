import pytest
from factory_contract_tests.discovery import modules_for
from factory_contract_tests.suites import (
    assert_auth_contract,
    assert_clarifier_contract,
    assert_eval_contract,
    assert_gate_contract,
    assert_harness_contract,
    assert_intake_contract,
    assert_model_contract,
    assert_notifier_contract,
    assert_observability_contract,
    assert_orchestrator_contract,
    assert_planner_contract,
    assert_sandbox_contract,
    assert_secrets_contract,
    assert_skill_contract,
    assert_storage_contract,
    assert_vcs_contract,
)
from factory_core import LoadedModule


def _ids(module: LoadedModule) -> str:
    return module.manifest.id


@pytest.mark.parametrize("module", modules_for("Orchestrator"), ids=_ids)
async def test_orchestrator_contract(module: LoadedModule) -> None:
    await assert_orchestrator_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("Storage"), ids=_ids)
async def test_storage_contract(module: LoadedModule) -> None:
    await assert_storage_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("IntakeSource"), ids=_ids)
async def test_intake_contract(module: LoadedModule) -> None:
    await assert_intake_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("Notifier"), ids=_ids)
async def test_notifier_contract(module: LoadedModule) -> None:
    await assert_notifier_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("Clarifier"), ids=_ids)
async def test_clarifier_contract(module: LoadedModule) -> None:
    await assert_clarifier_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("Planner"), ids=_ids)
async def test_planner_contract(module: LoadedModule) -> None:
    await assert_planner_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("HarnessAdapter"), ids=_ids)
async def test_harness_contract(module: LoadedModule) -> None:
    await assert_harness_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("ModelProvider"), ids=_ids)
async def test_model_contract(module: LoadedModule) -> None:
    await assert_model_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("SandboxProvider"), ids=_ids)
async def test_sandbox_contract(module: LoadedModule) -> None:
    await assert_sandbox_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("VcsProvider"), ids=_ids)
async def test_vcs_contract(module: LoadedModule) -> None:
    await assert_vcs_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("QualityGate"), ids=_ids)
async def test_gate_contract(module: LoadedModule) -> None:
    await assert_gate_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("SkillSource"), ids=_ids)
async def test_skill_contract(module: LoadedModule) -> None:
    await assert_skill_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("EvalRunner"), ids=_ids)
async def test_eval_contract(module: LoadedModule) -> None:
    await assert_eval_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("ObservabilityExporter"), ids=_ids)
async def test_observability_contract(module: LoadedModule) -> None:
    await assert_observability_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("AuthProvider"), ids=_ids)
async def test_auth_contract(module: LoadedModule) -> None:
    await assert_auth_contract(module.implementation())


@pytest.mark.parametrize("module", modules_for("SecretsProvider"), ids=_ids)
async def test_secrets_contract(module: LoadedModule) -> None:
    await assert_secrets_contract(module.implementation())
