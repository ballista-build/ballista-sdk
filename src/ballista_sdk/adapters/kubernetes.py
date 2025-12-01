from __future__ import annotations

from collections.abc import Sequence
from typing import Any, NotRequired, Protocol, TypedDict

import yaml
from kubernetes import client, config, utils

from ballista_sdk.adapters.exceptions import UnknownArtifact, UnknownResourceRequirement
from ballista_sdk.api.v1 import (
    ArtifactExecutionParameters,
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentTier,
    ExecutableArtifact,
    ExecutionParameters,
    HealthcheckProbe,
    Project,
    ProjectResourceRequirement,
    Resource,
    ResourceProviderArtifactReference,
    ServiceRequirement,
    SpecificArtifact,
    VolumeExecutionParameters,
    VolumeRequirement,
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
        METADATA_LABEL_ENVIRONMENT: environment.name,
        METADATA_LABEL_ENVIRONMENT_TIER: str(environment.tier),
    }


def _get_selector_labels(environment: Environment, bolt: Bolt, artifact: ExecutableArtifact) -> dict[str, str]:
    """Get labels specifically for targeting Pods."""

    return {
        METADATA_LABEL_ENVIRONMENT: environment.name,
        "app.kubernetes.io/part-of": bolt.project,
        "app.kubernetes.io/name": artifact.name,
    }


def _get_metadata_labels(environment: Environment, bolt: Bolt, artifact: ExecutableArtifact) -> dict[str, str]:
    return _get_environment_labels(environment) | {
        "app.kubernetes.io/instance": f"{artifact.name}-{bolt.version}",
        "app.kubernetes.io/part-of": bolt.project,
        "app.kubernetes.io/name": artifact.name,
        "app.kubernetes.io/version": bolt.version,
    }


def _get_bolt_kubernetes_namespace(environment: Environment, bolt: Bolt) -> str:
    # TODO: This will need to be changed and allow customization
    if PER_PROJECT_NAMESPACES:
        return f"{bolt.project}-{environment.name}"
    else:
        return environment.name


def _get_artifact_kubernetes_name(
    environment: Environment, bolt: Bolt, artifact: ExecutableArtifact, name: str | None = None
) -> str:
    # TODO: This will need to be changed and allow customization
    if PER_PROJECT_NAMESPACES:
        return artifact.name + (f"-{name}" if name else "")
    else:
        return f"{bolt.project}-{artifact.name}" + (f"-{name}" if name else "")


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
    project: Project,
    bolt: Bolt,
    artifacts: Sequence[ExecutableArtifact],
    execution_parameters: ExecutionParameters,
) -> tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]]:
    """Generate Kubernetes resource definitions shared across multiple artifacts and the individual artifacts."""
    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate resources.")

    artifact_resources = {
        artifact.name: _generate_artifact_resources(
            adapter=adapter,
            environment=environment,
            project=project,
            bolt=bolt,
            artifact=artifact,
            artifact_execution_parameters=execution_parameters.params_for_artifact(
                environment=environment, project=project, artifact=artifact
            ),
        )
        for artifact in artifacts
    }

    # Bolt resources
    k8s_resources: list[KubernetesResource] = []
    return k8s_resources, artifact_resources


def _generate_probe(probe: HealthcheckProbe, services: dict[str, ServiceRequirement]) -> dict[str, dict] | None:
    if probe.exec:
        return {"exec": {"command": probe.exec.commands}}

    # Get port common in grpc, http, and port probes
    port_probe = probe.grpc or probe.http or probe.tcp
    if port_probe is None:
        return None

    port = port_probe.port
    service = services.get(port_probe.service) if port_probe.service else None

    if probe.grpc:
        # GRPC cannot use a named port
        return {"grpc": {"port": service.grpc if service and service.grpc else port}}

    if probe.http:
        return {
            "httpGet": {
                "path": probe.http.path or "/healthz",
                "port": service.name if service and service.http else port,
            }
        }

    if probe.tcp:
        return {"tcpSocket": {"port": service.name if service and service.tcp else port}}


