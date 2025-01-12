from typing import Protocol

from ..types import BallistaProject


class BallistaEnvironmentDriver(Protocol):
    def startup(self, project: BallistaProject):
        pass

    def shutdown(self, project: BallistaProject):
        pass
