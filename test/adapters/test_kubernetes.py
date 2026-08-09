import pytest

from ballista_sdk.adapters.infrastructure import resolve_artifact_requirements
from ballista_sdk.adapters.kubernetes import (
    KubernetesAPIInfrastructureAdapter,
)
from ballista_sdk.adapters.kubernetes.environments import KubernetesEnvironmentConfig
from ballista_sdk.adapters.kubernetes.primitives import KubernetesResource
from ballista_sdk.api.v1 import (
    Bolt,
    Environment,
    ExecutionParameters,
)
from ballista_sdk.bolts.v1 import BoltV1Factory


@pytest.fixture(scope="session")
def bolt(
    bolt_yaml: dict[str, dict | str],
) -> Bolt:
    factory = BoltV1Factory()

    bolt = factory.get_bolt(bolt_yaml)
    if bolt:
        return bolt

    raise Exception("WTF")


@pytest.fixture(scope="session")
def environment_config() -> KubernetesEnvironmentConfig:
    return KubernetesEnvironmentConfig()


@pytest.fixture(scope="session")
def simple_bolt_resources():
    return [], {
        "api": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/instance": "api-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "api",
                        "app.kubernetes.io/part-of": "simple",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                    },
                    "name": "simple-api",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app.kubernetes.io/name": "api",
                            "app.kubernetes.io/part-of": "simple",
                            "ballista.build/environment": "test",
                        }
                    },
                    "strategy": {
                        "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                        "type": "RollingUpdate",
                    },
                    "template": {
                        "metadata": {
                            "labels": {
                                "app.kubernetes.io/instance": "api-1",
                                "app.kubernetes.io/managed-by": "Ballista",
                                "app.kubernetes.io/name": "api",
                                "app.kubernetes.io/part-of": "simple",
                                "app.kubernetes.io/version": "1",
                                "ballista.build/environment": "test",
                                "ballista.build/environment-tier": "development",
                            },
                            "name": "simple-api",
                            "namespace": "test",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "env": [
                                        {"name": "HTTP_SERVICE_PORT", "value": "80"},
                                        {"name": "HTTP_SERVICE_HOST", "value": "test.ballista.build"},
                                        {"name": "HTTP_SERVICE_SECURE", "value": "false"},
                                        {"name": "HTTP_SERVICE_PATH", "value": "/"},
                                    ],
                                    "envFrom": [
                                        # Service configs are always first
                                        {"configMapRef": {"name": "simple-api", "optional": True}},
                                        # Service secrets are either first or second
                                        {"secretRef": {"name": "simple-api", "optional": False}},
                                        # Shared configs and secrets are next
                                        {
                                            "prefix": "POSTGRES_",
                                            "configMapRef": {
                                                "name": "postgres-resources-database",
                                                "optional": False,
                                            },
                                        },
                                    ],
                                    "image": "hello-world:latest",
                                    "name": "api",
                                    "ports": [{"containerPort": 80, "name": "http"}],
                                    "readinessProbe": {"httpGet": {"path": "/healthz", "port": "http"}},
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
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "volume_a",
                                    "persistentVolumeClaim": {"claimName": "simple-api-volume_a"},
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
                    "annotations": {"ballista.build/service-json": '{"name":"http","http":80}'},
                    "labels": {
                        "app.kubernetes.io/instance": "api-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "api",
                        "app.kubernetes.io/part-of": "simple",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "http",
                    },
                    "name": "simple-api-http",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "app.kubernetes.io/name": "api",
                        "app.kubernetes.io/part-of": "simple",
                        "ballista.build/environment": "test",
                    },
                    "ports": [{"port": 80, "name": "http", "targetPort": "http"}],
                },
            },
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/instance": "api-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "api",
                        "app.kubernetes.io/part-of": "simple",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                    },
                    "name": "simple-api-volume_a",
                    "namespace": "test",
                },
                "spec": {
                    "accessModes": ["ReadWriteMany"],
                    "resources": {"limits": {"storage": "1.0G"}, "requests": {"storage": "0.01G"}},
                    "storageClassName": "generic-storage",
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/instance": "api-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "api",
                        "app.kubernetes.io/part-of": "simple",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "http",
                    },
                    "name": "simple-api-http",
                    "namespace": "test",
                },
                "spec": {
                    "rules": [
                        {
                            "host": "test.ballista.build",
                            "http": {
                                "paths": [
                                    {
                                        "backend": {"service": {"name": "simple-api-http", "port": {"number": 80}}},
                                        "path": "/",
                                        "pathType": "Prefix",
                                    }
                                ]
                            },
                        }
                    ]
                },
            },
        ]
    }


