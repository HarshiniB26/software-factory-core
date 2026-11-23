from pathlib import Path

import pytest
from factory_contracts import ModuleManifest
from factory_core import LoaderError, load_manifest, load_modules
from pydantic import ValidationError


def test_loader_discovers_fake_modules() -> None:
    modules = load_modules()
    ids = {module.manifest.id for module in modules}
    assert "sandbox-fake" in ids
    assert "harness-fake" in ids
    assert "orchestrator-temporal" in ids
    temporal = next(module for module in modules if module.manifest.id == "orchestrator-temporal")
    assert temporal.manifest.testing == "external"
    sandbox = next(module for module in modules if module.manifest.id == "sandbox-fake")
    assert sandbox.manifest.interface_name == "SandboxProvider"
    assert sandbox.schema_path is not None


def test_manifest_rejects_unknown_interface(tmp_path: Path) -> None:
    path = tmp_path / "module.yaml"
    path.write_text(
        "id: example\nversion: 0.1.0\nimplements: NotARealProvider@1\n",
        encoding="utf-8",
    )
    with pytest.raises(LoaderError):
        load_manifest(path)


def test_manifest_model_rejects_bad_version() -> None:
    with pytest.raises(ValidationError):
        ModuleManifest.model_validate(
            {"id": "example", "version": "1", "implements": "SandboxProvider@1"}
        )
