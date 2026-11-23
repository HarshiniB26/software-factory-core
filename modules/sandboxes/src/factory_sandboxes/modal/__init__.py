"""Modal sandbox module. Uses the host workspace until MODAL_TOKEN_ID is set."""

import os

from factory_sandboxes.host import HostSandbox


class ModalSandbox(HostSandbox):
    def __init__(self) -> None:
        super().__init__(backend="modal")
        self._modal = bool(
            os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET")
        )
