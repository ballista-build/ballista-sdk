from typing import Annotated

from kubernetes import client, config
from pydantic import BaseModel, Field

from ballista_sdk.api.v1 import Environment


class KubernetesEnvironmentConfig(BaseModel):
    """Configuration for a Kubernetes environment."""

    # TODO: This might change when there's better support for building and publishing artifacts.
    image_registry: Annotated[
        str | None,
        Field(
            description="Docker Image registry where executable artifacts are stored. Used for artifacts that were built by Ballista."
        ),
    ] = None
    """Image registry for image execution."""

    ensure_namespaces: bool = True
    """Ensures proper Namespaces are available and configured."""

    force_image_registry: Annotated[
        bool, Field(description="Force images to be retrieved and executed from configured image registry.")
    ] = False
    """Force images to be retrieved and executed from configured image registry."""

    project_namespaces: bool = False
    """Projects are deployed into their own namespaces."""


def get_environment_config(environment: Environment) -> KubernetesEnvironmentConfig:
    """Get a shaped configuration from an Environment."""

    return KubernetesEnvironmentConfig.model_validate(environment.config if environment.config else {})


def get_kubernetes_client(environment: Environment) -> client.ApiClient:
    # TODO: Get context where environment is
    context = None

    return config.new_client_from_config(context=context)
