import pytest

from ballista.adapters.kubernetes import BoltK8sResources, _generate_bolt_resources
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
                                "metadata": {"labels": {"service": "api"}, "name": "api", "namespace": "example"},
                                "spec": {
                                    "selector": {"matchLabels": {"service": "api"}},
                                    "strategy": {
                                        "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                                        "type": "RollingUpdate",
                                    },
                                    "template": {
                                        "spec": {
                                            "metadata": {
                                                "labels": {"service": "api"},
                                                "name": "api",
                                                "namespace": "example",
                                            },
                                            "spec": {
                                                "containers": [
                                                    {
                                                        "image": "api:1",
                                                        "livenessProbe": {},
                                                        "name": "api",
                                                        "ports": [{"containerPort": 80, "name": "http"}],
                                                        "readinessProbe": {},
                                                        "resources": {
                                                            "limits": {
                                                                "memory": "1.0Gi",
                                                            },
                                                            "requests": {"cpu": 0.25, "memory": "0.1Gi"},
                                                        },
                                                        "startupProbe": {},
                                                    }
                                                ]
                                            },
                                        }
                                    },
                                },
                            },
                        ),
                        (
                            "Service",
                            {
                                "apiVersion": "v1",
                                "kind": "Service",
                                "metadata": {"labels": {"service": "api"}, "name": "api", "namespace": "example"},
                                "spec": {
                                    "selector": {},
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
def test_resource_generation(bolt: Bolt, resources: BoltK8sResources, execution_environment: ExecutionEnvironment):
    assert resources == _generate_bolt_resources(
        artifacts=bolt.executable_artifacts, bolt=bolt, environment=execution_environment
    )
