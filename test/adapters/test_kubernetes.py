import pytest

from ballista.adapters.kubernetes import KubernetesResource, _generate_bolt_resources
from ballista.types import Bolt, Environment, EnvironmentArtifactExecutionParameters


@pytest.fixture
def kubernetes_adapter():
    pass


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
                                    "app.kubernetes.io/name": "api",
                                    "app.kubernetes.io/managed-by": "Ballista",
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
                                            "app.kubernetes.io/name": "api",
                                            "app.kubernetes.io/managed-by": "Ballista",
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
                                                    {"name": "HTTP_SERVICE_PATH", "value": "/"},
                                                    {"name": "HTTP_SERVICE_PORT", "value": "80"},
                                                ],
                                                "envFrom": [
                                                    {"configMapRef": {"name": "api", "optional": True}},
                                                    {"secretRef": {"name": "api", "optional": False}},
                                                ],
                                                "image": "hello-world:latest",
                                                "name": "api",
                                                "ports": [{"containerPort": 80, "name": "http"}],
                                                "resources": {
                                                    "limits": {
                                                        "memory": "1.0Gi",
                                                    },
                                                    "requests": {"cpu": "0.25G", "memory": "0.1Gi"},
                                                },
                                                "volumeMounts": [
                                                    {
                                                        "mountPath": "/var/volume_a",
                                                        "name": "volume_a",
                                                        "subPath": "/custom/path/volume_a",
                                                    },
                                                    {
                                                        "mountPath": "/var/volume_b",
                                                        "name": "volume_b",
                                                        "subPath": "/custom/path/volume_b",
                                                    },
                                                ],
                                            }
                                        ],
                                        "volumes": [
                                            {
                                                "name": "volume_a",
                                                "persistentVolumeClaim": {"claimName": "api-volume_a"},
                                            },
                                            {
                                                "ephemeral": {
                                                    "volumeClaimTemplate": {
                                                        "metadata": {
                                                            "labels": {
                                                                "app.kubernetes.io/name": "api",
                                                                "app.kubernetes.io/managed-by": "Ballista",
                                                                "app.kubernetes.io/part-of": "simple",
                                                                "app.kubernetes.io/version": "1",
                                                            },
                                                        },
                                                        "spec": {
                                                            "accessModes": ["ReadWriteOnce"],
                                                            "resources": {"requests": {"storage": "0.25G"}},
                                                            "storageClassName": "generic-storage",
                                                        },
                                                    }
                                                },
                                                "name": "volume_b",
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
                                    "app.kubernetes.io/name": "api",
                                    "app.kubernetes.io/managed-by": "Ballista",
                                    "app.kubernetes.io/part-of": "simple",
                                    "app.kubernetes.io/version": "1",
                                },
                                "name": "api",
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
                                    "app.kubernetes.io/name": "api",
                                    "app.kubernetes.io/managed-by": "Ballista",
                                    "app.kubernetes.io/part-of": "simple",
                                    "app.kubernetes.io/version": "1",
                                },
                                "name": "api-volume_a",
                                "namespace": "simple-test",
                            },
                            "spec": {
                                "accessModes": ["ReadWriteMany"],
                                "resources": {"limits": {"storage": "1.0G"}, "requests": {"storage": "0.25G"}},
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
    environment_artifact_execution_parameters: EnvironmentArtifactExecutionParameters,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]
    assert resources == _generate_bolt_resources(
        artifacts=executable_artifacts,
        bolt=bolt,
        environment=environment,
        execution_parameters=environment_artifact_execution_parameters,
    )
