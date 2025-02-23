from typing import Any

from ..api import v1alpha
from ..types import (
    BallistaBolt,
)
from ..types import (
    BoltService as BaseBoltService,
)


class BoltService(BaseBoltService):
    def create_bolt(self, project: str) -> BallistaBolt:
        artifact = v1alpha.ArtifactInput(name=project, type={})
        return v1alpha.BoltInput(api_version="v1alpha", artifacts=[artifact], project=project, version="0.0.1")

    def get_bolt(self, bolt_data: dict[str, Any]) -> BallistaBolt:
        bolt = v1alpha.BoltInput.from_dict(bolt_data)
        if not bolt:
            raise ValueError()

        # Schema validation

        return bolt