@pytest.fixture(scope="session")
def project_bolt_resources():
    return [], {
        "resource-providers": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "annotations": {
                        "ballista.build/artifact-json": '{"name":"resource-providers","execution":{"provides":{"resources":[{"name":"project-resource1","description":"Resource Description","title":"Resource Provider Resource","configs":[{"name":"host","description":"Host of Database server.","title":"Host","type":"string","shared":true},{"name":"port","description":"Port Database server listens on.","title":"Port","type":"uint32","shared":true}],"instance_id_fields":["name"],"prefix":"RESOURCE1","requirements":{"properties":{"name":{"type":"string"}},"required":["name"]},"secrets":[{"name":"name","description":"Name of database","title":"Database","type":"string","shared":false},{"name":"username","description":"Login username to access database","title":"Username","type":"string","shared":false},{"name":"password","description":"Login password to access database","title":"Password","type":"string","shared":false}],"transport":{"rest":{"service":"resource-providers","path":"/resources"}}}],"services":[{"name":"resource-providers","http":80}]}},"type":{"docker_image":{"image":"hello-world:latest"}}}'
                    },
                    "labels": {
                        "app.kubernetes.io/instance": "resource-providers-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "resource-providers",
                        "app.kubernetes.io/part-of": "project",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/resource": "true",
                    },
                    "name": "project-resource-providers",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app.kubernetes.io/name": "resource-providers",
                            "app.kubernetes.io/part-of": "project",
                            "ballista.build/environment": "test",
                        }
                    },
                    "strategy": {
                        "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                        "type": "RollingUpdate",
                    },
                    "template": {
                        "metadata": {
                            "labels": {
                                "app.kubernetes.io/instance": "resource-providers-1",
                                "app.kubernetes.io/managed-by": "Ballista",
                                "app.kubernetes.io/name": "resource-providers",
                                "app.kubernetes.io/part-of": "project",
                                "app.kubernetes.io/version": "1",
                                "ballista.build/environment": "test",
                                "ballista.build/environment-tier": "development",
                                "ballista.build/resource": "true",
                            },
                            "name": "project-resource-providers",
                            "namespace": "test",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "env": [
                                        {"name": "RESOURCE_PROVIDERS_SERVICE_PORT", "value": "80"},
                                        {
                                            "name": "RESOURCE_PROVIDERS_SERVICE_HOST",
                                            "value": "test.ballista.build",
                                        },
                                        {"name": "RESOURCE_PROVIDERS_SERVICE_SECURE", "value": "false"},
                                        {"name": "RESOURCE_PROVIDERS_SERVICE_PATH", "value": "/"},
                                    ],
                                    "image": "hello-world:latest",
                                    "name": "resource-providers",
                                    "ports": [{"containerPort": 80, "name": "resource-providers"}],
                                    "resources": {
                                        "limits": {
                                            "memory": "1.0Gi",
                                        },
                                        "requests": {"cpu": "0.25G", "memory": "0.1Gi"},
                                    },
                                }
                            ],
                        },
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "annotations": {"ballista.build/service-json": '{"name":"resource-providers","http":80}'},
                    "labels": {
                        "app.kubernetes.io/instance": "resource-providers-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "resource-providers",
                        "app.kubernetes.io/part-of": "project",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "resource-providers",
                    },
                    "name": "project-resource-providers-resource-providers",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "app.kubernetes.io/name": "resource-providers",
                        "app.kubernetes.io/part-of": "project",
                        "ballista.build/environment": "test",
                    },
                    "ports": [{"port": 80, "name": "resource-providers", "targetPort": "resource-providers"}],
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/instance": "resource-providers-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "resource-providers",
                        "app.kubernetes.io/part-of": "project",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "resource-providers",
                    },
                    "name": "project-resource-providers-resource-providers",
                    "namespace": "test",
                },
                "spec": {
                    "rules": [
                        {
                            "host": "test.ballista.build",
                            "http": {
                                "paths": [
                                    {
                                        "backend": {
                                            "service": {
                                                "name": "project-resource-providers-resource-providers",
                                                "port": {"number": 80},
                                            }
                                        },
                                        "path": "/",
                                        "pathType": "Prefix",
                                    }
                                ]
                            },
                        }
                    ]
                },
            },
        ]
    }


@pytest.mark.integration
async def test_generate_resources(
    request,
    bolt: Bolt,
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    kubernetes_api_adapter: KubernetesAPIInfrastructureAdapter,
    execution_parameters: ExecutionParameters,
):
    bolt_name = request.node.callspec.params.get("bolt_yaml")
    expected_bolt_resources: tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]] = (
        request.getfixturevalue(f"{bolt_name}_bolt_resources")
    )

    resource_providers, service_providers = await resolve_artifact_requirements(
        kubernetes_api_adapter, environment, bolt
    )

    bolt_resources = kubernetes_api_adapter.generate_bolt_resources(
        bolt=bolt,
        environment=environment,
        environment_config=environment_config,
        execution_parameters=execution_parameters,
        resource_providers=resource_providers,
        service_providers=service_providers,
    )
    assert bolt_resources == expected_bolt_resources
