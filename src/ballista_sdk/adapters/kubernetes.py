from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, NotRequired, Protocol, TypedDict, cast

import yaml
from kubernetes import client, config, utils

from ballista_sdk.adapters.exceptions import UnknownResourceRequirement
from ballista_sdk.adapters.settings import BoundSetting, Config, Secret, Setting, SettingValue
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
    ResourceProviderReference,
    ResourceReference,
    ResourceSetting,
    ServiceRequirement,
    SettingDataType,
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
    spec: NotRequired[dict[str, Any]]


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
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
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
            bolt=bolt,
            artifact=artifact,
            artifact_execution_parameters=execution_parameters.params_for_artifact(
                environment=environment, bolt=bolt, artifact=artifact
            ),
        )
        for artifact in artifacts
    }

    # Bolt resources
    k8s_resources: list[KubernetesResource] = []
    return k8s_resources, artifact_resources


def _generate_probe(probe: HealthcheckProbe, services: dict[str, ServiceRequirement]) -> dict[str, dict] | None:
    if probe.exec:
        commands = ["sh", "-c"] if probe.exec.shell else []

        return {"exec": {"command": commands}}

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
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    k8s_resources: list[KubernetesResource] = []

    for generator in adapter._generators:
        k8s_resources += generator(
            adapter=adapter,
            environment=environment,
            bolt=bolt,
            artifact=artifact,
            artifact_execution_parameters=artifact_execution_parameters,
        )

    return k8s_resources


def _generate_yaml_files(k8s_resources: Sequence[KubernetesResource]) -> dict[str, str]:
    return {kind.lower() + ".yaml": str(yaml.dump(data)) for kind, data in k8s_resources}


# Settings
class BaseKubernetesSettingsAdapter[SettingType: Setting]:
    def _get_artifact_settings_refname(self, artifact_reference: ArtifactReference) -> str:
        return f"{artifact_reference.project_name}.{artifact_reference.artifact_name}"

    def _get_resource_settings_refname(self, resource_reference: ResourceReference) -> str:
        return f"{resource_reference.project_name}.resources.{resource_reference.resource_name}"

    def _add_setting_reference(
        self, container_spec: dict, ref_name: str, sensitive: bool, required: bool, prefix: str | None
    ):
        ref_type = "secretRef" if sensitive else "configMapRef"
        reference = {"name": ref_name, "optional": not required}

        env: dict[str, dict | str] = {ref_type: reference}
        if prefix:
            env["prefix"] = prefix + "_"

        if "envFrom" not in container_spec:
            container_spec["envFrom"] = [env]
        elif env not in container_spec["envFrom"]:
            container_spec["envFrom"].append(env)

    def add_artifact_setting(self, container_spec: dict, artifact_reference: ArtifactReference, setting: Setting):
        self._add_setting_reference(
            container_spec,
            self._get_artifact_settings_refname(artifact_reference),
            setting.sensitive,
            setting.sensitive,
            None,
        )

    def add_resource_setting(
        self,
        container_spec: dict,
        artifact_reference: ArtifactReference,
        resource_reference: ResourceReference,
        resource_setting: ResourceSetting,
        prefix: str,
        instance: list[str],
    ):
        if resource_setting.shared:
            # Shared setting means we reference it into the artifact
            self._add_setting_reference(
                container_spec,
                self._get_resource_settings_refname(resource_reference),
                resource_setting.sensitive,
                True,
                prefix,
            )

        else:
            # Unique setting is already inside the normal artifact settings
            self.add_artifact_setting(container_spec, artifact_reference, resource_setting)

    def delete(self, environment: Environment, bound_setting: BoundSetting):
        raise Exception()

    def exists(self, environment: Environment, bound_setting: BoundSetting) -> bool:
        raise Exception()

    def generate_kubernetes_resources(
        self,
        adapter: KubernetesInfrastructureAdapter,
        environment: Environment,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        artifact_execution_parameters: ArtifactExecutionParameters,
    ) -> list[KubernetesResource]:
        return []

    def read(self, environment: Environment, bound_setting: BoundSetting) -> SettingValue:
        raise Exception()

    def write(self, environment: Environment, bound_setting: BoundSetting, value: SettingValue):
        raise Exception()


