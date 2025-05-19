from typing import Any

from ballista.api.v1 import models

from ..types import (
    BoltService as BaseBoltService,
)


class BoltService(BaseBoltService):
    def create_bolt(self, project_id: str) -> models.Bolt:
        return models.Bolt(artifacts=[], project_id=project_id, version="0.1.0")

    def get_bolt(self, bolt_data: dict[str, Any]) -> models.Bolt:
        return models.Bolt.model_validate(bolt_data)
