from __future__ import annotations

from collections.abc import Sequence
from typing import Any, NotRequired, Protocol, TypedDict

import yaml
from kubernetes import client, config, utils

from ballista_sdk.adapters.exceptions import UnknownArtifact, UnknownResourceDependency
from ballista_sdk.adapters.types import fake_artifact_types
from ballista_sdk.api.v1.models import Resource as V1Resource
from ballista_sdk.types import (
    ArtifactExecutionParameters,
    ArtifactExecutionProbe,
    ArtifactExecutionResourceDependency,
    ArtifactExecutionService,
    ArtifactExecutionVolume,
    ArtifactExecutionVolumeParameters,
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentTier,
    ExecutableArtifact,
    ExecutionParameters,
    Resource,
    ResourceWithProviderArtifact,
    Secret,
    SpecificArtifact,
    UniqueConfig,
    UniqueSecret,
)


class KubernetesMetadata(TypedDict):
    annotations: NotRequired[dict[str, str]]
    labels: NotRequired[dict[str, str]]
    name: str
    namespace: str


class KubernetesResource(TypedDict):
    apiVersion: str
    kind: str
    metadata: KubernetesMetadata
    spec: dict[str, Any]


"""

Environments:
    - cluster per environment
    - namespace per environment
    - namespace per project-environment pair

"""


PER_PROJECT_NAMESPACES = False
"""Eventually a setting in an environment to create namespaces per project."""

METADATA_MANAGED_BY = "Ballista"
METADATA_DOMAIN = "ballista.build"
METADATA_LABEL_ENVIRONMENT = f"{METADATA_DOMAIN}/environment"
METADATA_LABEL_ENVIRONMENT_TIER = f"{METADATA_DOMAIN}/environment-tier"
METADATA_LABEL_RESOURCE = f"{METADATA_DOMAIN}/resource"
METADATA_ANNOTATION_RESOURCE = f"{METADATA_DOMAIN}/resource-json"


def _get_environment_labels(environment: Environment) -> dict[str, str]:
    return {
        "app.kubernetes.io/managed-by": METADATA_MANAGED_BY,
        METADATA_LABEL_ENVIRONMENT: environment.id,
        METADATA_LABEL_ENVIRONMENT_TIER: str(environment.tier),
    }


def _get_selector_labels(environment: Environment, bolt: Bolt, artifact: ExecutableArtifact) -> dict[str, str]:
    """Get labels specifically for targeting Pods."""

    return {
        METADATA_LABEL_ENVIRONMENT: environment.id,
        "app.kubernetes.io/part-of": bolt.project_id,
        "app.kubernetes.io/name": artifact.id,
    }


def _get_metadata_labels(environment: Environment, bolt: Bolt, artifact: ExecutableArtifact) -> KubernetesMetadata:
    return _get_environment_labels(environment) | {
        "app.kubernetes.io/instance": f"{artifact.id}-{bolt.version}",
        "app.kubernetes.io/part-of": bolt.project_id,
        "app.kubernetes.io/name": artifact.id,
        "app.kubernetes.io/version": bolt.version,
    }


def _get_bolt_kubernetes_namespace(environment: Environment, bolt: Bolt) -> str:
    # TODO: This will need to be changed and allow customization
    if PER_PROJECT_NAMESPACES:
        return f"{bolt.project_id}-{environment.id}"
    else:
        return environment.id


def _get_artifact_kubernetes_name(
    environment: Environment, bolt: Bolt, artifact: ExecutableArtifact, name: str | None = None
) -> str:
    # TODO: This will need to be changed and allow customization
    if PER_PROJECT_NAMESPACES:
        return artifact.id + (f"-{name}" if name else "")
    else:
        return f"{bolt.project_id}-{artifact.id}" + (f"-{name}" if name else "")


