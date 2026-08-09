"""Generation of Kubernetes resources."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, Sequence

from kubernetes.client.models import V1Deployment
from pydantic_core import to_json

from ballista_sdk.adapters.infrastructure import InfrastructureAdapter
from ballista_sdk.adapters.primitives import (
    ArtifactReference,
    ProvidedResourceReference,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceReference,
    ProvidedServiceWithArtifactReference,
)
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactExecution,
    ArtifactExecutionParameters,
    Bolt,
    ComputeExecutionParameters,
    Environment,
    ExecutionParameters,
    HealthcheckProbe,
    ProvidedService,
    ResourceSetting,
    Setting,
    VolumeExecutionParameters,
    VolumeRequirement,
)

from . import primitives
from .environments import KubernetesEnvironmentConfig
from .primitives import KubernetesMetadata, KubernetesMetadataLabels, KubernetesResource


def generate_environment_labels(environment) -> KubernetesMetadataLabels:
    """Generate metadata labels for a specific Environment."""

    return {
        primitives.METADATA_LABEL_APP_MANAGED_BY: primitives.METADATA_MANAGED_BY,
        primitives.METADATA_LABEL_ENVIRONMENT: environment.name,
        primitives.METADATA_LABEL_ENVIRONMENT_TIER: str(environment.tier),
    }


def generate_artifact_metadata_labels(
    environment: Environment, bolt: Bolt, artifact: Artifact
) -> KubernetesMetadataLabels:
    """Generate metadata labels for an Artifact in a specific Environment."""

    return generate_environment_labels(environment) | {
        primitives.METADATA_LABEL_APP_PART_OF: bolt.project,
        primitives.METADATA_LABEL_APP_NAME: artifact.name,
    }


def generate_versioned_artifact_metadata_labels(
    environment: Environment, bolt: Bolt, artifact: Artifact
) -> KubernetesMetadataLabels:
    """Generate metadata labels for an Artifact and version in a specific Environment."""

    return generate_artifact_metadata_labels(environment, bolt, artifact) | {
        primitives.METADATA_LABEL_APP_INSTANCE: f"{artifact.name}-{bolt.version}",
        primitives.METADATA_LABEL_APP_VERSION: bolt.version,
    }


def generate_artifact_selector_labels(
    environment: Environment, bolt: Bolt, artifact: Artifact
) -> KubernetesMetadataLabels:
    """Generate labels for selecting an Artifact in a specific Environment."""

    return {
        # Environment configuration may not guarantee namespace separation, so its name is included.
        primitives.METADATA_LABEL_ENVIRONMENT: environment.name,
        primitives.METADATA_LABEL_APP_PART_OF: bolt.project,
        primitives.METADATA_LABEL_APP_NAME: artifact.name,
    }


def generate_bolt_kubernetes_namespace(
    environment: Environment, environment_config: KubernetesEnvironmentConfig, bolt: Bolt
) -> str:
    """Generate the Kubernetes name for a Bolt's namespace when running in a specific Environment."""

    if environment_config.project_namespaces:
        # Projects are configured for their own unique namespace.

        return f"{bolt.project}-{environment.name}"
    else:
        # All projects are in the same Environment namespace.

        return environment.name


def generate_artifact_kubernetes_name(
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    artifact: Artifact,
    name: str | None = None,
) -> str:
    """Generate the Kubernetes name used for an Artifact or Artifact-specific item when running in a specific Environment."""

    if environment_config.project_namespaces:
        return artifact.name + (f"-{name}" if name else "")
    else:
        return f"{bolt.project}-{artifact.name}" + (f"-{name}" if name else "")


def generate_artifact_settings_refname(artifact_reference: ArtifactReference) -> str:
    return f"{artifact_reference.project_name}-{artifact_reference.artifact_name}"


def generate_resource_settings_refname(resource_reference: ProvidedResourceReference) -> str:
    return f"{resource_reference.project_name}-resources-{resource_reference.resource_name}"


