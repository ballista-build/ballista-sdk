from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from kubernetes import client, config, utils

from ballista_sdk.adapters.exceptions import ArtifactNotFound, ProvidedResourceNotFound, ProvidedServiceNotFound
from ballista_sdk.adapters.infrastructure import BoltInspector, resolve_artifact_requirements
from ballista_sdk.adapters.primitives import (
    ArtifactReference,
    ProvidedResourceReference,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceReference,
    ProvidedServiceWithArtifactReference,
)
from ballista_sdk.adapters.resources.transports import (
    ResourceProviderTransport,
    RESTResourceProviderTransport,
)
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentTier,
    ExecutableArtifact,
    ExecutionParameters,
    Project,
    ProvidedResource,
    ProvidedService,
    ResourceRequirement,
    ResourceStatus,
    ServiceRequirement,
    ServiceType,
)

from . import primitives
from .environments import get_environment_config, get_kubernetes_client
from .generation import (
    KubernetesInfrastructureAdapter,
    generate_bolt_kubernetes_namespace,
    generate_environment_labels,
)
from .settings import KubernetesAPIConfigsAdapter, KubernetesAPISecretsAdapter


@dataclass
class KubernetesAPIInfrastructureAdapter(KubernetesInfrastructureAdapter):
    """KubernetesInfrastructureAdapter that communicates directly via the Kubernetes API."""

    _bolts: list[Bolt] = field(default_factory=list)

    _configs_adapter: KubernetesAPIConfigsAdapter = field(default_factory=KubernetesAPIConfigsAdapter, init=False)
    _secrets_adapter: KubernetesAPISecretsAdapter = field(default_factory=KubernetesAPISecretsAdapter, init=False)

    _use_gateway: bool = field(default=False, init=False)
    """Use Gateway API instead of Ingress."""

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
        resource_providers, service_providers = await resolve_artifact_requirements(self, environment, bolt, artifacts)

        environment_config = get_environment_config(environment)

        bolt_resources, all_artifact_resources = self.generate_bolt_resources(
            bolt=bolt,
            artifacts=artifacts,
            environment=environment,
            environment_config=environment_config,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
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

    async def list_artifact_types(self, environments: Sequence[Environment]) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    async def list_bolts(
        self,
        environments: Sequence[Environment],
        project_names: Sequence[str] | None = None,
    ) -> list[Bolt]:
        if self._bolts:
            return BoltInspector.list_bolts(self._bolts, project_names=project_names)

        return []

    async def list_environments(self) -> list[Environment]:
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

    async def list_executable_artifacts(
        self,
        environments: Sequence[Environment],
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
    ) -> list[ArtifactReference]:
        if self._bolts:
            return BoltInspector.list_executable_artifacts(
                self._bolts, project_names=project_names, artifact_names=artifact_names
            )

        executable_artifacts = []
        labels = [
            f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY}",
            f"{primitives.METADATA_LABEL_ENVIRONMENT} in ({','.join([environment.name for environment in environments])})",
            primitives.METADATA_LABEL_RESOURCE,
        ]

        if project_names:
            labels.append(f"app.kubernetes.io/part-of in ({','.join(project_names)})")
        if artifact_names:
            labels.append(f"app.kubernetes.io/name in ({','.join(artifact_names)})")

        for environment in environments:
            api_client = get_kubernetes_client(environment)

            # 1:1 ExecutableArtifact:Deployment
            api = client.AppsV1Api(api_client)
            deployments = api.list_deployment_for_all_namespaces(label_selector=",".join(labels))

            for deployment in deployments.items:
                metadata_labels = deployment.metadata.labels
                executable_artifacts.append(
                    ArtifactReference(
                        project_name=metadata_labels["app.kubernetes.io/part-of"],
                        artifact_name=metadata_labels["app.kubernetes.io/name"],
                        version=metadata_labels["app.kubernetes.io/version"],
                    )
                )

        return executable_artifacts

    async def list_projects(self, environments: Sequence[Environment]) -> list[Project]:
        if self._bolts:
            return BoltInspector.list_projects(self._bolts)

        projects: set[Project] = set()
        for environment in environments:
            api_client = get_kubernetes_client(environment)

            # 1:1 ExecutableArtifact:Deployment
            api = client.AppsV1Api(api_client)
            deployments = api.list_deployment_for_all_namespaces(
                label_selector=f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY},{primitives.METADATA_LABEL_ENVIRONMENT}={environment.name}"
            )

            for deployment in deployments.items:
                metadata_labels = deployment.metadata.labels
                projects.add(Project(name=metadata_labels["app.kubernetes.io/part-of"]))

        return list(projects)

    async def list_provided_resources(
        self,
        environments: Sequence[Environment],
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
    ) -> list[ProvidedResourceWithArtifactReference]:
        """List Provided Resources and the providing ArtifactIDReference in the specified Environment."""
        if self._bolts:
            return BoltInspector.list_provided_resources(
                self._bolts, project_names=project_names, artifact_names=artifact_names, resource_names=resource_names
            )

        # 1:1 ExecutableArtifact:Deployment
        resources = []

        labels = [
            f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY}",
            f"{primitives.METADATA_LABEL_ENVIRONMENT} in ({','.join([environment.name for environment in environments])})",
        ]

        if project_names:
            labels.append(f"app.kubernetes.io/part-of in ({','.join(project_names)})")
        if artifact_names:
            labels.append(f"app.kubernetes.io/name in ({','.join(artifact_names)})")
        if resource_names:
            # Use label selector for resource names
            labels.append(f"{primitives.METADATA_LABEL_RESOURCE} in ({','.join(resource_names)})")
        else:
            # Otherwise look for any resource
            labels.append(primitives.METADATA_LABEL_RESOURCE)

        for environment in environments:
            api_client = get_kubernetes_client(environment)
            api = client.AppsV1Api(api_client)

            for deployment in api.list_deployment_for_all_namespaces(label_selector=",".join(labels)).items:
                metadata = cast(client.models.V1ObjectMeta, deployment.metadata)
                metadata_labels = cast(dict[str, str], metadata.labels)
                provided_resource_json = metadata.annotations.get(primitives.METADATA_ANNOTATION_RESOURCE)
                if provided_resource_json is not None:
                    try:
                        provided_resource = ProvidedResource.model_validate_json(provided_resource_json)
                        ref = ProvidedResourceWithArtifactReference(
                            provided_resource=provided_resource,
                            artifact_reference=ArtifactReference(
                                project_name=metadata_labels["app.kubernetes.io/part-of"],
                                artifact_name=metadata_labels["app.kubernetes.io/name"],
                                version=metadata_labels["app.kubernetes.io/version"],
                            ),
                        )
                        resources.append(ref)

                    except Exception as e:
                        print(e)

        return resources

    async def list_provided_services(
        self,
        environments: Sequence[Environment],
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
    ) -> list:
        if self._bolts:
            return BoltInspector.list_provided_services(
                self._bolts, project_names=project_names, artifact_names=artifact_names, service_names=service_names
            )

        # TODO: This won't work when there are Virtual services
        services = []

        labels = [
            f"app.kubernetes.io/managed-by={primitives.METADATA_MANAGED_BY}",
            f"{primitives.METADATA_LABEL_ENVIRONMENT} in ({','.join([environment.name for environment in environments])})",
        ]

        if project_names:
            labels.append(f"app.kubernetes.io/part-of in ({','.join(project_names)})")
        if artifact_names:
            labels.append(f"app.kubernetes.io/name in ({','.join(artifact_names)})")
        if service_names:
            labels.append(f"{primitives.METADATA_LABEL_SERVICE} in ({','.join(service_names)})")
        else:
            labels.append(primitives.METADATA_LABEL_SERVICE)

        for environment in environments:
            api_client = get_kubernetes_client(environment)
            api = client.CoreV1Api(api_client)

            for service in api.list_service_for_all_namespaces(label_selector=",".join(labels)).items:
                metadata = cast(client.models.V1ObjectMeta, service.metadata)
                metadata_labels = cast(dict[str, str], metadata.labels)
                provided_service_json = metadata.annotations.get(primitives.METADATA_ANNOTATION_SERVICE)
                if provided_service_json is not None:
                    try:
                        provided_service = ProvidedService.model_validate_json(provided_service_json)
                        ref = ProvidedServiceWithArtifactReference(
                            provided_service=provided_service,
                            artifact_reference=ArtifactReference(
                                project_name=metadata_labels["app.kubernetes.io/part-of"],
                                artifact_name=metadata_labels["app.kubernetes.io/name"],
                                version=metadata_labels["app.kubernetes.io/version"],
                            ),
                        )
                        services.append(ref)

                    except Exception as e:
                        print(e)

        return services

    async def list_resources(
        self,
        environments: Sequence[Environment],
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
        resource_statuses: Sequence[ResourceStatus] | None = None,
    ) -> list:
        return []

    async def list_services(
        self,
        environments: Sequence[Environment],
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
        service_types: Sequence[ServiceType] | None = None,
    ) -> list:
        return []

    async def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> tuple[Bolt, Artifact]:
        if self._bolts:
            return BoltInspector.resolve_artifact_reference(self._bolts, artifact_reference)

        # TODO: Do this when the bolts are stored
        raise ArtifactNotFound(artifact_reference)

    async def resolve_resource_provider_transport(
        self,
        environment: Environment,
        provided_resource_with_artifact: ProvidedResourceWithArtifactReference,
        bolt: Bolt | None = None,
    ) -> ResourceProviderTransport:
        resource = provided_resource_with_artifact.provided_resource

        if resource.transport:
            artifact_reference = provided_resource_with_artifact.artifact_reference
            bolt, artifact = await self.resolve_artifact_reference(environment, artifact_reference)

            if rest_transport := resource.transport.rest:
                port = None

                if artifact.execution and artifact.execution.provides:
                    for service in artifact.execution.provides.services:
                        if service.name == rest_transport.service and service.http:
                            port = service.http
                            break

                if port is None:
                    raise ValueError("BAD SERVICE REFERENCE")

                ref_name = f"{artifact_reference.project_name}-{artifact_reference.artifact_name}"

                return RESTResourceProviderTransport(
                    ProvidedResourceReference(
                        project_name=artifact_reference.project_name,
                        resource_name=resource.name,
                    ),
                    f"{ref_name}:{port}{rest_transport.path}",
                )

        raise ValueError()

    async def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirement
    ) -> ProvidedResourceWithArtifactReference:
        if self._bolts:
            return BoltInspector.resolve_resource_requirement(self._bolts, resource_requirement)

        requirement_project_name = resource_requirement.project_name
        requirement_resource_name = resource_requirement.resource_name

        provided_resources = await self.list_provided_resources(
            [environment],
            project_names=[requirement_project_name],
            resource_names=[requirement_resource_name],
        )
        for provided_resource_with_provider_artifact in provided_resources:
            return provided_resource_with_provider_artifact

        raise ProvidedResourceNotFound(
            ProvidedResourceReference(
                project_name=requirement_project_name,
                resource_name=requirement_resource_name,
            )
        )

    async def resolve_service_requirement(
        self, environment: Environment, service_requirement: ServiceRequirement
    ) -> ProvidedServiceWithArtifactReference:
        if self._bolts:
            return BoltInspector.resolve_service_requirement(self._bolts, service_requirement)

        requirement_project_name = service_requirement.project_name
        requirement_artifact_name = service_requirement.artifact_name
        requirement_service_name = service_requirement.service_name

        provided_resources = await self.list_provided_services(
            [environment],
            project_names=[requirement_project_name],
            artifact_names=[requirement_artifact_name],
            service_names=[requirement_service_name],
        )
        for provided_resource_with_provider_artifact in provided_resources:
            return provided_resource_with_provider_artifact

        raise ProvidedServiceNotFound(
            ProvidedServiceReference(
                project_name=requirement_project_name,
                artifact_name=requirement_artifact_name,
                service_name=requirement_service_name,
            )
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
