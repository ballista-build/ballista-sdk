from collections.abc import Collection
from typing import Any, TypedDict

import yaml
from kubernetes import client, config, utils

from ballista.adapters.types import EnvironmentExecutionAdapter
from ballista.types import (
    ArtifactExecutionProbe,
    ArtifactExecutionService,
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentArtifactExecutionParameters,
    ExecutableArtifact,
    Resource,
)


class KubernetesResource(TypedDict):
    apiVersion: str
    kind: str
    metadata: dict[str, Any]
    spec: dict[str, Any]


def _generate_bolt_resources(
    bolt: Bolt,
    artifacts: Collection[ExecutableArtifact],
    environment: Environment,
    execution_parameters: EnvironmentArtifactExecutionParameters,
) -> tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]]:
    """Generate Kubernetes resource definitions shared across multiple artifacts and the individual artifacts."""
    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate resources.")

    artifact_resources = {
        artifact.id: _generate_artifact_resources(
            bolt=bolt, artifact=artifact, execution_parameters=execution_parameters, environment=environment
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
    common = probe.grpc or probe.http or probe.port
    if common is None:
        return None

    service = services.get(common.service_id) if common.service_id else None
    port = common.port

    if probe.grpc:
        # GRPC cannot use a named port
        return {"grpc": {"port": service.port if service else port}}

    if probe.http:
        return {"httpGet": {"path": probe.http.path or "/healthz", "port": service.id if service else port}}

    if probe.port:
        return {"tcpSocket": {"port": service.id if service else port}}


def _generate_artifact_resources(
    bolt: Bolt,
    artifact: ExecutableArtifact,
    environment: Environment,
    execution_parameters: EnvironmentArtifactExecutionParameters,
) -> list[KubernetesResource]:
    k8s_resources: list[KubernetesResource] = []

    # Common metadata
    service_name = artifact.id
    service_env_name = artifact.id
    metadata = {
        "labels": {
            "app.kubernetes.io/managed-by": "Ballista",
            "app.kubernetes.io/name": service_name,
            "app.kubernetes.io/part-of": bolt.project_id,
            "app.kubernetes.io/version": bolt.version,
        },
        "name": service_name,
        "namespace": f"{bolt.project_id}-{environment.id}",
    }

    env = []
    env_from = []

    container = {
        "name": service_name,
        "image": artifact.type.config.get("image", f"{artifact.id}:{bolt.version}"),
    }

    # Configs
    if artifact.execution.configs:
        env_from.append({"configMapRef": {"name": service_env_name, "optional": True}})

    # Execution Parameters Resources
    if execution_resources := execution_parameters.resources:
        pod_resources = {"requests": {}, "limits": {}}
        if execution_resources.min_cpu:
            pod_resources["requests"]["cpu"] = f"{execution_resources.min_cpu}G"
        if execution_resources.min_memory:
            pod_resources["requests"]["memory"] = f"{execution_resources.min_memory}G"
        if execution_resources.max_cpu:
            pod_resources["limits"]["cpu"] = f"{execution_resources.max_cpu}G"
        if execution_resources.max_memory:
            pod_resources["limits"]["memory"] = f"{execution_resources.max_memory}G"

        container["resources"] = pod_resources

    has_secrets = bool(artifact.execution.secrets)

    # TODO: Platform Resources

    # Secrets
    if has_secrets:
        env_from.append({"secretRef": {"name": service_env_name, "optional": False}})

    # Services
    services = {}
    if execution_services := artifact.execution.services:
        ports = []
        for service in execution_services:
            services[service.id] = service

            key = f"{service.id.upper()}_SERVICE"

            ports.append({"containerPort": service.port, "name": service.id})

            env.append({"name": f"{key}_PORT", "value": str(service.port)})

        container["ports"] = ports

    # Healthchecks; processed after Services since they can refer to them
    if healthchecks := artifact.execution.healthchecks:
        if (ready := healthchecks.ready) and (probe := _generate_probe(ready, services)):
            container["readinessProbe"] = probe

        if (alive := healthchecks.alive) and (probe := _generate_probe(alive, services)):
            container["livenessProbe"] = probe

        if (started := healthchecks.started) and (probe := _generate_probe(started, services)):
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
                    "matchLabels": {"app.kubernetes.io/name": service_name}
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
    if services:
        k8s_resources.extend(
            [
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "labels": metadata["labels"],
                        "name": f"{service_name}-{s.id}",
                        "namespace": metadata["namespace"],
                    },
                    "spec": {
                        "selector": {"app.kubernetes.io/name": service_name},
                        "ports": [{"port": s.port, "name": s.id, "targetPort": s.id}],
                    },
                }
                for s in services.values()
            ]
        )

    # Volumes
    if artifact.execution.volumes:
        volumes = []
        volume_mounts = []
        for volume in artifact.execution.volumes:
            volume_claim_metadata = {
                "labels": metadata["labels"],
                "name": f"{service_name}-{volume.id}",
                "namespace": metadata["namespace"],
            }

            # Mount Path
            volume_mount = {"mountPath": volume.path, "name": volume.id}
            volume_mounts.append(volume_mount)

            volume_claim = {"resources": {"requests": {"storage": f"{volume.capacity}Gi"}}}

            # Claim resources
            if execution_volume := execution_parameters.volumes.get(volume.id):
                if execution_volume.max_capacity:
                    volume_claim["resources"]["limits"] = {"storage": f"{execution_volume.max_capacity}Gi"}

                if execution_volume.path:
                    # Set a subPath in the volume for this specific mount
                    volume_mount["subPath"] = f"{execution_volume.path}/{volume.id}"
                if execution_volume.type:
                    volume_claim["storageClassName"] = execution_volume.type

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

    # Ingress
    external_services = []

    if external_services:
        k8s_resources.append(
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": metadata,
                "spec": {
                    "rules": [
                        {
                            "host": "host",
                            "http": {
                                "paths": [
                                    {
                                        "path": s["external_path"],
                                        "pathType": "Prefix",
                                        "backend": {
                                            "service": {"name": s["name"], "port": {"number": s["target_port"]}}
                                        },
                                    }
                                    for s in external_services
                                ]
                            },
                        }
                    ]
                },
            },
        )

    return k8s_resources


