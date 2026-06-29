from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from kubernetes import client, config, utils

from ballista_sdk.adapters.exceptions import ArtifactNotFound, ResourceProviderNotFound
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentTier,
    ExecutableArtifact,
    ExecutionParameters,
    Project,
    ProvidedResource,
    ProvidedResourceWithArtifactReference,
    ResourceProviderReference,
    ResourceRequirementProject,
)

from . import primitives
from .environments import get_environment_config, get_kubernetes_client
from .generation import KubernetesInfrastructureAdapter, generate_bolt_kubernetes_namespace, generate_environment_labels
from .settings import KubernetesAPIConfigsAdapter, KubernetesAPISecretsAdapter


@dataclass
class KubernetesAPIInfrastructureAdapter(KubernetesInfrastructureAdapter):
    """KubernetesInfrastructureAdapter that communicates directly via the Kubernetes API."""

    _bolts: list[Bolt] = field(default_factory=list)

    _configs_adapter: KubernetesAPIConfigsAdapter = field(default_factory=KubernetesAPIConfigsAdapter, init=False)
    _secrets_adapter: KubernetesAPISecretsAdapter = field(default_factory=KubernetesAPISecretsAdapter, init=False)

    @property
    def name(self) -> Literal["kubernetes-api"]:
        return "kubernetes-api"

    @property
    def configs_adapter(self) -> KubernetesAPIConfigsAdapter:
        return self._configs_adapter

    @property
    def secrets_adapter(self) -> KubernetesAPISecretsAdapter:
        return self._secrets_adapter

    async def deploy(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        environment_config = get_environment_config(environment)

        bolt_resources, all_artifact_resources = self.generate_bolt_resources(
            bolt=bolt,
            artifacts=artifacts,
            environment=environment,
            environment_config=environment_config,
            execution_parameters=execution_parameters,
        )

        api_client = get_kubernetes_client(environment)

        namespace = generate_bolt_kubernetes_namespace(environment, environment_config, bolt)

        if environment_config.ensure_namespaces:
            self._ensure_namespace_exists(environment, api_client, namespace)

        [utils.create_from_dict(api_client, resource, namespace=namespace, apply=True) for resource in bolt_resources]

        for artifact_id, artifact_resources in all_artifact_resources.items():
            [
                utils.create_from_dict(api_client, resource, namespace=namespace, apply=True)
                for resource in artifact_resources
            ]

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    def list_environments(self) -> list[Environment]:
        environments = []
        # Use the current kubeconfig context
        _, context = config.list_kube_config_contexts()

        if context:
            api_client = config.new_client_from_config(context=context["name"])

            # TODO: We don't have an Environment type, so use Namespace with labels for now.
            corev1_api = client.CoreV1Api(api_client=api_client)
            ballista_namespaces = corev1_api.list_namespace(
                label_selector=f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY},{primitives.METADATA_LABEL_ENVIRONMENT},{primitives.METADATA_LABEL_ENVIRONMENT_TIER}"
            )

            environments.extend(
                [
                    Environment(
                        name=n.metadata.name,
                        tier=EnvironmentTier(n.metadata.labels.get(primitives.METADATA_LABEL_ENVIRONMENT_TIER)),
                    )
                    for n in ballista_namespaces.items
                ]
            )

        return environments

    def list_executable_artifacts(self, environment: Environment) -> list[ArtifactReference]:
        if self._bolts:
            executable_artifacts = []
            for bolt in self._bolts:
                executable_artifacts.extend(
                    [
                        ArtifactReference(artifact.name, bolt.version, bolt.project)
                        for artifact in bolt.executable_artifacts
                    ]
                )
            return executable_artifacts

        api_client = get_kubernetes_client(environment)

        # 1:1 ExecutableArtifact:Deployment
        api = client.AppsV1Api(api_client)
        deployments = api.list_deployment_for_all_namespaces(
            label_selector=f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY},{primitives.METADATA_LABEL_ENVIRONMENT}={environment.name}"
        )

        executable_artifacts = []
        for deployment in deployments.items:
            labels = deployment.metadata.labels
            executable_artifacts.append(
                ArtifactReference(
                    labels["app.kubernetes.io/name"],
                    labels["app.kubernetes.io/version"],
                    labels["app.kubernetes.io/part-of"],
                )
            )

        return executable_artifacts

    def list_projects(self, environments: Sequence[Environment]) -> list[Project]:
        # TODO: Read these from Custom Resources when they exist. For now, read them out of the annotations of Deployments.

        if self._bolts:
            return list({Project(name=bolt.project) for bolt in self._bolts})

        projects: set[Project] = set()
        for environment in environments:
            api_client = get_kubernetes_client(environment)

            # 1:1 ExecutableArtifact:Deployment
            api = client.AppsV1Api(api_client)
            deployments = api.list_deployment_for_all_namespaces(
                label_selector=f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY},{primitives.METADATA_LABEL_ENVIRONMENT}={environment.name}"
            )

            for deployment in deployments.items:
                labels = deployment.metadata.labels
                projects.add(Project(name=labels["app.kubernetes.io/part-of"]))

        return list(projects)

    def list_project_bolts(self, project: Project, environments: Sequence[Environment]) -> list[Bolt]:
        return []

    def list_resources(self, environment: Environment) -> list[ProvidedResourceWithArtifactReference]:
        """List available Resources and the providing ArtifactIDReference in the specified Environment."""
        if self._bolts:
            executable_artifacts = []
            for bolt in self._bolts:
                executable_artifacts.extend(
                    [
                        ProvidedResourceWithArtifactReference(resource, bolt.project, artifact.name, bolt.version)
                        for artifact in bolt.executable_artifacts
                        for resource in artifact.provides
                    ]
                )

            return executable_artifacts

        api_client = get_kubernetes_client(environment)

        # 1:1 ExecutableArtifact:Deployment
        resources = []
        api = client.AppsV1Api(api_client)
        for deployment in api.list_deployment_for_all_namespaces(
            label_selector=f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY},{primitives.METADATA_LABEL_ENVIRONMENT}={environment.name},{primitives.METADATA_LABEL_RESOURCE}"
        ).items:
            metadata = cast(client.models.V1ObjectMeta, deployment.metadata)
            labels = cast(dict[str, str], metadata.labels)
            resource_json = metadata.annotations.get(primitives.METADATA_ANNOTATION_RESOURCE)
            if resource_json is not None:
                try:
                    resource = ProvidedResource.model_validate_json(resource_json)
                    ref = ProvidedResourceWithArtifactReference(
                        resource,
                        labels["app.kubernetes.io/part-of"],
                        labels["app.kubernetes.io/name"],
                        labels["app.kubernetes.io/version"],
                    )
                    resources.append(ref)

                except Exception as e:
                    print(e)

        return resources

    def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> tuple[Bolt, Artifact]:
        # TODO: Do this when the bolts are stored
        raise ArtifactNotFound(artifact_reference)

    def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirementProject
    ) -> ProvidedResourceWithArtifactReference:
        requirement_project_name = resource_requirement.which()
        requirement_resource_name = resource_requirement.resource_name

        # TODO: Do a smarter lookup via K8s API
        for provided_resource_with_provider_artifact in self.list_resources(environment):
            if (
                provided_resource_with_provider_artifact.project_name == requirement_project_name
                and provided_resource_with_provider_artifact.provided_resource.name == requirement_resource_name
            ):
                return provided_resource_with_provider_artifact

        raise ResourceProviderNotFound(
            ResourceProviderReference(project_name=requirement_project_name, resource_name=requirement_resource_name)
        )

    async def teardown(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        pass

    def _ensure_namespace_exists(self, environment: Environment, api_client, namespace: str):
        """Ensure the specified Environment has a properly setup Kubernetes Namespace."""

        api = client.CoreV1Api(api_client)

        labels = generate_environment_labels(environment)

        try:
            existing_namespace = cast(client.V1Namespace, api.read_namespace(namespace))

        except client.ApiException:
            api.create_namespace(
                client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        labels=labels,
                        name=namespace,
                    )
                )
            )

        else:
            # Update labels
            existing_metadata = cast(client.V1ObjectMeta, existing_namespace.metadata)
            existing_metadata.labels.update(labels)
            api.patch_namespace(namespace, client.V1Namespace(metadata=existing_metadata))
