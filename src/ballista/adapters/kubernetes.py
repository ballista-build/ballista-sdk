from __future__ import annotations

from collections.abc import Collection
from typing import Any, TypedDict

import yaml
from kubernetes import client, config, utils

from ballista.adapters.types import EnvironmentExecutionAdapter, fake_artifact_types
from ballista.types import (
    ArtifactExecutionExternalServiceParameters,
    ArtifactExecutionParameters,
    ArtifactExecutionProbe,
    ArtifactExecutionResourceDependency,
    ArtifactExecutionService,
    ArtifactType,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutableArtifactReference,
    ExecutionParameters,
    ResourceWithArtifactProvider,
)


class KubernetesResource(TypedDict):
    apiVersion: str
    kind: str
    metadata: dict[str, Any]
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
METADATA_LABEL_ENVIRONMENT = "ballista.build/environment"


def _get_metadata_labels(
    environment: Environment, bolt: Bolt | None = None, artifact: ExecutableArtifact | None = None
) -> dict[str, str]:
    labels = {
        "app.kubernetes.io/managed-by": METADATA_MANAGED_BY,
        METADATA_LABEL_ENVIRONMENT: environment.id,
    }

    if bolt is None:
        return labels

    labels.update(
        {
            "app.kubernetes.io/part-of": bolt.project_id,
            "app.kubernetes.io/version": bolt.version,
        }
    )

    if artifact is None:
        return labels

    labels.update(
        {"app.kubernetes.io/instance": f"{artifact.id}-{bolt.version}", "app.kubernetes.io/name": artifact.id}
    )

    return labels


def _get_bolt_kubernetes_namespace(bolt: Bolt, environment: Environment) -> str:
    # TODO: This will need to be changed and allow customization
    if PER_PROJECT_NAMESPACES:
        return f"{bolt.project_id}-{environment.id}"
    else:
        return environment.id


def _get_artifact_kubernetes_name(name: str, bolt: Bolt, environment: Environment) -> str:
    # TODO: This will need to be changed and allow customization
    if PER_PROJECT_NAMESPACES:
        return name
    else:
        return f"{bolt.project_id}-{name}"


def _generate_bolt_resources(
    bolt: Bolt,
    artifacts: Collection[ExecutableArtifact],
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    execution_parameters: ExecutionParameters,
) -> tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]]:
    """Generate Kubernetes resource definitions shared across multiple artifacts and the individual artifacts."""
    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate resources.")

    artifact_resources = {
        artifact.id: _generate_artifact_resources(
            bolt=bolt,
            artifact=artifact,
            adapter=adapter,
            environment=environment,
            artifact_execution_parameters=execution_parameters.params_for_artifact(
                environment=environment, project_id=bolt.project_id, artifact=artifact
            ),
        )
        for artifact in artifacts
    }

    # Bolt resources
    k8s_resources: list[KubernetesResource] = []
    return k8s_resources, artifact_resources


