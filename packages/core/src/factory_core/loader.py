"""Discover modules from the factory.modules entry-point group."""

import importlib.metadata
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from factory_contracts import PROTOCOLS, ModuleManifest

from factory_core.errors import LoaderError


@dataclass(frozen=True)
class LoadedModule:
    manifest: ModuleManifest
    implementation: type[Any]
    manifest_path: Path
    schema_path: Path | None
    entry_point: str


def load_manifest(path: Path) -> ModuleManifest:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LoaderError(f"{path} must be a mapping")
    try:
        return ModuleManifest.model_validate(raw)
    except Exception as exc:
        raise LoaderError(f"invalid manifest {path}: {exc}") from exc


def _protocol_methods(interface: str) -> set[str]:
    protocol = PROTOCOLS.get(interface)
    if protocol is None:
        raise LoaderError(f"unknown interface {interface}")
    attrs = getattr(protocol, "__protocol_attrs__", None)
    if not isinstance(attrs, set):
        raise LoaderError(f"cannot read methods for {interface}")
    return {name for name in attrs if isinstance(name, str) and not name.startswith("_")}


def load_modules() -> list[LoadedModule]:
    found: list[LoadedModule] = []
    seen: set[str] = set()
    for entry in importlib.metadata.entry_points(group="factory.modules"):
        loaded = entry.load()
        if not isinstance(loaded, type):
            raise LoaderError(f"{entry.name} does not point at a class")
        manifest_path = Path(inspect.getfile(loaded)).resolve().parent / "module.yaml"
        if not manifest_path.is_file():
            raise LoaderError(f"{entry.name} is missing {manifest_path}")
        manifest = load_manifest(manifest_path)
        if manifest.id != entry.name:
            raise LoaderError(f"entry point {entry.name} does not match manifest id {manifest.id}")
        if manifest.id in seen:
            raise LoaderError(f"duplicate module id {manifest.id}")
        seen.add(manifest.id)
        missing = sorted(
            name for name in _protocol_methods(manifest.interface_name) if not hasattr(loaded, name)
        )
        if missing:
            raise LoaderError(f"{manifest.id} is missing {', '.join(missing)}")
        schema_path: Path | None = None
        if manifest.config_schema:
            schema_path = (manifest_path.parent / manifest.config_schema).resolve()
            if not schema_path.is_file():
                raise LoaderError(f"{manifest.id} is missing config schema {schema_path}")
        found.append(
            LoadedModule(
                manifest=manifest,
                implementation=loaded,
                manifest_path=manifest_path,
                schema_path=schema_path,
                entry_point=entry.value,
            )
        )
    return found


async def instantiate(module: LoadedModule, settings: dict[str, Any] | None = None) -> Any:
    factory = getattr(module.implementation, "from_settings", None)
    if factory is None:
        return module.implementation()
    result = factory(settings)
    if inspect.isawaitable(result):
        return await result
    return result
