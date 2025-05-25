import pytest

from ballista.adapters.kubernetes import KubernetesResource, _generate_bolt_resources
from ballista.adapters.types import ExecutionEnvironment
from ballista.types import Bolt


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
                        (
                            "Deployment",
                            {
                                "apiVersion": "apps/v1",
                                "kind": "Deployment",
                                "metadata": {
                                    "labels": {
                                        "app.kubernetes.io/name": "api",
                                        "app.kubernetes.io/managed-by": "Ballista",
                                        "app.kubernetes.io/part-of": "example",
                                        "app.kubernetes.io/version": "1",
                                    },
                                    "name": "api",
                                    "namespace": "example",
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
                                                "app.kubernetes.io/part-of": "example",
                                                "app.kubernetes.io/version": "1",
                                            },
                                            "name": "api",
                                            "namespace": "example",
                                        },
                                        "spec": {
                                            "containers": [
                                                {
                                                    "image": "hello-world:latest",
                                                    "name": "api",
                                                    "ports": [{"containerPort": 80, "name": "http"}],
                                                    "resources": {
                                                        "limits": {
                                                            "memory": "1.0Gi",
                                                        },
                                                        "requests": {"cpu": 0.25, "memory": "0.1Gi"},
                                                    },
                                                }
                                            ]
                                        },
                                    },
                                },
                            },
                        ),
                        (
                            "Service",
                            {
                                "apiVersion": "v1",
                                "kind": "Service",
                                "metadata": {
                                    "labels": {
                                        "app.kubernetes.io/name": "api",
                                        "app.kubernetes.io/managed-by": "Ballista",
                                        "app.kubernetes.io/part-of": "example",
                                        "app.kubernetes.io/version": "1",
                                    },
                                    "name": "api",
                                    "namespace": "example",
                                },
                                "spec": {
                                    "selector": {"app.kubernetes.io/name": "api"},
                                    "ports": [{"port": 80, "name": "http", "targetPort": "http"}],
                                },
                            },
                        ),
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
    execution_environment: ExecutionEnvironment,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]
    assert resources == _generate_bolt_resources(
        artifacts=executable_artifacts, bolt=bolt, environment=execution_environment
    )