def _generate_probe(probe: ArtifactExecutionProbe, services: dict[str, ArtifactExecutionService]) -> dict | None:
    if probe.exec:
        return {"exec": {"command": probe.exec.commands}}

    # Get port common in grpc, http, and port probes
    common = probe.grpc or probe.http or probe.tcp
    if common is None:
        return None

    service = services.get(common.service_id) if common.service_id else None
    port = common.port

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
    bolt: Bolt,
    artifact: ExecutableArtifact,
    adapter: KubernetesExecutionEnvironmentAdapter,
    environment: Environment,
    artifact_execution_parameters: ArtifactExecutionParameters,
) -> list[KubernetesResource]:
    execution = artifact.execution

    k8s_resources: list[KubernetesResource] = []

    artifact_name = artifact.id
    """Local context name of artifact."""
    artifact_ref_name = _get_artifact_kubernetes_name(artifact_name, bolt, environment)
    """Reference name of artifact."""

    metadata = {
        "labels": _get_metadata_labels(environment=environment, bolt=bolt, artifact=artifact),
        "name": artifact_ref_name,
        "namespace": _get_bolt_kubernetes_namespace(bolt, environment),
    }

    env = []
    env_from = []

    # TODO: This will need a better abstraction so it can use explicit Docker registries.
    if (image := artifact.type.config.get("image")) is None:
        image = f"{bolt.project_id}_{artifact.id}:{bolt.version}"

    container = {"name": artifact_name, "image": image}

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

    has_service_configs = bool(execution.configs)
    has_service_secrets = bool(execution.secrets)

    # Platform Resources
    if resource_dependencies := execution.resources:
        for dependency in resource_dependencies:
            resource, _ = adapter.resolve_resource_dependency(dependency, environment)

            prefix = (dependency.config.get("prefix") or resource.prefix) + "_"
            ref_name = f"{resource.id}-shared"

            has_shared_configs = False
            for config in resource.configs:
                if config.shared:
                    has_shared_configs = True
                else:
                    has_service_configs = True

            if has_shared_configs:
                env_from.append(
                    {
                        "prefix": prefix,
                        "configMapRef": {"name": ref_name, "optional": False},
                    }
                )

            has_shared_secrets = False
            for secret in resource.secrets:
                if secret.shared:
                    has_shared_secrets = True
                else:
                    has_service_secrets = True

            if has_shared_secrets:
                env_from.append(
                    {
                        "prefix": prefix,
                        "secretRef": {"name": ref_name, "optional": False},
                    }
                )

    # Secrets
    if has_service_secrets:
        # Service secrets are either first or second item
        env_from.insert(0, {"secretRef": {"name": artifact_ref_name, "optional": False}})

    # Configs
    if has_service_configs:
        # Service configs are always first item and marked as optional
        env_from.insert(0, {"configMapRef": {"name": artifact_ref_name, "optional": True}})

    # Services
    services_added = {}
    ports = []
    external_services: list[tuple[ArtifactExecutionService, ArtifactExecutionExternalServiceParameters]] = []
    for service in execution.services:
        port_service = service.grpc or service.http or service.tcp
        if port_service is None:
            # TODO: WTF is it, then? Probably need a better abstraction haha
            continue

        services_added[service.id] = service

        key = f"{service.id.upper()}_SERVICE"
        host = "localhost"
        path = "/"
        ports.append({"containerPort": port_service.port, "name": service.id})
        env.append({"name": f"{key}_PORT", "value": str(port_service.port)})

        external_service_parameters = artifact_execution_parameters.external_services.get(service.id)
        if external_service_parameters and external_service_parameters.host:
            host = external_service_parameters.host
            if external_service_parameters.path:
                path = external_service_parameters.path

            external_services.append((service, external_service_parameters))

        env.append({"name": f"{key}_HOST", "value": host})
        if service.http:
            env.append({"name": f"{key}_PATH", "value": path})

    if ports:
        container["ports"] = ports

    # Healthchecks; processed after Services since they can refer to them
    if healthchecks := execution.healthchecks:
        if (ready := healthchecks.ready) and (probe := _generate_probe(ready, services_added)):
            container["readinessProbe"] = probe

        if (alive := healthchecks.alive) and (probe := _generate_probe(alive, services_added)):
            container["livenessProbe"] = probe

        if (started := healthchecks.started) and (probe := _generate_probe(started, services_added)):
            container["startupProbe"] = probe

    if env:
        container["env"] = env
    if env_from:
        container["envFrom"] = env_from

    # TODO
    # securityContext

    # Generate Kubernetes resource definitions
    pod_spec = {"containers": [container]}

    pod_template = {
        "metadata": metadata,
        "spec": pod_spec,
    }

    # Deployment
    k8s_resources.append(
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": metadata,
            "spec": {
                "selector": {  # LabelSelector
                    "matchLabels": metadata["labels"]
                },
                "strategy": {
                    "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                    "type": "RollingUpdate",
                },
                "template": pod_template,  # PodTemplate
            },
        },
    )

    # Services
    if services_added:
        for service in services_added.values():
            ports = []
            resource: KubernetesResource = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "labels": metadata["labels"],
                    "name": f"{artifact_ref_name}-{service.id}",
                    "namespace": metadata["namespace"],
                },
                "spec": {"selector": metadata["labels"], "ports": ports},
            }

            if http_service := (service.grpc or service.http):
                ports.append({"port": http_service.port, "name": service.id, "targetPort": service.id})

            elif service.tcp:
                # TODO: Need to create a different kind of service for TCP traffic
                pass

            k8s_resources.append(resource)

    # Volumes
    if execution.volumes:
        volumes = []
        volume_mounts = []
        for volume in execution.volumes:
            volume_claim_metadata = {
                "labels": metadata["labels"],
                "name": f"{artifact_ref_name}-{volume.id}",
                "namespace": metadata["namespace"],
            }

            # Mount Path
            volume_mount = {"mountPath": volume.path, "name": volume.id}
            volume_mounts.append(volume_mount)

            volume_claim = {"resources": {"requests": {"storage": f"{volume.capacity}G"}}}

            # Claim resources
            if execution_volume_parameters := artifact_execution_parameters.volumes.get(volume.id):
                if execution_volume_parameters.max_capacity:
                    volume_claim["resources"]["limits"] = {"storage": f"{execution_volume_parameters.max_capacity}G"}

                if execution_volume_parameters.path:
                    # Set a subPath in the volume for this specific mount
                    volume_mount["subPath"] = f"{execution_volume_parameters.path}/{volume.id}"
                if execution_volume_parameters.type:
                    volume_claim["storageClassName"] = execution_volume_parameters.type

            if volume.persistent:
                volumes.append(
                    {"name": volume.id, "persistentVolumeClaim": {"claimName": volume_claim_metadata["name"]}}
                )

                # Create a PersistentVolumeClaim; multiple pods can access the claim.
                volume_claim.update({"accessModes": ["ReadWriteMany"]})

                k8s_resources.append(
                    {
                        "apiVersion": "v1",
                        "kind": "PersistentVolumeClaim",
                        "metadata": volume_claim_metadata,
                        "spec": volume_claim,
                    }
                )

            else:
                # Add an ephemeral volume claim to the PodTemplate
                volume_claim.update({"accessModes": ["ReadWriteOnce"]})

                volumes.append(
                    {
                        "name": volume.id,
                        "ephemeral": {
                            "volumeClaimTemplate": {
                                "metadata": {"labels": metadata["labels"]},
                                "spec": volume_claim,
                            }
                        },
                    }
                )

        container["volumeMounts"] = volume_mounts
        pod_spec["volumes"] = volumes

    # TODO: Generate GatewayRoutes instead
    # Ingress
    if external_services:
        hosts = {}
        for service, service_execution_parameters in external_services:
            port_service = service.grpc or service.http
            if port_service is None or service.tcp:
                # Can't expose TCP this way
                continue

            path = {
                "path": service_execution_parameters.path or "/",
                "pathType": "Prefix",
                "backend": {
                    "service": {
                        "name": service.id,
                        "port": {"number": service_execution_parameters.port or port_service.port},
                    }
                },
            }

            host = service_execution_parameters.host
            if host in hosts:
                hosts[host]["http"]["paths"].append(path)
            else:
                hosts[host] = {"host": host, "http": {"paths": [path]}}

        if hosts:
            k8s_resources.append(
                {
                    "apiVersion": "networking.k8s.io/v1",
                    "kind": "Ingress",
                    "metadata": metadata,
                    "spec": {"rules": list(hosts.values())},
                },
            )

    return k8s_resources


