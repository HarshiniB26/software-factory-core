"""Write one JSON line per signal. A collector can scrape stdout later."""

import json
import sys

from factory_contracts import ObservabilityItem


class OtelExporter:
    def __init__(self) -> None:
        self.exported: list[ObservabilityItem] = []

    async def export(self, item: ObservabilityItem) -> None:
        self.exported.append(item)
        sys.stdout.write(json.dumps({"factory": item.model_dump()}) + "\n")
