"""Entry-point discovery for the conformance tests."""

from factory_core import LoadedModule, load_modules


def modules_for(interface: str) -> list[LoadedModule]:
    return [
        module
        for module in load_modules()
        if module.manifest.interface_name == interface and module.manifest.testing == "in-process"
    ]
