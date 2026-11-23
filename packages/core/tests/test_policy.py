from pathlib import Path

import pytest
from factory_core import Policy, PolicyError, load_modules, resolve_config


def test_defaults_pass_policy(tmp_path: Path) -> None:
    Policy().validate(resolve_config(tmp_path), load_modules())


def test_unknown_module_is_rejected(tmp_path: Path) -> None:
    config = resolve_config(tmp_path, run={"modules": {"sandbox": "sandbox-missing"}})
    with pytest.raises(PolicyError, match="sandbox-missing"):
        Policy().validate(config, load_modules())


def test_module_config_must_match_schema(tmp_path: Path) -> None:
    config = resolve_config(
        tmp_path,
        run={"module_config": {"sandbox-fake": {"image": 1}}},
    )
    with pytest.raises(PolicyError, match="sandbox-fake"):
        Policy().validate(config, load_modules())


def test_checked_in_config_is_valid() -> None:
    root = Path(__file__).resolve().parents[3]
    config = resolve_config(root)
    Policy().validate(config, load_modules())
    assert "repo" in config.layers_applied
