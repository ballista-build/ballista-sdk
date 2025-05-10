from typing import Any

from semver import Version

from ballista import models

from ..api import v1alpha
from ..types import (
    Bolt,
)
from ..types import (
    BoltService as BaseBoltService,
)


class BoltService(BaseBoltService):
    def create_bolt(self, project_id: str) -> Bolt:
        data = {}

        return self.get_bolt(data)

    def get_bolt(self, bolt_data: dict[str, Any]) -> Bolt:
        v1a_bolt = v1alpha.BoltInput.from_dict(bolt_data)
        if not v1a_bolt:
            raise ValueError()

        # Translate the outdated API models into our working internal stuff for now
        project = models.PydanticProject(id=v1a_bolt.project, name=v1a_bolt.project)
        artifacts = []
        for v1a_artifact in v1a_bolt.artifacts:
            artifact_type = models.PydanticArtifactType(id="docker_image", name="docker_image")
            artifact = models.PydanticArtifact(id=v1a_artifact.name, type=artifact_type)

            if v1a_artifact.execution:
                execution = models.PydanticArtifactExecution()
                if v1a_local_resources := v1a_artifact.execution.local_resources:
                    local_resources = models.PydanticArtifactLocalResourceNeeds()
                    if max_cpu_cores := v1a_local_resources.max_cpu_cores:
                        local_resources.max_cpu = max_cpu_cores
                    if min_cpu_cores := v1a_local_resources.min_cpu_cores:
                        local_resources.min_cpu = min_cpu_cores
                    if max_memory_mb := v1a_local_resources.max_memory_mb:
                        local_resources.max_memory = max_memory_mb / 1024
                    if min_memory_mb := v1a_local_resources.min_memory_mb:
                        local_resources.min_memory = min_memory_mb / 1024
                        execution.local_resources = local_resources
                artifact.execution = execution

            artifacts.append(artifact)

        # Schema validation
        return models.PydanticBolt(artifacts=artifacts, project=project, version=Version.parse(v1a_bolt.version))