def generate_artifact_metadata(
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    artifact: Artifact,
    name: str | None = None,
) -> KubernetesMetadata:
    """Generates the Kubernetes metadata for an Artifact in a specific Environment."""

    return {
        "labels": generate_versioned_artifact_metadata_labels(environment, bolt, artifact),
        "name": generate_artifact_kubernetes_name(environment, environment_config, bolt, artifact, name),
        "namespace": generate_bolt_kubernetes_namespace(environment, environment_config, bolt),
    }


class KubernetesResourcesGenerator(Protocol):
    """Generates a Sequence of KubernetesResources."""

    @staticmethod
    def __call__(
        adapter: KubernetesInfrastructureAdapter,
        environment: Environment,
        environment_config: KubernetesEnvironmentConfig,
        bolt: Bolt,
        execution_parameters: ExecutionParameters,
        artifact: Artifact,
        artifact_execution: ArtifactExecution,
        artifact_execution_parameters: ArtifactExecutionParameters,
        resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
        service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
    ) -> Sequence[KubernetesResource]: ...


# TODO: Break out into a "Default" adapter?
@dataclass
class KubernetesInfrastructureAdapter(InfrastructureAdapter):
    """Infrastructure Adapter for Kubernetes."""

    _generators: ClassVar[list[KubernetesResourcesGenerator]] = []

    @classmethod
    def add_generator(cls: type[KubernetesInfrastructureAdapter], method: KubernetesResourcesGenerator):
        """Add KubernetesResourceGenerator to be included when generating."""
        cls._generators.append(method)
        return method

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
        """Add an Artifact-specific setting into a PodSpec container."""

        self._add_setting_reference(
            container_spec,
            generate_artifact_settings_refname(artifact_reference),
            setting.sensitive,
            setting.sensitive,
            None,
        )

    def add_resource_setting(
        self,
        container_spec: dict,
        artifact_reference: ArtifactReference,
        resource_reference: ProvidedResourceReference,
        resource_setting: ResourceSetting,
        prefix: str,
        instance: list[str],
    ):
        """Add an Artifact and Resource-specific setting into a PodSpec container."""

        if resource_setting.shared:
            # Shared setting means we reference it into the artifact.
            self._add_setting_reference(
                container_spec,
                generate_resource_settings_refname(resource_reference),
                resource_setting.sensitive,
                True,
                prefix,
            )

        else:
            # Unique settings are added as normal Artifact settings.
            self.add_artifact_setting(container_spec, artifact_reference, resource_setting)

    def generate_bolt_resources(
        self,
        environment: Environment,
        environment_config: KubernetesEnvironmentConfig,
        bolt: Bolt,
        execution_parameters: ExecutionParameters,
        resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
        service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
    ) -> tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]]:
        """Generate Kubernetes resource definitions shared across multiple artifacts and the individual artifacts."""

        artifact_resources = {
            artifact.name: self.generate_artifact_resources(
                environment=environment,
                environment_config=environment_config,
                bolt=bolt,
                execution_parameters=execution_parameters,
                artifact=artifact,
                artifact_execution=artifact.execution,
                artifact_execution_parameters=execution_parameters.params_for_artifact(
                    environment=environment, bolt=bolt, artifact=artifact
                ),
                resource_providers=resource_providers,
                service_providers=service_providers,
            )
            for artifact in bolt.artifacts
            if artifact.execution
        }

        if len(artifact_resources) == 0:
            raise ValueError("No artifacts to generate resources.")

        # Bolt resources
        k8s_resources: list[KubernetesResource] = []
        return k8s_resources, artifact_resources

    def generate_artifact_resources(
        self,
        environment: Environment,
        environment_config: KubernetesEnvironmentConfig,
        bolt: Bolt,
        execution_parameters: ExecutionParameters,
        artifact: Artifact,
        artifact_execution: ArtifactExecution,
        artifact_execution_parameters: ArtifactExecutionParameters,
        resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
        service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
    ) -> list[KubernetesResource]:
        """Generate Kubernetes Resources for a specific ExecutableArtifact."""

        k8s_resources: list[KubernetesResource] = []

        for generator in self._generators:
            k8s_resources += generator(
                adapter=self,
                environment=environment,
                environment_config=environment_config,
                bolt=bolt,
                execution_parameters=execution_parameters,
                artifact=artifact,
                artifact_execution=artifact_execution,
                artifact_execution_parameters=artifact_execution_parameters,
                resource_providers=resource_providers,
                service_providers=service_providers,
            )

        return k8s_resources

    def _get_docker_image_name(
        self,
        environment: Environment,
        environment_config: KubernetesEnvironmentConfig,
        bolt: Bolt,
        artifact: Artifact,
    ) -> str:
        """Get the name of the image to use in a PodSpec Container definition."""

        if not artifact.type.docker_image:
            raise ValueError()

        if not (image := artifact.type.docker_image.image):
            # No specified image name, so generate one.
            image = f"{bolt.project}_{artifact.name}:{bolt.version}"

        if environment_config.force_image_registry or artifact.build is not None:
            # Use configured registry
            registry = environment_config.image_registry

            if registry is None:
                raise ValueError("Image requires configured registry, but no registry has been configured.")

            return f"{registry}/{image}"

        return image


