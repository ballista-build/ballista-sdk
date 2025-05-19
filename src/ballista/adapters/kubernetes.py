from collections.abc import Collection
from typing import Any

import yaml

from ballista.adapters.types import ExecutionEnvironmentAdapter
from ballista.types import ArtifactType, Bolt, ExecutableArtifact, ExecutionEnvironment, PlatformResource

KubernetesResource = tuple[str, dict[str, Any]]
"""A Kubernetes resource with an explicit Kind and data."""


def _generate_bolt_resources(
    bolt: Bolt, artifacts: Collection[ExecutableArtifact], environment: ExecutionEnvironment
) -> tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]]:
    """Generate Kubernetes resource definitions shared across multiple artifacts and the individual artifacts."""
    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate resources.")

    artifact_resources = {
        artifact.id: _generate_artifact_resources(bolt=bolt, artifact=artifact, environment=environment)
        for artifact in artifacts
    }

    # Bolt resources
    k8s_resources = []
    return k8s_resources, artifact_resources


def _generate_artifact_resources(
    bolt: Bolt, artifact: ExecutableArtifact, environment: ExecutionEnvironment
) -> list[KubernetesResource]:
    k8s_resources = []

    # Common metadata
    metadata = {"labels": {"service": artifact.id}, "name": artifact.id, "namespace": bolt.project_id}

    # TODO: Service types
    services = [{"container_port": 80, "name": "http", "external_host": None, "external_path": None, "target_port": 80}]

    # TODO: Probes
    liveness_probe = {}
    readiness_probe = {}
    startup_probe = {}

    pod_resources = {"requests": {}, "limits": {}}
    if local_resources := artifact.execution.local_resources:
        if local_resources.min_cpu:
            pod_resources["requests"]["cpu"] = local_resources.min_cpu
        if local_resources.min_memory:
            pod_resources["requests"]["memory"] = f"{local_resources.min_memory}Gi"
        if local_resources.max_cpu:
            pod_resources["limits"]["cpu"] = local_resources.max_cpu
        if local_resources.max_memory:
            pod_resources["limits"]["memory"] = f"{local_resources.max_memory}Gi"

    pod_template = {
        "spec": {  # PodTemplateSpec
            "metadata": metadata,
            "spec": {  # PodSpec
                "containers": [  # Container
                    {
                        "name": artifact.id,
                        "image": artifact.type.config.get("image", f"{artifact.id}:{bolt.version}"),
                        "livenessProbe": liveness_probe,
                        "ports": [
                            {
                                "containerPort": s["container_port"],
                                "name": s["name"],
                            }
                            for s in services
                        ],
                        "readinessProbe": readiness_probe,
                        "resources": {**pod_resources},  # ResourceRequirements
                        "startupProbe": startup_probe,
                    }
                ],
            },
        }
    }
    # TODO
    # env
    # securityContext

    # Deployment
    k8s_resources.append(
        (
            "Deployment",
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": metadata,
                "spec": {
                    "selector": {  # LabelSelector
                        "matchLabels": {"service": artifact.id}
                    },
                    "strategy": {
                        "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                        "type": "RollingUpdate",
                    },
                    "template": pod_template,  # PodTemplate
                },
            },
        )
    )

    # Service
    k8s_resources.append(
        (
            "Service",
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": metadata,
                "spec": {
                    "selector": {},
                    "ports": [{"port": s["target_port"], "name": s["name"], "targetPort": s["name"]} for s in services],
                },
            },
        )
    )
    # Ingress
    external_services = [s for s in services if s["external_host"] or s["external_path"]]

    if external_services:
        k8s_resources.append(
            (
                "Ingress",
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
        )

    return k8s_resources


def _generate_yaml_files(k8s_resources: Collection[KubernetesResource]) -> dict[str, str]:
    return {kind.lower() + ".yaml": yaml.dump(data) for kind, data in k8s_resources}


class KubernetesExecutionEnvironmentAdapter(ExecutionEnvironmentAdapter):
    def deploy(self, bolt: Bolt, artifacts: Collection[ExecutableArtifact], environment: ExecutionEnvironment):
        bolt_resources, artifact_resources = _generate_bolt_resources(
            bolt=bolt, artifacts=artifacts, environment=environment
        )

        _bolt_files = _generate_yaml_files(bolt_resources)

        _artifact_files = {
            artifact_id: _generate_yaml_files(resources) for artifact_id, resources in artifact_resources.items()
        }

    def fulfill_platform_resource_dependency(self, environment: ExecutionEnvironment, artifact: ExecutableArtifact):
        pass

    def list_artifact_types(self, environment: ExecutionEnvironment) -> list[ArtifactType]:
        return []

    def list_platform_resources(self, environment: ExecutionEnvironment) -> list[PlatformResource]:
        return []

    def list_services(self, environment: ExecutionEnvironment) -> list[ExecutableArtifact]:
        return []


class ArgoCDGitOpsKubernetesExecutionEnvironmentAdapter(KubernetesExecutionEnvironmentAdapter):
    pass