def _generate_yaml_files(k8s_resources: Collection[KubernetesResource]) -> dict[str, str]:
    return {kind.lower() + ".yaml": yaml.dump(data) for kind, data in k8s_resources}


class KubernetesExecutionEnvironmentAdapter(EnvironmentExecutionAdapter):
    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: Environment,
        execution_parameters: EnvironmentArtifactExecutionParameters,
    ):
        bolt_resources, all_artifact_resources = _generate_bolt_resources(
            bolt=bolt, artifacts=artifacts, environment=environment, execution_parameters=execution_parameters
        )

        # TODO: This needs expanding to not rely on the local kubeconf
        config.load_kube_config()
        k8s_client = client.ApiClient()

        namespace = f"{bolt.project_id}-{environment.id}"

        if True:
            # Create namespace
            api = client.CoreV1Api()
            try:
                api.read_namespace(namespace)
            except client.ApiException:
                api.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))

        [utils.create_from_dict(k8s_client, resource, apply=True, namespace=namespace) for resource in bolt_resources]

        for artifact_id, artifact_resources in all_artifact_resources.items():
            [
                utils.create_from_dict(k8s_client, resource, apply=True, namespace=namespace)
                for resource in artifact_resources
            ]

    def fulfill_platform_resource_dependency(self, environment: Environment, artifact: ExecutableArtifact):
        pass

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return []

    def list_platform_resources(self, environment: Environment) -> list[Resource]:
        return []

    def list_services(self, environment: Environment) -> list[ExecutableArtifact]:
        return []


class ArgoCDGitOpsKubernetesExecutionEnvironmentAdapter(KubernetesExecutionEnvironmentAdapter):
    pass