@KubernetesInfrastructureAdapter.add_generator
def _generate_config_kubernetes_resources(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    execution_parameters: ExecutionParameters,
    artifact: Artifact,
    artifact_execution: ArtifactExecution,
    artifact_execution_parameters: ArtifactExecutionParameters,
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
) -> list[KubernetesResource]:
    return []


@KubernetesInfrastructureAdapter.add_generator
def _generate_secrets_kubernetes_resources(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    execution_parameters: ExecutionParameters,
    artifact: Artifact,
    artifact_execution: ArtifactExecution,
    artifact_execution_parameters: ArtifactExecutionParameters,
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
) -> list[KubernetesResource]:
    return []


def _generate_probe(probe: HealthcheckProbe, services: dict[str, ProvidedService]) -> dict[str, dict] | None:
    if probe.exec:
        commands = ["sh", "-c"] if probe.exec.shell else []

        return {"exec": {"command": commands + probe.exec.commands}}

    # Get port common in grpc, http, and port probes
    port_probe = probe.grpc or probe.http or probe.tcp
    if port_probe is None:
        return None

    port = port_probe.port
    service = None

    if port_probe.service:
        service = services.get(port_probe.service)
        if service is None:
            raise ValueError(f'Unknown referenced service "{port_probe.service}".')

    if probe.grpc:
        if service:
            if service.grpc is None:
                raise ValueError("GRPC probe must reference a GRPC service.")

            port = service.grpc

        if not port:
            raise ValueError("GPRC probe bad.")

        # GRPC must use the port number
        return {"grpc": {"port": port}}

    if probe.http:
        if service:
            if service.http is None:
                raise ValueError("HTTP probe must reference a HTTP service.")

            port = service.name

        if not port:
            raise ValueError("HTTP probe bad.")

        return {"httpGet": {"path": probe.http.path or "/healthz", "port": port}}

    if probe.tcp:
        if service:
            if service.tcp is None:
                raise ValueError("TCP probe must reference a TCP service.")

            port = service.name

        if not port:
            raise ValueError("TCP probe bad.")

        return {"tcpSocket": {"port": port}}


