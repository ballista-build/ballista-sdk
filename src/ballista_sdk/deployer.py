from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.api.v1 import (
    ArtifactReference,
    Bolt,
    BoundSetting,
    Environment,
    ExecutableArtifact,
    ResourceReference,
)


class Deployer:
    def get_settings(
        self,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        environment: Environment,
        adapter: InfrastructureAdapter,
        sensitive: bool | None = None,
    ) -> list[BoundSetting]:
        """Get Settings used by artifacts in Bolt.

        `sensitive` allows filterings for configs or secrets. None returns both."""
        artifact_reference = ArtifactReference(bolt.project, artifact.name, bolt.version)

        if sensitive is True:
            artifact_settings = artifact.execution.secrets
        elif sensitive is False:
            artifact_settings = artifact.execution.configs
        else:
            artifact_settings = artifact.execution.configs + artifact.execution.secrets

        settings = [BoundSetting(artifact=artifact_reference, setting=s) for s in artifact_settings]

        # Get all the settings from Resource requirements
        for resource_requirement in artifact.execution.resources:
            resource, resource_project, _, _ = adapter.resolve_resource_requirement(resource_requirement, environment)
            requirement_instance = []
            resource_reference = ResourceReference(resource_project, resource.name)

            if sensitive is True:
                resource_settings = resource.secrets
            elif sensitive is False:
                resource_settings = resource.configs
            else:
                resource_settings = resource.configs + resource.secrets

            # Bind all the resource configs and secrets
            settings.extend(
                [
                    BoundSetting(
                        artifact=artifact_reference,
                        resource=resource_reference,
                        setting=s,
                        resource_instance=requirement_instance,
                    )
                    for s in resource_settings
                ]
            )

        return settings
