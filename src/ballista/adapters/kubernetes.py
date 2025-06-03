from collections.abc import Collection
from typing import Any, TypedDict

import yaml
from kubernetes import client, config, utils

from ballista.adapters.types import ConfigsAdapter, ExecutionEnvironmentAdapter, SecretsAdapter
from ballista.types import ArtifactType, Bolt, ExecutableArtifact, ExecutionEnvironment, PlatformResource


class KubernetesResource(TypedDict):
    apiVersion: str
    kind: str
    metadata: dict[str, Any]
    spec: dict[str, Any]


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
    k8s_resources: list[KubernetesResource] = []
    return k8s_resources, artifact_resources


def _generate_artifact_resources(
    bolt: Bolt, artifact: ExecutableArtifact, environment: ExecutionEnvironment
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

    container = {}

    # TODO: Service types
    services = [{"container_port": 80, "name": "http", "external_host": None, "external_path": None, "target_port": 80}]
    env.extend([{"name": "HTTP_SERVICE_PATH", "value": "/"}, {"name": "HTTP_SERVICE_PORT", "value": "80"}])

    container = {
        "env": env,
        "name": service_name,
        "image": artifact.type.config.get("image", f"{artifact.id}:{bolt.version}"),
        "ports": [
            {
                "containerPort": s["container_port"],
                "name": s["name"],
            }
            for s in services
        ],
    }

    # Configs
    if artifact.execution.configs:
        env_from.append({"configMapRef": {"name": service_env_name, "optional": True}})

    # Local Resources
    if local_resources := artifact.execution.local_resources:
        pod_resources = {"requests": {}, "limits": {}}
        if local_resources.min_cpu:
            pod_resources["requests"]["cpu"] = local_resources.min_cpu
        if local_resources.min_memory:
            pod_resources["requests"]["memory"] = f"{local_resources.min_memory}Gi"
        if local_resources.max_cpu:
            pod_resources["limits"]["cpu"] = local_resources.max_cpu
        if local_resources.max_memory:
            pod_resources["limits"]["memory"] = f"{local_resources.max_memory}Gi"

        container["resources"] = pod_resources

    has_service_secrets = bool(artifact.execution.secrets)

    # TODO: Platform Resources

    # Secrets
    if has_service_secrets:
        env_from.append({"secretRef": {"name": service_env_name, "optional": False}})

    if env_from:
        container["envFrom"] = env_from

    pod_template = {
        "metadata": metadata,
        "spec": {  # PodTemplateSpec
            "containers": [  # Container
                container
            ],
        },
    }

    # TODO
    # env
    # probes
    # securityContext

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

    # Service
    k8s_resources.append(
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": metadata,
            "spec": {
                "selector": {"app.kubernetes.io/name": service_name},
                "ports": [{"port": s["target_port"], "name": s["name"], "targetPort": s["name"]} for s in services],
            },
        }
    )
    # Ingress
    external_services = [s for s in services if s["external_host"] or s["external_path"]]

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


class KubernetesExecutionEnvironmentAdapter(ExecutionEnvironmentAdapter):
    def deploy(self, bolt: Bolt, artifacts: Collection[ExecutableArtifact], environment: ExecutionEnvironment):
        bolt_resources, all_artifact_resources = _generate_bolt_resources(
            bolt=bolt, artifacts=artifacts, environment=environment
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


class KubernetesSecretSecretsAadapter(SecretsAdapter):
    pass


class KubernetesConfigMapConfigsAdapter(ConfigsAdapter):
    pass
