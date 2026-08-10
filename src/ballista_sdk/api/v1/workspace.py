from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .execution import DefaultExecutionParameters


class LocalEnvironmentConfiguration(BaseModel):
    adapter: Annotated[
        Literal["docker-compose", "kubernetes-api"],
        Field(description="Infrastructure Adapter to use for Environment."),
    ]

    default_execution_parameters: Annotated[
        DefaultExecutionParameters, Field(default_factory=DefaultExecutionParameters)
    ]


class Workspace(BaseModel):
    """Workspace configuration."""

    api_version: Literal["v1"] = "v1"
    kind: Literal["Workspace"] = "Workspace"

    local_environment: Annotated[
        LocalEnvironmentConfiguration | None, Field(description="Configuration for local development environment.")
    ] = None

    kubeconfig_environments: Annotated[
        bool,
        Field(description="Automatically use kube-config entries for remote KubernetesAPI Environments."),
    ] = True
