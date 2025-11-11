from typing import cast

import pytest

from ballista_sdk.adapters.kubernetes import (
    KubernetesExecutionEnvironmentAdapter,
    KubernetesResource,
    _generate_bolt_resources,
)
from ballista_sdk.types import Bolt, Environment, ExecutableArtifact, ExecutionParameters, SpecificArtifact


@pytest.fixture
def kubernetes_adapter(fake_executable_artifacts: list[SpecificArtifact]):
    return KubernetesExecutionEnvironmentAdapter(fake_executable_artifacts)


@pytest.fixture
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
                                                "name": "postgres-database-shared",
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
                    "labels": {
                        "app.kubernetes.io/instance": "api-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "api",
                        "app.kubernetes.io/part-of": "simple",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
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
                    },
                    "name": "simple-api",
                    "namespace": "test",
                },
                "spec": {
                    "rules": [
                        {
                            "host": "test.ballista.build",
                            "http": {
                                "paths": [
                                    {
                                        "backend": {"service": {"name": "http", "port": {"number": 80}}},
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


@pytest.fixture
def resource_provider_bolt_resources():
    return [], {}


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
                                                            "name": "postgres-database-shared",
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
                                },
                                "name": "simple-api",
                                "namespace": "test",
                            },
                            "spec": {
                                "rules": [
                                    {
                                        "host": "test.ballista.build",
                                        "http": {
                                            "paths": [
                                                {
                                                    "backend": {"service": {"name": "http", "port": {"number": 80}}},
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
                },
            ),
        ),
        (
            "resource_provider",
            (
                [],
                {
                    "server": [
                        {
                            "apiVersion": "apps/v1",
                            "kind": "Deployment",
                            "metadata": {
                                "annotations": {
                                    "ballista.build/resource-json": '{"configs":[{"description":"Host of Database server.","id":"host","name":"Host","template":"","type":"string","shared":true},{"description":"Port Database server listens on.","id":"port","name":"Port","template":"","type":"integer","shared":true}],"description":"Resource Description","id":"resource_provider-resource1","instance_id_fields":["database_id"],"name":"Resource Provider Resource","prefix":"RESOURCE","requirement_schemas":{"properties":{},"required":[]},"secrets":[{"description":"Name of database","id":"database","name":"Database","template":"","type":"string","shared":false},{"description":"Login username to access database","id":"username","name":"Username","template":"","type":"string","shared":false},{"description":"Login password to access database","id":"password","name":"Password","template":null,"type":"password","shared":false}]}'
                                },
                                "labels": {
                                    "app.kubernetes.io/instance": "server-1",
                                    "app.kubernetes.io/managed-by": "Ballista",
                                    "app.kubernetes.io/name": "server",
                                    "app.kubernetes.io/part-of": "resource_provider",
                                    "app.kubernetes.io/version": "1",
                                    "ballista.build/environment": "test",
                                    "ballista.build/environment-tier": "development",
                                    "ballista.build/resource": "resource_provider-resource1",
                                },
                                "name": "resource_provider-server",
                                "namespace": "test",
                            },
                            "spec": {
                                "selector": {
                                    "matchLabels": {
                                        "app.kubernetes.io/name": "server",
                                        "app.kubernetes.io/part-of": "resource_provider",
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
                                            "app.kubernetes.io/instance": "server-1",
                                            "app.kubernetes.io/managed-by": "Ballista",
                                            "app.kubernetes.io/name": "server",
                                            "app.kubernetes.io/part-of": "resource_provider",
                                            "app.kubernetes.io/version": "1",
                                            "ballista.build/environment": "test",
                                            "ballista.build/environment-tier": "development",
                                            "ballista.build/resource": "resource_provider-resource1",
                                        },
                                        "name": "resource_provider-server",
                                        "namespace": "test",
                                    },
                                    "spec": {
                                        "containers": [
                                            {
                                                "image": "hello-world:latest",
                                                "name": "server",
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
                        }
                    ]
                },
            ),
        ),
    ],
    ids=["simple", "resource_provider"],
    indirect=["bolt"],
)
def test_resource_generation(
    bolt: Bolt,
    resources: tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]],
    environment: Environment,
    kubernetes_adapter: KubernetesExecutionEnvironmentAdapter,
    execution_parameters: ExecutionParameters,
):
    executable_artifacts = [cast(ExecutableArtifact, a) for a in bolt.artifacts if a.execution is not None]
    assert resources == _generate_bolt_resources(
        artifacts=executable_artifacts,
        bolt=bolt,
        adapter=kubernetes_adapter,
        environment=environment,
        execution_parameters=execution_parameters,
    )
