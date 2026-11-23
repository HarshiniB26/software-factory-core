"""Keeps exported items on the instance so tests can inspect them."""

from factory_contracts import ObservabilityItem


class FakeObservability:
    def __init__(self) -> None:
        self.exported: list[ObservabilityItem] = []

    async def export(self, item: ObservabilityItem) -> None:
        self.exported.append(item)