def _generate_artifact_resources(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    project: Project,
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
            project=project,
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
        project: Project,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        bolt_resources, all_artifact_resources = _generate_bolt_resources(
            project=project,
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
        for artifact, version, project in self._executable_artifacts:
            if (
                artifact_reference.artifact == artifact.name
                and artifact_reference.version == version
                and artifact_reference.project == project.name
            ):
                return SpecificArtifact(artifact, version, project)

        # TODO: We don't have a way to store and then retrieve a complete Artifact yet.
        raise UnknownArtifact(artifact_reference)

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
                label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT},{METADATA_LABEL_ENVIRONMENT_TIER}"
            )

            environments.extend(
                [
                    Environment(
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
            label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT}={environment.name}"
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

    def list_resources(self, environment: Environment) -> list[ResourceProviderArtifactReference]:
        """List available Resources and the providing ArtifactIDReference in the specified Environment."""
        if self._executable_artifacts:
            return [
                ResourceProviderArtifactReference(
                    resource,
                    ArtifactReference(artifact.name, version, project.name),
                )
                for artifact, version, project in self._executable_artifacts
                for resource in artifact.provides
            ]

        api_client = self._get_kubernetes_client(environment)

        # 1:1 ExecutableArtifact:Deployment
        resources = []
        api = client.AppsV1Api(api_client)
        for deployment in api.list_deployment_for_all_namespaces(
            label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT}={environment.name},{METADATA_LABEL_RESOURCE}"
        ).items:
            labels = deployment.metadata.labels
            resource_json = deployment.metadata.annotations.get(METADATA_ANNOTATION_RESOURCE)
            if resource_json is not None:
                try:
                    resource = Resource.model_validate_json(resource_json)
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

    def resolve_resource_requirement(
        self, resource_requirement: ProjectResourceRequirement, environment: Environment
    ) -> ResourceProviderArtifactReference:
        for resource_with_provider_artifact in self.list_resources(environment):
            if (
                resource_with_provider_artifact.artifact.project == resource_requirement.project
                and resource_with_provider_artifact.resource.name == resource_requirement.resource
            ):
                return resource_with_provider_artifact

        raise UnknownResourceRequirement(resource_requirement.project, resource_requirement.resource)

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
        project: Project,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        artifact_execution_parameters: ArtifactExecutionParameters,
    ) -> Sequence[KubernetesResource]: ...


