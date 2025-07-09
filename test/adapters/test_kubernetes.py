import pytest

from ballista.adapters.kubernetes import (
    KubernetesExecutionEnvironmentAdapter,
    KubernetesResource,
    _generate_bolt_resources,
)
from ballista.types import Bolt, Environment, EnvironmentArtifactExecutionParameters


@pytest.fixture
def kubernetes_adapter():
    return KubernetesExecutionEnvironmentAdapter()


@pytest.mark.parametrize(
    "bolt,resources",
    [
        (
            "simple",
            (
                [],
                {
                    "api": [
                        {
                            "apiVersion": "apps/v1",
                            "kind": "Deployment",
                            "metadata": {
                                "labels": {
                                    "app.kubernetes.io/managed-by": "Ballista",
                                    "app.kubernetes.io/name": "api",
                                    "app.kubernetes.io/part-of": "simple",
                                    "app.kubernetes.io/version": "1",
                                },
                                "name": "api",
                                "namespace": "simple-test",
                            },
                            "spec": {
                                "selector": {"matchLabels": {"app.kubernetes.io/name": "api"}},
                                "strategy": {
                                    "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                                    "type": "RollingUpdate",
                                },
                                "template": {
                                    "metadata": {
                                        "labels": {
                                            "app.kubernetes.io/managed-by": "Ballista",
                                            "app.kubernetes.io/name": "api",
                                            "app.kubernetes.io/part-of": "simple",
                                            "app.kubernetes.io/version": "1",
                                        },
                                        "name": "api",
                                        "namespace": "simple-test",
                                    },
                                    "spec": {
                                        "containers": [
                                            {
                                                "env": [
                                                    {"name": "HTTP_SERVICE_PORT", "value": "80"},
                                                ],
                                                "envFrom": [
                                                    {"configMapRef": {"name": "api", "optional": True}},
                                                    {"secretRef": {"name": "api", "optional": False}},
                                                ],
                                                "image": "hello-world:latest",
                                                "name": "api",
                                                "ports": [{"containerPort": 80, "name": "http"}],
                                                "readinessProbe": {"httpGet": {"path": "/healthz", "port": "http"}},
                                                "resources": {
                                                    "limits": {
                                                        "memory": "1.0G",
                                                    },
                                                    "requests": {"cpu": "0.25G", "memory": "0.1G"},
                                                },
                                                "volumeMounts": [
                                                    {
                                                        "mountPath": "/var/volume_a",
                                                        "name": "volume_a",
                                                        "subPath": "/custom/path/volume_a",
                                                    },
                                                ],
                                            }
                                        ],
                                        "volumes": [
                                            {
                                                "name": "volume_a",
                                                "persistentVolumeClaim": {"claimName": "api-volume_a"},
                                            },
                                        ],
                                    },
                                },
                            },
                        },
                        {
                            "apiVersion": "v1",
                            "kind": "Service",
                            "metadata": {
                                "labels": {
                                    "app.kubernetes.io/managed-by": "Ballista",
                                    "app.kubernetes.io/name": "api",
                                    "app.kubernetes.io/part-of": "simple",
                                    "app.kubernetes.io/version": "1",
                                },
                                "name": "api-http",
                                "namespace": "simple-test",
                            },
                            "spec": {
                                "selector": {"app.kubernetes.io/name": "api"},
                                "ports": [{"port": 80, "name": "http", "targetPort": "http"}],
                            },
                        },
                        {
                            "apiVersion": "v1",
                            "kind": "PersistentVolumeClaim",
                            "metadata": {
                                "labels": {
                                    "app.kubernetes.io/managed-by": "Ballista",
                                    "app.kubernetes.io/name": "api",
                                    "app.kubernetes.io/part-of": "simple",
                                    "app.kubernetes.io/version": "1",
                                },
                                "name": "api-volume_a",
                                "namespace": "simple-test",
                            },
                            "spec": {
                                "accessModes": ["ReadWriteMany"],
                                "resources": {"limits": {"storage": "1.0Gi"}, "requests": {"storage": "0.01Gi"}},
                                "storageClassName": "generic-storage",
                            },
                        },
                    ]
                },
            ),
        )
    ],
    ids=["simple"],
    indirect=["bolt"],
)
def test_resource_generation(
    bolt: Bolt,
    resources: tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]],
    environment: Environment,
    kubernetes_adapter: KubernetesExecutionEnvironmentAdapter,
    environment_artifact_execution_parameters: EnvironmentArtifactExecutionParameters,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]
    assert resources == _generate_bolt_resources(
        artifacts=executable_artifacts,
        bolt=bolt,
        adapter=kubernetes_adapter,
        environment=environment,
        execution_parameters=environment_artifact_execution_parameters,
    )
