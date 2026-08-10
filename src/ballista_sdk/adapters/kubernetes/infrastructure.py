from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Literal

from kubernetes import client, config, utils
from kubernetes.client.api_client import ApiClient
from kubernetes.client.exceptions import ApiException
from pydantic import ValidationError

from ballista_sdk.adapters.exceptions import (
    ArtifactNotFound,
    BoltNotFound,
    ProvidedResourceNotFound,
    ProvidedServiceNotFound,
)
from ballista_sdk.adapters.infrastructure import resolve_artifact_requirements
from ballista_sdk.adapters.primitives import (
    ArtifactReference,
    BoltReference,
    ProjectReference,
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
    DefaultExecutionParameters,
    Environment,
    EnvironmentTier,
    ExecutionParameters,
    ExternalizedServiceParameters,
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

LOGGER = logging.getLogger("ballista")


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

    async def _get_api_client(self, environment: Environment) -> ApiClient:
        return get_kubernetes_client(environment)

    async def deploy(self, bolt: Bolt, environment: Environment):
        resource_providers, service_providers = await resolve_artifact_requirements(self, environment, bolt)

        environment_config = get_environment_config(environment)

        execution_parameters = await self.determine_execution_parameters(bolt, environment)

        bolt_resources, all_artifact_resources = self.generate_bolt_resources(
            bolt=bolt,
            environment=environment,
            environment_config=environment_config,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
        )

        api_client = await self._get_api_client(environment)

        namespace = generate_bolt_kubernetes_namespace(environment, environment_config, bolt)

        if environment_config.ensure_namespaces:
            self._ensure_namespace_exists(environment, api_client, namespace)

        for resource in bolt_resources + [
            resource for artifact_resources in all_artifact_resources.values() for resource in artifact_resources
        ]:
            try:
                utils.create_from_dict(api_client, resource, namespace=namespace, apply=True)
            except Exception:
                LOGGER.exception("Error applying resource.")

    async def determine_execution_parameters(self, bolt: Bolt, environment: Environment) -> ExecutionParameters:
        api_client = await self._get_api_client(environment)
        corev1_api = client.CoreV1Api(api_client=api_client)
        appsv1_api = client.AppsV1Api(api_client=api_client)
        networkingv1_api = client.NetworkingV1Api(api_client=api_client)

        # Get initial from somewhere
        initial = DefaultExecutionParameters()
        execution_parameters = ExecutionParameters(initial=initial)

        environment_label_selector = ",".join(
            [
                f"{primitives.METADATA_LABEL_APP_MANAGED_BY}={primitives.METADATA_MANAGED_BY}",
                f"{primitives.METADATA_LABEL_ENVIRONMENT}={environment.name}",
                f"{primitives.METADATA_LABEL_ENVIRONMENT_TIER}={environment.tier}",
            ]
        )

        # Environment parameters are on namespaces
        namespace_response = corev1_api.list_namespace(label_selector=environment_label_selector)
        for namespace in namespace_response.items:
            if not namespace.metadata or not namespace.metadata.labels or not namespace.metadata.annotations:
                continue

            metadata_labels = namespace.metadata.labels
            environment_name = metadata_labels.get(primitives.METADATA_LABEL_ENVIRONMENT)
            annotation = namespace.metadata.annotations.get(primitives.METADATA_ANNOTATION_DEFAULT_EXECUTION_PARAMETERS)
            if not environment_name or not annotation:
                continue

            try:
                default_execution_parameters = DefaultExecutionParameters.model_validate_json(annotation)
                execution_parameters.environments[environment_name] = default_execution_parameters
            except ValidationError:
                pass

        project_label_selector = ",".join(
            [environment_label_selector, f"{primitives.METADATA_LABEL_APP_PART_OF}={bolt.project}"]
        )

        # TODO: Nothing for Project parameters

        # Artifact parameters are on Deployments
        deployment_response = appsv1_api.list_deployment_for_all_namespaces(
            label_selector=f"{project_label_selector},{primitives.METADATA_LABEL_APP_NAME}"
        )
        for deployment in deployment_response.items:
            if not deployment.metadata or not deployment.metadata.labels or not deployment.metadata.annotations:
                continue

            metadata_labels = deployment.metadata.labels
            environment_name = metadata_labels.get(primitives.METADATA_LABEL_ENVIRONMENT)
            project_name = metadata_labels.get(primitives.METADATA_LABEL_APP_PART_OF)
            artifact_name = metadata_labels.get(primitives.METADATA_LABEL_APP_NAME)
            annotation = deployment.metadata.annotations.get(
                primitives.METADATA_ANNOTATION_DEFAULT_EXECUTION_PARAMETERS
            )
            if not environment_name or not project_name or not artifact_name or not annotation:
                continue

            try:
                default_execution_parameters = DefaultExecutionParameters.model_validate_json(annotation)
                execution_parameters.artifacts[(environment_name, project_name, artifact_name)] = (
                    default_execution_parameters
                )
            except ValidationError:
                pass

        # List all ingresses with the appropriate labels
        ingress_response = networkingv1_api.list_ingress_for_all_namespaces(
            label_selector=f"{project_label_selector},{primitives.METADATA_LABEL_APP_NAME}"
        )
        for ingress in ingress_response.items:
            if not ingress.metadata or not ingress.metadata.labels or not ingress.metadata.annotations:
                continue

            metadata_labels = ingress.metadata.labels
            environment_name = metadata_labels.get(primitives.METADATA_LABEL_ENVIRONMENT)
            project_name = metadata_labels.get(primitives.METADATA_LABEL_APP_PART_OF)
            artifact_name = metadata_labels.get(primitives.METADATA_LABEL_APP_NAME)
            service_name = metadata_labels.get(primitives.METADATA_LABEL_SERVICE)
            annotation = ingress.metadata.annotations.get(primitives.METADATA_ANNOTATION_EXTERNALIZED_SERVICE)
            if not environment_name or not project_name or not artifact_name or not service_name or not annotation:
                continue

            try:
                externalized_service = ExternalizedServiceParameters.model_validate_json(annotation)
                execution_parameters.external_services[
                    (environment_name, project_name, artifact_name, service_name)
                ] = externalized_service
            except ValidationError:
                pass

        # Volumes are stuffed in ???
        return execution_parameters

    async def interact(self, bolt: Bolt, environment: Environment):
        raise NotImplementedError("No interactive session support.")

    async def list_artifacts(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        buildable: bool | None = None,
        executable: bool | None = None,
    ) -> list[ArtifactReference]:
        artifacts = []
        labels = [
            f"{primitives.METADATA_LABEL_APP_MANAGED_BY}={primitives.METADATA_MANAGED_BY}",
            f"{primitives.METADATA_LABEL_ENVIRONMENT} in ({','.join([environment.name for environment in environments])})",
        ]

        if project_names:
            labels.append(f"{primitives.METADATA_LABEL_APP_PART_OF} in ({','.join(project_names)})")
        if artifact_names:
            labels.append(f"{primitives.METADATA_LABEL_APP_NAME} in ({','.join(artifact_names)})")

        for environment in environments:
            api_client = await self._get_api_client(environment)

            api = client.AppsV1Api(api_client)
            deployments = api.list_deployment_for_all_namespaces(label_selector=",".join(labels))

            for deployment in deployments.items:
                if not deployment.metadata or not deployment.metadata.labels:
                    continue

                artifact_reference = _get_artifact_reference_from_metadata(deployment.metadata)
                if not artifact_reference:
                    continue

                artifacts.append(artifact_reference)

        return artifacts

    async def list_artifact_types(self, environments: Collection[Environment]) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    async def list_bolts(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
    ) -> list[BoltReference]:
        return []

    async def list_environments(self) -> list[Environment]:
        environments = []
        # Use the current kubeconfig context
        _, current_context = config.list_kube_config_contexts()

        if current_context:
            api_client = config.new_client_from_config(context=current_context["name"])

            with api_client:
                # TODO: We don't have an Environment type, so use Namespace with labels for now.
                corev1_api = client.CoreV1Api(api_client=api_client)
                namespace_response = corev1_api.list_namespace(
                    label_selector=f"{primitives.METADATA_LABEL_APP_MANAGED_BY}={primitives.METADATA_MANAGED_BY},{primitives.METADATA_LABEL_ENVIRONMENT},{primitives.METADATA_LABEL_ENVIRONMENT_TIER}",
                )

                for namespace in namespace_response.items:
                    if not namespace.metadata or not namespace.metadata.labels:
                        continue

                    environment_name = namespace.metadata.labels.get(primitives.METADATA_LABEL_ENVIRONMENT)
                    environment_tier = namespace.metadata.labels.get(primitives.METADATA_LABEL_ENVIRONMENT_TIER)

                    if not environment_name or not environment_tier:
                        continue

                    environments.append(Environment(name=environment_name, tier=EnvironmentTier(environment_tier)))

        return environments

    async def list_projects(
        self, environments: Collection[Environment], *, project_names: Collection[str] | None = None
    ) -> list[ProjectReference]:
        projects: set[ProjectReference] = set()
        for environment in environments:
            api_client = await self._get_api_client(environment)

            # 1:1 ExecutableArtifact:Deployment
            api = client.AppsV1Api(api_client)
            deployments = api.list_deployment_for_all_namespaces(
                label_selector=f"{primitives.METADATA_LABEL_APP_MANAGED_BY}={primitives.METADATA_MANAGED_BY},{primitives.METADATA_LABEL_ENVIRONMENT}={environment.name}"
            )

            for deployment in deployments.items:
                if not deployment.metadata or not deployment.metadata.labels:
                    continue

                metadata_labels = deployment.metadata.labels
                project_name = metadata_labels.get(primitives.METADATA_LABEL_APP_PART_OF)

                if not project_name:
                    continue

                projects.add(ProjectReference(project_name=project_name))

        return list(projects)

    async def list_provided_resources(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
    ) -> list[ProvidedResourceWithArtifactReference]:
        """List Provided Resources and the providing ArtifactIDReference in the specified Environment."""
        provided_resources = []

        labels = [
            f"{primitives.METADATA_LABEL_APP_MANAGED_BY}={primitives.METADATA_MANAGED_BY}",
            f"{primitives.METADATA_LABEL_ENVIRONMENT} in ({','.join([environment.name for environment in environments])})",
        ]

        if project_names:
            labels.append(f"{primitives.METADATA_LABEL_APP_PART_OF} in ({','.join(project_names)})")
        if artifact_names:
            labels.append(f"{primitives.METADATA_LABEL_APP_NAME} in ({','.join(artifact_names)})")
        # Always look for any resource as we can't attach individual Resources until we get CRDs
        labels.append(primitives.METADATA_LABEL_RESOURCE)

        for environment in environments:
            api_client = await self._get_api_client(environment)
            api = client.AppsV1Api(api_client)

            for deployment in api.list_deployment_for_all_namespaces(label_selector=",".join(labels)).items:
                if not deployment.metadata or not deployment.metadata.labels or not deployment.metadata.annotations:
                    continue

                artifact_reference = _get_artifact_reference_from_metadata(deployment.metadata)
                # We need to decode the entire Artifact JSON to get the ProvidedResources YIKES
                annotation = deployment.metadata.annotations.get(primitives.METADATA_ANNOTATION_ARTIFACT)
                if not artifact_reference or not annotation:
                    continue

                try:
                    artifact = Artifact.model_validate_json(annotation)
                    if not artifact.execution or not artifact.execution.provides.resources:
                        continue

                    for provided_resource in artifact.execution.provides.resources:
                        if not resource_names or provided_resource.name in resource_names:
                            provided_resources.append(
                                ProvidedResourceWithArtifactReference(
                                    provided_resource=provided_resource, artifact_reference=artifact_reference
                                )
                            )
                except ValidationError:
                    pass

        return provided_resources

    async def list_provided_services(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
    ) -> list[ProvidedServiceWithArtifactReference]:
        provided_services = []

        labels = [
            f"{primitives.METADATA_LABEL_APP_MANAGED_BY}={primitives.METADATA_MANAGED_BY}",
            f"{primitives.METADATA_LABEL_ENVIRONMENT} in ({','.join([environment.name for environment in environments])})",
        ]

        if project_names:
            labels.append(f"{primitives.METADATA_LABEL_APP_PART_OF} in ({','.join(project_names)})")
        if artifact_names:
            labels.append(f"{primitives.METADATA_LABEL_APP_NAME} in ({','.join(artifact_names)})")
        if service_names:
            labels.append(f"{primitives.METADATA_LABEL_SERVICE} in ({','.join(service_names)})")
        else:
            labels.append(primitives.METADATA_LABEL_SERVICE)

        for environment in environments:
            api_client = await self._get_api_client(environment)
            api = client.CoreV1Api(api_client)

            for service in api.list_service_for_all_namespaces(label_selector=",".join(labels)).items:
                if not service.metadata or not service.metadata.labels or not service.metadata.annotations:
                    continue

                artifact_reference = _get_artifact_reference_from_metadata(service.metadata)
                annotation = service.metadata.annotations.get(primitives.METADATA_ANNOTATION_SERVICE)
                if not artifact_reference or not annotation:
                    continue

                try:
                    provided_service = ProvidedService.model_validate_json(annotation)
                    provided_services.append(
                        ProvidedServiceWithArtifactReference(
                            provided_service=provided_service, artifact_reference=artifact_reference
                        )
                    )
                except ValidationError:
                    pass

        return provided_services

    async def list_resources(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_project_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
        resource_statuses: Collection[ResourceStatus] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedResourceReference, ResourceStatus]]:
        return []

    async def list_services(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_project_names: Collection[str] | None = None,
        service_artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedServiceReference, ServiceType]]:
        return []

    async def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> Artifact:
        labels = [
            f"{primitives.METADATA_LABEL_APP_MANAGED_BY}={primitives.METADATA_MANAGED_BY}",
            f"{primitives.METADATA_LABEL_ENVIRONMENT}={environment.name}",
            f"{primitives.METADATA_LABEL_APP_PART_OF}={artifact_reference.project_name}",
            f"{primitives.METADATA_LABEL_APP_NAME}={artifact_reference.artifact_name}",
            f"{primitives.METADATA_LABEL_APP_VERSION}={artifact_reference.version}",
        ]

        api_client = await self._get_api_client(environment)
        api = client.AppsV1Api(api_client)
        deployments = api.list_deployment_for_all_namespaces(label_selector=",".join(labels))

        for deployment in deployments.items:
            if not deployment.metadata or not deployment.metadata.annotations:
                continue

            annotation = deployment.metadata.annotations.get(primitives.METADATA_ANNOTATION_ARTIFACT)
            if not annotation:
                continue

            try:
                artifact = Artifact.model_validate_json(annotation)

                if artifact.name == artifact_reference.artifact_name:
                    return artifact

            except ValidationError:
                pass

        raise ArtifactNotFound(artifact_reference)

    async def resolve_bolt_reference(self, environment: Environment, bolt_reference: BoltReference) -> Bolt:
        raise BoltNotFound(bolt_reference)

    async def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirement
    ) -> ProvidedResourceWithArtifactReference:
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

    async def remove(self, bolt: Bolt, environment: Environment):
        pass

    async def transport_resource_provider(
        self,
        environment: Environment,
        provided_resource_with_artifact: ProvidedResourceWithArtifactReference,
        bolt: Bolt | None = None,
    ) -> ResourceProviderTransport:
        resource = provided_resource_with_artifact.provided_resource

        if resource.transport:
            artifact_reference = provided_resource_with_artifact.artifact_reference
            artifact = await self.resolve_artifact_reference(environment, artifact_reference)

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

    def _ensure_namespace_exists(self, environment: Environment, api_client: ApiClient, namespace: str):
        """Ensure the specified Environment has a properly setup Kubernetes Namespace."""

        api = client.CoreV1Api(api_client)

        labels = generate_environment_labels(environment)

        try:
            existing_namespace = api.read_namespace(namespace)

        except ApiException:
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
            existing_metadata = existing_namespace.metadata or client.V1ObjectMeta()
            existing_metadata.labels = existing_metadata.labels or {}
            existing_metadata.labels.update(labels)
            api.patch_namespace(namespace, client.V1Namespace(metadata=existing_metadata))


def _get_artifact_reference_from_metadata(metadata: client.V1ObjectMeta) -> ArtifactReference | None:
    if labels := metadata.labels:
        project_name = labels.get(primitives.METADATA_LABEL_APP_PART_OF)
        artifact_name = labels.get(primitives.METADATA_LABEL_APP_NAME)
        version = labels.get(primitives.METADATA_LABEL_APP_VERSION)

        if project_name and artifact_name and version:
            return ArtifactReference(project_name=project_name, artifact_name=artifact_name, version=version)