@KubernetesInfrastructureAdapter.add_generator
def _generate_deployment(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    execution_parameters: ExecutionParameters,
    artifact: Artifact,
    artifact_execution: ArtifactExecution,
    artifact_execution_parameters: ArtifactExecutionParameters,
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
) -> list[KubernetesResource]:
    artifact_reference = ArtifactReference(bolt.project, artifact.name, bolt.version)

    metadata = generate_artifact_metadata(environment, environment_config, bolt, artifact)

    env: OrderedDict[str, str] = OrderedDict()

    # Start PodSpec
    container: dict[str, Any] = {
        "name": artifact.name,
        "image": adapter._get_docker_image_name(environment, environment_config, bolt, artifact),
    }
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

    # Artifact configs and secrets
    [
        adapter.add_artifact_setting(container, artifact_reference, s)
        for s in artifact_execution.requires.configs + artifact_execution.requires.secrets
    ]

    # Required Resources
    for resource_requirement in artifact_execution.requires.resources:
        provided_resource_reference = ProvidedResourceReference(
            resource_requirement.project_name, resource_requirement.resource_name
        )
        provided_resource, provider_artifact_reference = resource_providers[provided_resource_reference]

        requirement_prefix = resource_requirement.prefix or provided_resource.prefix
        requirement_instance = [
            getattr(resource_requirement.resource_requirement, f) for f in provided_resource.instance_id_fields
        ]

        [
            adapter.add_resource_setting(
                container, artifact_reference, provided_resource_reference, s, requirement_prefix, requirement_instance
            )
            for s in provided_resource.configs + provided_resource.secrets
        ]

    # Required Services
    for service_requirement in artifact_execution.requires.services:
        provided_service_reference = ProvidedServiceReference(
            service_requirement.project_name, service_requirement.artifact_name, service_requirement.service_name
        )
        service, provider_artifact_reference = service_providers[provided_service_reference]

    # Provided Services
    services_added = {}
    for service in artifact_execution.provides.services:
        service_port = service.grpc or service.http or service.tcp
        if service_port is None:
            # TODO: WTF is it, then? Probably need a better abstraction haha
            continue

        services_added[service.name] = service

        key = service.name.upper().replace("-", "_") + "_SERVICE"
        host = "localhost"
        path = "/"
        secure = service.secure
        container["ports"] = container.get("ports", []) + [{"containerPort": service_port, "name": service.name}]
        env[f"{key}_PORT"] = str(service_port)

        external_service_parameters = artifact_execution_parameters.external_services.get(service.name)
        if external_service_parameters and external_service_parameters.host:
            host = external_service_parameters.host
            if external_service_parameters.path:
                path = external_service_parameters.path
            if external_service_parameters.secure:
                # Only set this if true; no downgrading to insecure.
                secure = external_service_parameters.secure

        env[f"{key}_HOST"] = host
        env[f"{key}_SECURE"] = "true" if secure else "false"
        if service.http:
            env[f"{key}_PATH"] = path

    # Healthchecks; processed after Provided Services since they can refer to them
    if healthchecks := artifact_execution.provides.healthchecks:
        if healthchecks.alive and (liveness_probe := _generate_probe(healthchecks.alive, services_added)):
            container["livenessProbe"] = liveness_probe
        if healthchecks.ready and (readiness_probe := _generate_probe(healthchecks.ready, services_added)):
            container["readinessProbe"] = readiness_probe
        if healthchecks.started and (startup_probe := _generate_probe(healthchecks.started, services_added)):
            container["startupProbe"] = startup_probe

    if env:
        container["env"] = [{"name": key, "value": value} for key, value in env.items()]

    # TODO
    # securityContext
    #
    # Volumes
    volumes: list[dict] = []
    volume_mounts: list[dict] = []
    for volume in artifact_execution.requires.volumes:
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
                        "claimName": generate_artifact_kubernetes_name(
                            environment, environment_config, bolt, artifact, volume.name
                        )
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
                            "spec": generate_volume_claim(volume, ["ReadWriteOnce"], execution_volume_parameters),
                        }
                    },
                }
            )

    if volume_mounts:
        container["volumeMounts"] = volume_mounts

    if volumes:
        pod_spec["volumes"] = volumes

    resource_names = [provided_resource.name for provided_resource in artifact_execution.provides.resources]
    if resource_names:
        metadata["labels"][primitives.METADATA_LABEL_RESOURCE] = to_json(resource_names).decode()

    pod_template = {
        "metadata": metadata,
        "spec": pod_spec,
    }

    deployment_metadata = metadata.copy()
    # Stuff Artifact into annotation
    deployment_metadata["annotations"] = {
        primitives.METADATA_ANNOTATION_ARTIFACT: artifact.model_dump_json(exclude_unset=True)
    }

    # Deployment
    return [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": deployment_metadata,
            "spec": {
                "selector": {"matchLabels": generate_artifact_selector_labels(environment, bolt, artifact)},
                "strategy": {
                    "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                    "type": "RollingUpdate",
                },
                "template": pod_template,
            },
        }
    ]