def generate_deployment(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    project: Project,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    execution = artifact.execution

    metadata = _get_artifact_metadata(environment, bolt, artifact)

    env = []
    env_from = []

    # TODO: This will need a better abstraction so it can use explicit Docker registries.
    artifact.type.docker_image
    if (image := artifact.type.docker_image.image) is None:
        image = f"{project.name}_{artifact.name}:{bolt.version}"

    # Create barebones PodSpec
    container = {"name": artifact.name, "image": image}
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

    has_artifact_configs = len(execution.configs) > 0
    has_artifact_secrets = len(execution.secrets) > 0

    # Platform Resources
    if resource_requirements := execution.resources:
        for resource_requirement in resource_requirements:
            resource, artifact_reference = adapter.resolve_resource_requirement(resource_requirement, environment)

            prefix = (resource_requirement.prefix or resource.prefix) + "_"

            has_shared_configs = False
            for config in resource.configs:
                if config.shared:
                    has_shared_configs = True
                else:
                    has_artifact_configs = True

            if has_shared_configs:
                env_from.append(
                    {
                        "prefix": prefix,
                        "configMapRef": {
                            "name": adapter.configs_adapter.get_shared_resource_name(
                                environment, artifact_reference, resource
                            ),
                            "optional": False,
                        },
                    }
                )

            has_shared_secrets = False
            for secret in resource.secrets:
                if secret.shared:
                    has_shared_secrets = True
                else:
                    has_artifact_secrets = True

            if has_shared_secrets:
                env_from.append(
                    {
                        "prefix": prefix,
                        "secretRef": {
                            "name": adapter.secrets_adapter.get_shared_resource_name(
                                environment, artifact_reference, resource
                            ),
                            "optional": False,
                        },
                    }
                )

    # Secrets
    if has_artifact_secrets:
        # Service secrets are either first or second item
        env_from.insert(0, {"secretRef": {"name": metadata["name"], "optional": False}})

    # Configs
    if has_artifact_configs:
        # Service configs are always first item and marked as optional
        env_from.insert(0, {"configMapRef": {"name": metadata["name"], "optional": True}})

    # Services
    services_added = {}
    for service in execution.services:
        service_port = service.grpc or service.http or service.tcp
        if service_port is None:
            # TODO: WTF is it, then? Probably need a better abstraction haha
            continue

        services_added[service.name] = service

        key = f"{service.name.upper()}_SERVICE"
        host = "localhost"
        path = "/"
        container["ports"] = container.get("ports", []) + [{"containerPort": service_port, "name": service.name}]
        env.append({"name": f"{key}_PORT", "value": str(service_port)})

        external_service_parameters = artifact_execution_parameters.external_services.get(service.name)
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
            volume_mount = {"mountPath": volume.path, "name": volume.name}
            volume_mounts.append(volume_mount)

            execution_volume_parameters = artifact_execution_parameters.volumes.get(volume.name)
            if execution_volume_parameters and execution_volume_parameters.path:
                # Set a subPath in the volume for this specific mount
                volume_mount["subPath"] = f"{execution_volume_parameters.path}/{volume.name}"

            if volume.persistent:
                volumes.append(
                    {
                        "name": volume.name,
                        "persistentVolumeClaim": {
                            "claimName": _get_artifact_kubernetes_name(environment, bolt, artifact, volume.name)
                        },
                    }
                )

            else:
                # Add an ephemeral volume claim to the PodTemplate
                volumes.append(
                    {
                        "name": volume.name,
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
    for provided_resource in artifact.provides:
        metadata["labels"][METADATA_LABEL_RESOURCE] = provided_resource.name

        deployment_metadata = metadata.copy()
        deployment_metadata["annotations"] = {
            METADATA_ANNOTATION_RESOURCE: provided_resource.model_dump_json(exclude_unset=True)
        }
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
    project: Project,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    ports = []
    for service in artifact.execution.services:
        if http_port := (service.grpc or service.http):
            ports.append({"port": http_port, "name": service.name, "targetPort": service.name})
        elif service.tcp:
            # TODO: Need to create a different kind of service for TCP traffic?
            ports.append({"port": service.tcp, "name": service.name, "targetPort": service.name})

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
    volume: VolumeRequirement,
    access_modes: list[str],
    execution_volume_parameters: VolumeExecutionParameters | None,
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
    project: Project,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    resources = []
    for volume in artifact.execution.volumes:
        if volume.persistent is False:
            continue

        execution_volume_parameters = artifact_execution_parameters.volumes.get(volume.name)

        resources.append(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": _get_artifact_metadata(environment, bolt, artifact, volume.name),
                "spec": _get_volume_claim(volume, ["ReadWriteMany"], execution_volume_parameters),
            }
        )

    return resources


def generate_ingresses(
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    project: Project,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    # external_service_parameters = {artifact_execution_parameters.external_services
    hosts = {}
    for service in artifact.execution.services:
        http_service_port = service.http or service.grpc
        if not http_service_port:
            # Only do HTTP service right now
            continue

        service_execution_parameters = artifact_execution_parameters.external_services.get(service.name)
        if service_execution_parameters is None:
            continue

        path = {
            "path": service_execution_parameters.path or "/",
            "pathType": "Prefix",
            "backend": {
                "service": {
                    "name": service.name,
                    "port": {"number": service_execution_parameters.port or http_service_port},
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
    def get_shared_resource_name(
        self, environment: Environment, artifact_reference: ArtifactReference, resource: Resource
    ) -> str:
        return f"{artifact_reference.project}-{resource.name}-shared"

    def get_artifact_resource_names(
        self, environment: Environment, bolt: Bolt, artifact: ExecutableArtifact
    ) -> list[str]:
        return []

    def generate_kubernetes_resources(
        self,
        adapter: KubernetesExecutionEnvironmentAdapter,
        environment: Environment,
        project: Project,
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
    def get_namespace_name(self, secret) -> str:
        return ""


class ExternalSecretsAdapter(BaseKubernetesSettingsAdapter):
    pass