@dataclass
class KubernetesConfigsAdapter(BaseKubernetesSettingsAdapter[Config]):
    @property
    def verify_before_deploy(self) -> Literal[True]:
        return True

    def _generate_configmap_data(self, configs: list[tuple[str, SettingDataType, SettingValue]]):
        binary_data: dict[str, bytes] = {}
        data: dict[str, str] = {}
        for name, data_type, value in configs:
            if data_type == SettingDataType.BYTES:
                binary_data[name] = base64.b64encode(cast(bytes, value))
            else:
                data[name] = str(value)

        return ({"binaryData": binary_data} if binary_data else {}) | ({"data": data} if data else {})

    def generate_kubernetes_resources(
        self,
        adapter: KubernetesInfrastructureAdapter,
        environment: Environment,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        artifact_execution_parameters: ArtifactExecutionParameters,
    ) -> list[KubernetesResource]:
        return []


@dataclass
class KubernetesSecretsAdapter(BaseKubernetesSettingsAdapter[Secret]):
    @property
    def verify_before_deploy(self) -> Literal[True]:
        return True

    def _generate_secret_data(self, secrets: list[tuple[str, SettingDataType, SettingValue]]):
        return {
            "data": {
                name: base64.b64encode(
                    cast(bytes, value) if data_type == SettingDataType.BYTES else str(value).encode()
                )
                for name, data_type, value in secrets
            },
            "type": "Opaque",
        }


@dataclass
class ExternalSecretsAdapter(BaseKubernetesSettingsAdapter):
    @property
    def verify_before_deploy(self) -> Literal[False]:
        return False


@dataclass
class KubernetesInfrastructureAdapter:
    _generators: ClassVar[list[KubernetesResourcesGenerator]] = []

    _bolts: list[Bolt] = field(default_factory=list)
    # TODO: These shouldn't be here; they are going to be Environment dependent!
    configs_adapter: KubernetesConfigsAdapter = field(default_factory=KubernetesConfigsAdapter)
    secrets_adapter: KubernetesSecretsAdapter = field(default_factory=KubernetesSecretsAdapter)

    @classmethod
    def add_generator(cls: type[KubernetesInfrastructureAdapter], method: KubernetesResourcesGenerator):
        """Add KubernetesResourceGenerator to be included when generating."""
        cls._generators.append(method)
        return method

    @property
    def name(self) -> Literal["kubernetes"]:
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

    def list_projects(self, environments: Sequence[Environment] | None = None) -> list[Project]:
        return []

    def list_project_bolts(self, project: Project) -> list[Bolt]:
        return []

    def list_resources(self, environment: Environment) -> list[ResourceProviderReference]:
        """List available Resources and the providing ArtifactIDReference in the specified Environment."""
        if self._bolts:
            executable_artifacts = []
            for bolt in self._bolts:
                executable_artifacts.extend(
                    [
                        ResourceProviderReference(resource, bolt.project, artifact.name, bolt.version)
                        for artifact in bolt.executable_artifacts
                        for resource in artifact.provides
                    ]
                )

            return executable_artifacts

        api_client = self._get_kubernetes_client(environment)

        # 1:1 ExecutableArtifact:Deployment
        resources = []
        api = client.AppsV1Api(api_client)
        for deployment in api.list_deployment_for_all_namespaces(
            label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT}={environment.name},{METADATA_LABEL_RESOURCE}"
        ).items:
            metadata = cast(client.models.V1ObjectMeta, deployment.metadata)
            labels = cast(dict[str, str], metadata.labels)
            resource_json = metadata.annotations.get(METADATA_ANNOTATION_RESOURCE)
            if resource_json is not None:
                try:
                    resource = Resource.model_validate_json(resource_json)
                    ref = ResourceProviderReference(
                        resource,
                        labels["app.kubernetes.io/part-of"],
                        labels["app.kubernetes.io/name"],
                        labels["app.kubernetes.io/version"],
                    )
                    resources.append(ref)

                except Exception as e:
                    print(e)

        return resources

    def resolve_resource_requirement(
        self, resource_requirement: ProjectResourceRequirement, environment: Environment
    ) -> ResourceProviderReference:
        requirement_project_name = resource_requirement.which()
        requirement_resource_name = resource_requirement.resource_name

        if requirement_project_name is None or requirement_resource_name is None:
            raise UnknownResourceRequirement("PROJECT", "RESOURCE")

        # TODO: Do a smarter lookup via K8s API
        for resource_with_provider_artifact in self.list_resources(environment):
            if (
                resource_with_provider_artifact.project_name == requirement_project_name
                and resource_with_provider_artifact.resource.name == requirement_resource_name
            ):
                return resource_with_provider_artifact

        raise UnknownResourceRequirement(requirement_project_name, requirement_resource_name)

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
        adapter: KubernetesInfrastructureAdapter,
        environment: Environment,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        artifact_execution_parameters: ArtifactExecutionParameters,
    ) -> Sequence[KubernetesResource]: ...


