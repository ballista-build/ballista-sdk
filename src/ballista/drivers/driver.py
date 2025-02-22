from typing import Protocol

from ..types import BallistaBolt


class BallistaEnvironmentDriver(Protocol):
    def startup(self, bolt: BallistaBolt):
        pass

    def shutdown(self, bolt: BallistaBolt):
        pass