def _generate_yaml_files(k8s_resources: Collection[KubernetesResource]) -> dict[str, str]:
    return {kind.lower() + ".yaml": yaml.dump(data) for kind, data in k8s_resources}


class KubernetesExecutionEnvironmentAdapter(EnvironmentExecutionAdapter):
    def __init__(self, executable_artifact_references: list[ExecutableArtifactReference] = []):
        self._executable_artifact_references = executable_artifact_references

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
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

        namespace = _get_bolt_kubernetes_namespace(bolt, environment)

        if True:
            # Create namespace
            api = client.CoreV1Api(api_client)
            try:
                existing_namespace = api.read_namespace(namespace)

                # TODO: Make sure the namespace is labelled correctly.
            except client.ApiException:
                api.create_namespace(
                    client.V1Namespace(
                        metadata=client.V1ObjectMeta(
                            labels=_get_metadata_labels(environment=environment),
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
        return fake_artifact_types()

    def list_environments(self) -> list[Environment]:
        environments = []
        # Use all kube contexts to assemble a list of Ballista Environments
        contexts, _ = config.list_kube_config_contexts()

        for context in contexts:
            api_client = config.new_client_from_config(context=context["name"])

            # TODO: We don't have an Environment type, so use Namespace for now.
            corev1_api = client.CoreV1Api(api_client=api_client)
            ballista_namespaces = corev1_api.list_namespace(
                label_selector=f"app.kubernetes.io/managed-by={METADATA_MANAGED_BY},{METADATA_LABEL_ENVIRONMENT}"
            )

            environments.extend(
                [Environment(id=n.metadata.name, name=n.metadata.name) for n in ballista_namespaces.items]
            )

        return environments

    def list_executable_artifacts(self, environment: Environment) -> list[ExecutableArtifactReference]:
        # TODO: DO THIS FOR REAL. Extract this from annotations on something running? CRD?
        return []

    def list_resources(self, environment: Environment) -> list[ResourceWithArtifactProvider]:
        """List available Resources with a providing ArtifactReference in the specified Environment."""

        return [(ref[0].resource, ref) for ref in self._executable_artifact_references if ref[0].resource]

    def resolve_resource_dependency(
        self, resource_dependency: ArtifactExecutionResourceDependency, environment: Environment
    ) -> ResourceWithArtifactProvider:
        for item in self.list_resources(environment):
            if item[0].id == resource_dependency.resource_id:
                return item

        raise ValueError(f'Unknown resource "{resource_dependency.resource_id}"')

    def teardown(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        pass

    def _get_kubernetes_client(self, environment: Environment) -> client.ApiClient:
        # TODO: Get context where environment is
        context = None

        return config.new_client_from_config(context=context)