@KubernetesInfrastructureAdapter.add_generator
def _generate_config_kubernetes_resources(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    return []


@KubernetesInfrastructureAdapter.add_generator
def _generate_secrets_kubernetes_resources(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    return []


@KubernetesInfrastructureAdapter.add_generator
def _generate_deployment(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    execution = artifact.execution
    artifact_reference = ArtifactReference(bolt.project, artifact.name, bolt.version)

    metadata = _get_artifact_metadata(environment, bolt, artifact)

    env: list[dict] = []
    env_from: list[dict] = []

    # TODO: This will need a better abstraction so it can use explicit Docker registries.
    artifact.type.docker_image
    if (image := artifact.type.docker_image.image) is None:
        image = f"{bolt.project}_{artifact.name}:{bolt.version}"

    # Create barebones PodSpec
    container: dict[str, Any] = {"name": artifact.name, "image": image}
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

    # Artifact configs
    configs_adapter = adapter.configs_adapter
    [configs_adapter.add_artifact_setting(container, artifact_reference, c) for c in execution.configs]

    # Artifact secrets
    secrets_adapter = adapter.secrets_adapter
    [secrets_adapter.add_artifact_setting(container, artifact_reference, s) for s in execution.secrets]

    # Resources
    for resource_requirement in execution.resources:
        resource, resource_project, _, _ = adapter.resolve_resource_requirement(resource_requirement, environment)
        resource_reference = ResourceReference(resource_project, resource.name)
        requirement_prefix = resource_requirement.prefix or resource.prefix
        requirement_instance = [getattr(resource_requirement.requirement, f) for f in resource.instance_id_fields]

        [
            configs_adapter.add_resource_setting(
                container, artifact_reference, resource_reference, c, requirement_prefix, requirement_instance
            )
            for c in resource.configs
        ]
        [
            secrets_adapter.add_resource_setting(
                container, artifact_reference, resource_reference, s, requirement_prefix, requirement_instance
            )
            for s in resource.secrets
        ]

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
    volumes: list[dict] = []
    volume_mounts: list[dict] = []
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


@KubernetesInfrastructureAdapter.add_generator
def _generate_services(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
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
    volume_claim: dict[str, Any] = {
        "accessModes": access_modes,
        "resources": {"requests": {"storage": f"{volume.capacity}G"}},
    }

    # Claim resources
    if execution_volume_parameters:
        if execution_volume_parameters.max_capacity:
            volume_claim["resources"]["limits"] = {"storage": f"{execution_volume_parameters.max_capacity}G"}

        if execution_volume_parameters.type:
            volume_claim["storageClassName"] = execution_volume_parameters.type

    return volume_claim


@KubernetesInfrastructureAdapter.add_generator
def _generate_persistent_volume_claims(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    resources: list[KubernetesResource] = []
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


@KubernetesInfrastructureAdapter.add_generator
def _generate_ingresses(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    hosts: dict[str, dict] = {}
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
        if host:
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