def _get_artifact_metadata(
    environment: Environment, bolt: Bolt, artifact: ExecutableArtifact, name: str | None = None
) -> KubernetesMetadata:
    return {
        "labels": _get_metadata_labels(environment, bolt, artifact),
        "name": _get_artifact_kubernetes_name(environment, bolt, artifact, name),
        "namespace": _get_bolt_kubernetes_namespace(environment, bolt),
    }


def _generate_bolt_resources(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    bolt: Bolt,
    artifacts: Sequence[ExecutableArtifact],
    execution_parameters: ExecutionParameters,
) -> tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]]:
    """Generate Kubernetes resource definitions shared across multiple artifacts and the individual artifacts."""
    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate resources.")

    artifact_resources = {
        artifact.id: _generate_artifact_resources(
            adapter=adapter,
            environment=environment,
            bolt=bolt,
            artifact=artifact,
            artifact_execution_parameters=execution_parameters.params_for_artifact(
                environment=environment, project_id=bolt.project_id, artifact=artifact
            ),
        )
        for artifact in artifacts
    }

    # Bolt resources
    k8s_resources: list[KubernetesResource] = []
    return k8s_resources, artifact_resources


def _generate_probe(
    probe: ArtifactExecutionProbe, services: dict[str, ArtifactExecutionService]
) -> dict[str, dict] | None:
    if probe.exec:
        return {"exec": {"command": probe.exec.commands}}

    # Get port common in grpc, http, and port probes
    port_probe = probe.grpc or probe.http or probe.tcp
    if port_probe is None:
        return None

    port = port_probe.port
    service = services.get(port_probe.service_id) if port_probe.service_id else None

    if probe.grpc:
        # GRPC cannot use a named port
        return {"grpc": {"port": service.grpc.port if service and service.grpc else port}}

    if probe.http:
        return {
            "httpGet": {"path": probe.http.path or "/healthz", "port": service.id if service and service.http else port}
        }

    if probe.tcp:
        return {"tcpSocket": {"port": service.id if service and service.tcp else port}}