def extract_compute_execution_parameters_from_deployment(deployment: V1Deployment) -> ComputeExecutionParameters:
    return ComputeExecutionParameters()


@KubernetesInfrastructureAdapter.add_generator
def _generate_services(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    execution_parameters: ExecutionParameters,
    artifact: Artifact,
    artifact_execution: ArtifactExecution,
    artifact_execution_parameters: ArtifactExecutionParameters,
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
) -> list[KubernetesResource]:
    services: list[KubernetesResource] = []
    for provided_service in artifact_execution.provides.services:
        metadata = generate_artifact_metadata(environment, environment_config, bolt, artifact, provided_service.name)
        metadata["annotations"] = {
            primitives.METADATA_ANNOTATION_SERVICE: provided_service.model_dump_json(exclude_unset=True)
        }
        metadata["labels"][primitives.METADATA_LABEL_SERVICE] = provided_service.name

        services.append(
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": metadata,
                "spec": {
                    "selector": generate_artifact_selector_labels(environment, bolt, artifact),
                    "ports": [
                        {
                            "port": provided_service.grpc or provided_service.http or provided_service.tcp,
                            "name": provided_service.name,
                            "targetPort": provided_service.name,
                        }
                    ],
                },
            }
        )

    return services


def generate_volume_claim(
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
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    execution_parameters: ExecutionParameters,
    artifact: Artifact,
    artifact_execution: ArtifactExecution,
    artifact_execution_parameters: ArtifactExecutionParameters,
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
) -> list[KubernetesResource]:
    resources: list[KubernetesResource] = []
    for volume in artifact_execution.requires.volumes:
        if volume.persistent is False:
            continue

        execution_volume_parameters = artifact_execution_parameters.volumes.get(volume.name)

        resources.append(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": generate_artifact_metadata(environment, environment_config, bolt, artifact, volume.name),
                "spec": generate_volume_claim(volume, ["ReadWriteMany"], execution_volume_parameters),
            }
        )

    return resources


@KubernetesInfrastructureAdapter.add_generator
def _generate_ingresses(
    adapter: KubernetesInfrastructureAdapter,
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    bolt: Bolt,
    execution_parameters: ExecutionParameters,
    artifact: Artifact,
    artifact_execution: ArtifactExecution,
    artifact_execution_parameters: ArtifactExecutionParameters,
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
) -> list[KubernetesResource]:
    resources: list[KubernetesResource] = []

    for service in artifact_execution.provides.services:
        http_service_port = service.http
        if not http_service_port:
            # Only do HTTP service right now
            continue

        service_execution_parameters = artifact_execution_parameters.external_services.get(service.name)
        if service_execution_parameters is None:
            continue

        # Embed the
        metadata = generate_artifact_metadata(environment, environment_config, bolt, artifact, service.name)
        metadata["labels"][primitives.METADATA_LABEL_SERVICE] = service.name
        if top_externalized_service_parameters := execution_parameters.external_services.get(
            (environment.name, bolt.project, artifact.name, service.name)
        ):
            metadata["annotations"] = {
                primitives.METADATA_ANNOTATION_EXTERNALIZED_SERVICE: top_externalized_service_parameters.model_dump_json(
                    exclude_none=True
                )
            }
        resources.append(
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": metadata,
                "spec": {
                    "rules": [
                        {
                            "host": service_execution_parameters.host,
                            "http": {
                                "paths": [
                                    {
                                        "path": service_execution_parameters.path or "/",
                                        "pathType": "Prefix",
                                        "backend": {
                                            "service": {
                                                "name": generate_artifact_kubernetes_name(
                                                    environment, environment_config, bolt, artifact, service.name
                                                ),
                                                "port": {
                                                    "number": service_execution_parameters.port or http_service_port
                                                },
                                            }
                                        },
                                    }
                                ]
                            },
                        }
                    ]
                },
            }
        )

    return resources
