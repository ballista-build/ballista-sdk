from typing import Annotated

from kubernetes import config
from kubernetes.client.api_client import ApiClient
from pydantic import BaseModel, Field

from ballista_sdk.api.v1 import Environment


class KubernetesAPIEnvironment(Environment):
    """An Environment that can be used by KubernetesAPI adapters."""

    kubeconfig_file: str | None
    """Path to a kubeconfig file."""


class KubernetesEnvironmentConfig(BaseModel):
    """Configuration for a Kubernetes environment."""

    # TODO: This might change when there's fleshed-out support for building and publishing artifacts.
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

    gateway_api: bool = False
    """Use Gateway API instead of Ingress."""


def get_environment_config(environment: Environment) -> KubernetesEnvironmentConfig:
    """Get a shaped configuration from an Environment."""

    return KubernetesEnvironmentConfig.model_validate(environment.config if environment.config else {})


def get_environment_apiclient(environment: KubernetesAPIEnvironment) -> ApiClient:
    """Get a Kubernetes APIClient for the specified KuberenetesAPIEnvironment."""

    return config.new_client_from_config(
        config_file=environment.kubeconfig_file, persist_config=(environment.kubeconfig_file is None)
    )