def _generate_artifact_resources(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    generators = [
        generate_deployment,
        generate_services,
        generate_persistent_volume_claims,
        generate_ingresses,
        adapter.configs_adapter.generate_kubernetes_resources,
        adapter.secrets_adapter.generate_kubernetes_resources,
    ]

    k8s_resources: list[KubernetesResource] = []

    for generator in generators:
        k8s_resources += generator(
            adapter=adapter,
            environment=environment,
            bolt=bolt,
            artifact=artifact,
            artifact_execution_parameters=artifact_execution_parameters,
        )

    return k8s_resources


def _generate_yaml_files(k8s_resources: Sequence[KubernetesResource]) -> dict[str, str]:
    return {kind.lower() + ".yaml": yaml.dump(data) for kind, data in k8s_resources}


class KubernetesExecutionEnvironmentAdapter:
    _executable_artifacts: list[SpecificArtifact]
    configs_adapter: KubernetesConfigsAdapter
    secrets_adapter: KubernetesSecretsAdapter

    def __init__(self, executable_artifacts: list[SpecificArtifact] = []):
        self._executable_artifacts = executable_artifacts

        self.configs_adapter = KubernetesConfigsAdapter()
        self.secrets_adapter = KubernetesSecretsAdapter()

    @property
    def name(self) -> str:
        return "kubernetes"

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        bolt_resources, all_artifact_resources = _generate_bolt_resources(
            bolt=bolt,
            artifacts=artifacts,
            adapter=self,
            environment=environment,
            execution_parameters=execution_parameters,
        )

        api_client = self._get_kubernetes_client(environment)

        namespace = _get_bolt_kubernetes_namespace(environment, bolt)

        if True:
            # Create namespace
            api = client.CoreV1Api(api_client)
            try:
                api.read_namespace(namespace)

                # TODO: Make sure the namespace is labelled correctly.
            except client.ApiException:
                api.create_namespace(
                    client.V1Namespace(
                        metadata=client.V1ObjectMeta(
                            labels=_get_environment_labels(environment),
                            name=namespace,
                        )
                    )
                )

        [utils.create_from_dict(api_client, resource, namespace=namespace, apply=True) for resource in bolt_resources]

        for artifact_id, artifact_resources in all_artifact_resources.items():
            [
                utils.create_from_dict(api_client, resource, namespace=namespace, apply=True)
                for resource in artifact_resources
            ]

    def get_artifact_from_reference(
        self, artifact_reference: ArtifactReference, environment: Environment
    ) -> SpecificArtifact:
        for artifact, version, project_id in self._executable_artifacts:
            if (
                artifact_reference.artifact_id == artifact.id
                and artifact_reference.version == version
                and artifact_reference.project_id == project_id
            ):
                return SpecificArtifact(artifact, version, project_id)

        # TODO: We don't have a way to store and then retrieve a complete Artifact yet.
        raise UnknownArtifact(artifact_reference)

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return fake_artifact_types()

    def list_environments(self) -> list[Environment]:
        environments = []
        # Use the current kubeconfig context
        _, context = config.list_kube_config_contexts()

        if context:
            api_client = config.new_client_from_config(context=context["name"])

            # TODO: We don't have an Environment type, so use Namespace with labels for now.
            corev1_api = client.CoreV1Api(api_client=api_client)
            ballista_namespaces = corev1_api.list_namespace(
                label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT},{METADATA_LABEL_ENVIRONMENT_TIER}"
            )

            environments.extend(
                [
                    Environment(
                        id=n.metadata.name,
                        name=n.metadata.name,
                        tier=EnvironmentTier(n.metadata.labels.get(METADATA_LABEL_ENVIRONMENT_TIER)),
                    )
                    for n in ballista_namespaces.items
                ]
            )

        return environments

    def list_executable_artifacts(self, environment: Environment) -> list[ArtifactReference]:
        api_client = self._get_kubernetes_client(environment)

        # 1:1 ExecutableArtifact:Deployment
        api = client.AppsV1Api(api_client)
        deployments = api.list_deployment_for_all_namespaces(
            label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT}={environment.id}"
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

    def list_resources(self, environment: Environment) -> list[ResourceWithProviderArtifact]:
        """List available Resources and the providing ArtifactIDReference in the specified Environment."""
        if self._executable_artifacts:
            return [
                ResourceWithProviderArtifact(
                    resource,
                    ArtifactReference(artifact.id, version, project_id),
                )
                for artifact, version, project_id in self._executable_artifacts
                for resource in artifact.provided_resources
            ]

        api_client = self._get_kubernetes_client(environment)

        # 1:1 ExecutableArtifact:Deployment
        resources = []
        api = client.AppsV1Api(api_client)
        for deployment in api.list_deployment_for_all_namespaces(
            label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT}={environment.id},{METADATA_LABEL_RESOURCE}"
        ).items:
            labels = deployment.metadata.labels
            resource_json = deployment.metadata.annotations.get(METADATA_ANNOTATION_RESOURCE)
            if resource_json is not None:
                try:
                    resource = V1Resource.model_validate_json(resource_json)
                    ref = (
                        resource,
                        (
                            labels["app.kubernetes.io/name"],
                            labels["app.kubernetes.io/version"],
                            labels["app.kubernetes.io/part-of"],
                        ),
                    )
                    resources.append(ref)

                except Exception as e:
                    print(e)

        return resources

    def resolve_resource_dependency(
        self, resource_dependency: ArtifactExecutionResourceDependency, environment: Environment
    ) -> ResourceWithProviderArtifact:
        for resource_with_provider_artifact in self.list_resources(environment):
            if resource_with_provider_artifact.resource.id == resource_dependency.resource_id:
                return resource_with_provider_artifact

        raise UnknownResourceDependency(resource_dependency.resource_id)

    def teardown(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        pass

    def _get_kubernetes_client(self, environment: Environment) -> client.ApiClient:
        # TODO: Get context where environment is
        context = None

        return config.new_client_from_config(context=context)


class KubernetesResourcesGenerator(Protocol):
    """Generates a Sequence of KubernetesResources."""

    @staticmethod
    def __call__(
        adapter: KubernetesExecutionEnvironmentAdapter,
        environment: Environment,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        artifact_execution_parameters: ArtifactExecutionParameters,
    ) -> Sequence[KubernetesResource]: ...


def generate_deployment(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    execution = artifact.execution

    metadata = _get_artifact_metadata(environment, bolt, artifact)

    env = []
    env_from = []

    # TODO: This will need a better abstraction so it can use explicit Docker registries.
    if (image := artifact.type.config.get("image")) is None:
        image = f"{bolt.project_id}_{artifact.id}:{bolt.version}"

    # Create barebones PodSpec
    container = {"name": artifact.id, "image": image}
    pod_spec = {"containers": [container]}

    # Execution Parameters Resources
    pod_resources = {"requests": {}, "limits": {}}
    compute_parameters = artifact_execution_parameters.compute
    if compute_parameters.min_cpu:
        pod_resources["requests"]["cpu"] = f"{compute_parameters.min_cpu}G"
    if compute_parameters.min_memory:
        pod_resources["requests"]["memory"] = f"{compute_parameters.min_memory}Gi"
    if compute_parameters.max_cpu:
        pod_resources["limits"]["cpu"] = f"{compute_parameters.max_cpu}G"
    if compute_parameters.max_memory:
        pod_resources["limits"]["memory"] = f"{compute_parameters.max_memory}Gi"

    if pod_resources["requests"] or pod_resources["limits"]:
        container["resources"] = pod_resources

    artifact_configs = [
        UniqueConfig(
            environment=environment,
            project_id=bolt.project_id,
            artifact_id=artifact.id,
            id=c.id,
            name=c.name,
            description=c.description,
        )
        for c in execution.configs
    ]
    artifact_secrets = [
        UniqueSecret(
            environment=environment,
            project_id=bolt.project_id,
            artifact_id=artifact.id,
            id=c.id,
            name=c.name,
            description=c.description,
        )
        for c in execution.secrets
    ]

    # Platform Resources
    if resource_dependencies := execution.resources:
        for dependency in resource_dependencies:
            resource, _ = adapter.resolve_resource_dependency(dependency, environment)

            prefix = (dependency.config.get("prefix") or resource.prefix) + "_"

            has_shared_configs = False
            for config in resource.configs:
                if config.shared:
                    has_shared_configs = True
                else:
                    artifact_configs.append(
                        UniqueConfig(
                            environment=environment,
                            project_id=bolt.project_id,
                            artifact_id=artifact.id,
                            id=config.id,
                            name=config.name,
                            description=config.description,
                        )
                    )

            if has_shared_configs:
                env_from.append(
                    {
                        "prefix": prefix,
                        "configMapRef": {
                            "name": adapter.configs_adapter.get_shared_resource_name(environment, resource),
                            "optional": False,
                        },
                    }
                )

            has_shared_secrets = False
            for secret in resource.secrets:
                if secret.shared:
                    has_shared_secrets = True
                else:
                    artifact_secrets.append(
                        UniqueSecret(
                            environment=environment,
                            project_id=bolt.project_id,
                            artifact_id=artifact.id,
                            id=secret.id,
                            name=secret.name,
                            description=secret.description,
                        )
                    )

            if has_shared_secrets:
                env_from.append(
                    {
                        "prefix": prefix,
                        "secretRef": {
                            "name": adapter.secrets_adapter.get_shared_resource_name(environment, resource),
                            "optional": False,
                        },
                    }
                )

    # Secrets
    if artifact_secrets:
        # Service secrets are either first or second item
        env_from.insert(0, {"secretRef": {"name": metadata["name"], "optional": False}})

    # Configs
    if artifact_configs:
        # Service configs are always first item and marked as optional
        env_from.insert(0, {"configMapRef": {"name": metadata["name"], "optional": True}})

    # Services
    services_added = {}
    for service in execution.services:
        port_service = service.grpc or service.http or service.tcp
        if port_service is None:
            # TODO: WTF is it, then? Probably need a better abstraction haha
            continue

        services_added[service.id] = service

        key = f"{service.id.upper()}_SERVICE"
        host = "localhost"
        path = "/"
        container["ports"] = container.get("ports", []) + [{"containerPort": port_service.port, "name": service.id}]
        env.append({"name": f"{key}_PORT", "value": str(port_service.port)})

        external_service_parameters = artifact_execution_parameters.external_services.get(service.id)
        if external_service_parameters and external_service_parameters.host:
            host = external_service_parameters.host
            if external_service_parameters.path:
                path = external_service_parameters.path

        env.append({"name": f"{key}_HOST", "value": host})
        if service.http:
            env.append({"name": f"{key}_PATH", "value": path})

    # Healthchecks; processed after Services since they can refer to them
    if healthchecks := execution.healthchecks:
        if healthchecks.alive and (liveness_probe := _generate_probe(healthchecks.alive, services_added)):
            container["livenessProbe"] = liveness_probe
        if healthchecks.ready and (readiness_probe := _generate_probe(healthchecks.ready, services_added)):
            container["readinessProbe"] = readiness_probe
        if healthchecks.started and (startup_probe := _generate_probe(healthchecks.started, services_added)):
            container["startupProbe"] = startup_probe

    if env:
        container["env"] = env
    if env_from:
        container["envFrom"] = env_from

    # TODO
    # securityContext
    #
    # Volumes
    if execution.volumes:
        volumes = []
        volume_mounts = []
        for volume in execution.volumes:
            # Mount Path
            volume_mount = {"mountPath": volume.path, "name": volume.id}
            volume_mounts.append(volume_mount)

            execution_volume_parameters = artifact_execution_parameters.volumes.get(volume.id)
            if execution_volume_parameters and execution_volume_parameters.path:
                # Set a subPath in the volume for this specific mount
                volume_mount["subPath"] = f"{execution_volume_parameters.path}/{volume.id}"

            if volume.persistent:
                volumes.append(
                    {
                        "name": volume.id,
                        "persistentVolumeClaim": {
                            "claimName": _get_artifact_kubernetes_name(environment, bolt, artifact, volume.id)
                        },
                    }
                )

            else:
                # Add an ephemeral volume claim to the PodTemplate
                volumes.append(
                    {
                        "name": volume.id,
                        "ephemeral": {
                            "volumeClaimTemplate": {
                                "metadata": {"labels": metadata["labels"]},
                                "spec": _get_volume_claim(volume, ["ReadWriteOnce"], execution_volume_parameters),
                            }
                        },
                    }
                )

        if volume_mounts:
            container["volumeMounts"] = volume_mounts

        if volumes:
            pod_spec["volumes"] = volumes

    pod_template = {
        "metadata": metadata,
        "spec": pod_spec,
    }

    deployment_metadata = metadata
    for provided_resource in artifact.provided_resources:
        # JSON a resource with the V1 API and stuff it into annotations
        metadata["labels"][METADATA_LABEL_RESOURCE] = provided_resource.id

        resource_model = V1Resource.model_validate(provided_resource)

        deployment_metadata = metadata.copy()
        deployment_metadata["annotations"] = {METADATA_ANNOTATION_RESOURCE: resource_model.model_dump_json()}
        break

    # Deployment
    return [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": deployment_metadata,
            "spec": {
                "selector": {"matchLabels": _get_selector_labels(environment, bolt, artifact)},
                "strategy": {
                    "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                    "type": "RollingUpdate",
                },
                "template": pod_template,
            },
        }
    ]


def generate_services(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    ports = []
    for service in artifact.execution.services:
        if http_service := (service.grpc or service.http):
            ports.append({"port": http_service.port, "name": service.id, "targetPort": service.id})
        elif service.tcp:
            # TODO: Need to create a different kind of service for TCP traffic?
            ports.append({"port": service.tcp.port, "name": service.id, "targetPort": service.id})

    if not ports:
        return []

    return [
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": _get_artifact_metadata(environment, bolt, artifact),
            "spec": {"selector": _get_selector_labels(environment, bolt, artifact), "ports": ports},
        }
    ]


def _get_volume_claim(
    volume: ArtifactExecutionVolume,
    access_modes: list[str],
    execution_volume_parameters: ArtifactExecutionVolumeParameters | None,
) -> dict:
    volume_claim = {"accessModes": access_modes, "resources": {"requests": {"storage": f"{volume.capacity}G"}}}

    # Claim resources
    if execution_volume_parameters:
        if execution_volume_parameters.max_capacity:
            volume_claim["resources"]["limits"] = {"storage": f"{execution_volume_parameters.max_capacity}G"}

        if execution_volume_parameters.type:
            volume_claim["storageClassName"] = execution_volume_parameters.type

    return volume_claim


def generate_persistent_volume_claims(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    resources = []
    for volume in artifact.execution.volumes:
        if volume.persistent is False:
            continue

        execution_volume_parameters = artifact_execution_parameters.volumes.get(volume.id)

        resources.append(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": _get_artifact_metadata(environment, bolt, artifact, volume.id),
                "spec": _get_volume_claim(volume, ["ReadWriteMany"], execution_volume_parameters),
            }
        )

    return resources


def generate_ingresses(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    # external_service_parameters = {artifact_execution_parameters.external_services
    hosts = {}
    for service in artifact.execution.services:
        http_service = service.http or service.grpc
        if not http_service:
            # Only do HTTP service right now
            continue

        service_execution_parameters = artifact_execution_parameters.external_services.get(service.id)
        if service_execution_parameters is None:
            continue

        path = {
            "path": service_execution_parameters.path or "/",
            "pathType": "Prefix",
            "backend": {
                "service": {
                    "name": service.id,
                    "port": {"number": service_execution_parameters.port or http_service.port},
                }
            },
        }

        host = service_execution_parameters.host
        if host in hosts:
            hosts[host]["http"]["paths"].append(path)
        else:
            hosts[host] = {"host": host, "http": {"paths": [path]}}

    if not hosts:
        return []

    return [
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": _get_artifact_metadata(environment, bolt, artifact),
            "spec": {"rules": list(hosts.values())},
        }
    ]


class BaseKubernetesSettingsAdapter:
    def get_shared_resource_name(self, environment: Environment, resource: Resource) -> str:
        return f"{resource.id}-shared"

    def get_artifact_resource_names(
        self, environment: Environment, bolt: Bolt, artifact: ExecutableArtifact
    ) -> list[str]:
        return []

    def generate_kubernetes_resources(
        self,
        adapter: KubernetesExecutionEnvironmentAdapter,
        environment: Environment,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        artifact_execution_parameters: ArtifactExecutionParameters,
    ) -> list[KubernetesResource]:
        return []


class KubernetesConfigsAdapter(BaseKubernetesSettingsAdapter):
    def get_configmaps(self, environment: Environment, bolt: Bolt, artifact: ExecutableArtifact) -> list[str]:
        """Get list of ConfigMaps needed for ExecutableArtifact."""
        return []


class KubernetesSecretsAdapter(BaseKubernetesSettingsAdapter):
    def get_namespace_name(self, secret: Secret) -> str:
        return ""


class ExternalSecretsAdapter(BaseKubernetesSettingsAdapter):
    pass
