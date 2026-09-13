import pytest

from ballista_sdk.adapters.infrastructure import resolve_artifact_requirements
from ballista_sdk.adapters.kubernetes import (
    KubernetesAPIInfrastructureAdapter,
)
from ballista_sdk.adapters.kubernetes.environments import KubernetesAPIEnvironment, KubernetesEnvironmentConfig
from ballista_sdk.adapters.kubernetes.primitives import KubernetesResource
from ballista_sdk.api.v1 import (
    Bolt,
    EnvironmentTier,
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
                    "annotations": {
                        "ballista.build/artifact-json": '{"name":"api","execution":{"provides":{"healthchecks":{"alive":{"http":{"service":"http","path":"/healthz"}},"ready":{"http":{"service":"http","path":"/healthz"}},"started":{"http":{"service":"http","path":"/healthz"}}},"services":[{"name":"http","http":80}]},"requires":{"configs":[{"name":"option-a","type":"string"}],"resources":[{"postgres":{"database":{"name":"testdatabase","name_alias":"BUG_DATABASE"}}}],"secrets":[{"name":"secret-a","type":"string"}],"volumes":[{"name":"volume-a","title":"Volume A","capacity":0.01,"path":"/var/volume-a","persistent":true}]}},"type":{"docker_image":{"image":"hello-world:latest"}}}'
                    },
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
                                        {
                                            "name": "POSTGRES_HOST",
                                            "value": "postgres-server-postgres.test.svc.cluster.local",
                                        },
                                        {"name": "POSTGRES_PORT", "value": "5432"},
                                        {"name": "POSTGRES_SECURE", "value": "false"},
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
                                    ],
                                    "image": "hello-world:latest",
                                    "livenessProbe": {"httpGet": {"path": "/healthz", "port": "http"}},
                                    "name": "api",
                                    "ports": [{"containerPort": 80, "name": "http"}],
                                    "readinessProbe": {"httpGet": {"path": "/healthz", "port": "http"}},
                                    "resources": {
                                        "limits": {
                                            "memory": "1.0Gi",
                                        },
                                        "requests": {"cpu": "250m", "memory": "0.1Gi"},
                                    },
                                    "startupProbe": {"httpGet": {"path": "/healthz", "port": "http"}},
                                    "volumeMounts": [
                                        {
                                            "mountPath": "/var/volume-a",
                                            "name": "volume-a",
                                            "subPath": "/custom/path/volume-a",
                                        },
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "volume-a",
                                    "persistentVolumeClaim": {"claimName": "simple-api-volume-a"},
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
                    "name": "simple-api-volume-a",
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
def small_app_bolt_resources():
    return [], {
        "backend": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "annotations": {
                        "ballista.build/artifact-json": '{"name":"backend","execution":{"provides":{"services":[{"name":"api","http":8000}]}},"type":{"docker_image":{"image":"hello-world:latest"}}}',
                    },
                    "labels": {
                        "app.kubernetes.io/instance": "backend-1.2.3",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "backend",
                        "app.kubernetes.io/part-of": "small-app",
                        "app.kubernetes.io/version": "1.2.3",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                    },
                    "name": "small-app-backend",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app.kubernetes.io/name": "backend",
                            "app.kubernetes.io/part-of": "small-app",
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
                                "app.kubernetes.io/instance": "backend-1.2.3",
                                "app.kubernetes.io/managed-by": "Ballista",
                                "app.kubernetes.io/name": "backend",
                                "app.kubernetes.io/part-of": "small-app",
                                "app.kubernetes.io/version": "1.2.3",
                                "ballista.build/environment": "test",
                                "ballista.build/environment-tier": "development",
                            },
                            "name": "small-app-backend",
                            "namespace": "test",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "env": [
                                        {"name": "API_SERVICE_PORT", "value": "8000"},
                                        {"name": "API_SERVICE_HOST", "value": "test.ballista.build"},
                                        {"name": "API_SERVICE_SECURE", "value": "false"},
                                        {"name": "API_SERVICE_PATH", "value": "/"},
                                    ],
                                    "image": "hello-world:latest",
                                    "name": "backend",
                                    "ports": [{"containerPort": 8000, "name": "api"}],
                                    "resources": {
                                        "limits": {
                                            "memory": "1.0Gi",
                                        },
                                        "requests": {"cpu": "250m", "memory": "0.1Gi"},
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
                    "annotations": {"ballista.build/service-json": '{"name":"api","http":8000}'},
                    "labels": {
                        "app.kubernetes.io/instance": "backend-1.2.3",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "backend",
                        "app.kubernetes.io/part-of": "small-app",
                        "app.kubernetes.io/version": "1.2.3",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "api",
                    },
                    "name": "small-app-backend-api",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "app.kubernetes.io/name": "backend",
                        "app.kubernetes.io/part-of": "small-app",
                        "ballista.build/environment": "test",
                    },
                    "ports": [{"port": 8000, "name": "api", "targetPort": "api"}],
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/instance": "backend-1.2.3",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "backend",
                        "app.kubernetes.io/part-of": "small-app",
                        "app.kubernetes.io/version": "1.2.3",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "api",
                    },
                    "name": "small-app-backend-api",
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
                                            "service": {"name": "small-app-backend-api", "port": {"number": 8000}}
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
        ],
        "ui": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "annotations": {
                        "ballista.build/artifact-json": '{"name":"ui","execution":{"provides":{"services":[{"name":"http","http":80}]},"requires":{"services":[{"small-app":{"backend":"api"}}]}},"type":{"docker_image":{"image":"hello-world:latest"}}}'
                    },
                    "labels": {
                        "app.kubernetes.io/instance": "ui-1.2.3",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "ui",
                        "app.kubernetes.io/part-of": "small-app",
                        "app.kubernetes.io/version": "1.2.3",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                    },
                    "name": "small-app-ui",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app.kubernetes.io/name": "ui",
                            "app.kubernetes.io/part-of": "small-app",
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
                                "app.kubernetes.io/instance": "ui-1.2.3",
                                "app.kubernetes.io/managed-by": "Ballista",
                                "app.kubernetes.io/name": "ui",
                                "app.kubernetes.io/part-of": "small-app",
                                "app.kubernetes.io/version": "1.2.3",
                                "ballista.build/environment": "test",
                                "ballista.build/environment-tier": "development",
                            },
                            "name": "small-app-ui",
                            "namespace": "test",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "env": [
                                        {"name": "SMALL_APP_BACKEND_API_HOST", "value": "api"},
                                        {"name": "SMALL_APP_BACKEND_API_PORT", "value": "8000"},
                                        {"name": "SMALL_APP_BACKEND_API_SECURE", "value": "false"},
                                        {"name": "HTTP_SERVICE_PORT", "value": "80"},
                                        {"name": "HTTP_SERVICE_HOST", "value": "test.ballista.build"},
                                        {"name": "HTTP_SERVICE_SECURE", "value": "false"},
                                        {"name": "HTTP_SERVICE_PATH", "value": "/"},
                                    ],
                                    "image": "hello-world:latest",
                                    "name": "ui",
                                    "ports": [{"containerPort": 80, "name": "http"}],
                                    "resources": {
                                        "limits": {
                                            "memory": "1.0Gi",
                                        },
                                        "requests": {"cpu": "250m", "memory": "0.1Gi"},
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
                    "annotations": {"ballista.build/service-json": '{"name":"http","http":80}'},
                    "labels": {
                        "app.kubernetes.io/instance": "ui-1.2.3",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "ui",
                        "app.kubernetes.io/part-of": "small-app",
                        "app.kubernetes.io/version": "1.2.3",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "http",
                    },
                    "name": "small-app-ui-http",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "app.kubernetes.io/name": "ui",
                        "app.kubernetes.io/part-of": "small-app",
                        "ballista.build/environment": "test",
                    },
                    "ports": [{"port": 80, "name": "http", "targetPort": "http"}],
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/instance": "ui-1.2.3",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "ui",
                        "app.kubernetes.io/part-of": "small-app",
                        "app.kubernetes.io/version": "1.2.3",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "http",
                    },
                    "name": "small-app-ui-http",
                    "namespace": "test",
                },
                "spec": {
                    "rules": [
                        {
                            "host": "test.ballista.build",
                            "http": {
                                "paths": [
                                    {
                                        "backend": {"service": {"name": "small-app-ui-http", "port": {"number": 80}}},
                                        "path": "/",
                                        "pathType": "Prefix",
                                    }
                                ]
                            },
                        }
                    ]
                },
            },
        ],
    }


@pytest.fixture(scope="session")
def resource_provider_bolt_resources():
    return [], {
        "dependent": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "annotations": {
                        "ballista.build/artifact-json": '{"name":"dependent","execution":{"requires":{"resources":[{"resource-provider":{"resource":{"name":"mine","name_alias":"DIFFERENT_NAME","host_alias":"DIFFERENT_HOST","port_alias":"DIFFERENT_PORT","secure_alias":"DIFFERENT_SECURE"}}}]}},"type":{"docker_image":{"image":"hello-world:latest"}}}'
                    },
                    "labels": {
                        "app.kubernetes.io/instance": "dependent-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "dependent",
                        "app.kubernetes.io/part-of": "resource-provider",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                    },
                    "name": "resource-provider-dependent",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app.kubernetes.io/name": "dependent",
                            "app.kubernetes.io/part-of": "resource-provider",
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
                                "app.kubernetes.io/instance": "dependent-1",
                                "app.kubernetes.io/managed-by": "Ballista",
                                "app.kubernetes.io/name": "dependent",
                                "app.kubernetes.io/part-of": "resource-provider",
                                "app.kubernetes.io/version": "1",
                                "ballista.build/environment": "test",
                                "ballista.build/environment-tier": "development",
                            },
                            "name": "resource-provider-dependent",
                            "namespace": "test",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "env": [
                                        {
                                            "name": "RESOURCE_HOST",
                                            "value": "postgres-server-postgres.test.svc.cluster.local",
                                        },
                                        {"name": "RESOURCE_PORT", "value": "5432"},
                                        {"name": "RESOURCE_SECURE", "value": "false"},
                                    ],
                                    "envFrom": [
                                        {
                                            "configMapRef": {
                                                "name": "resource-provider-dependent",
                                                "optional": True,
                                            },
                                        },
                                        {
                                            "secretRef": {
                                                "name": "resource-provider-dependent",
                                                "optional": False,
                                            },
                                        },
                                    ],
                                    "image": "hello-world:latest",
                                    "name": "dependent",
                                    "resources": {
                                        "limits": {
                                            "memory": "1.0Gi",
                                        },
                                        "requests": {"cpu": "250m", "memory": "0.1Gi"},
                                    },
                                }
                            ],
                        },
                    },
                },
            }
        ],
        "resource": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "annotations": {
                        "ballista.build/artifact-json": '{"name":"resource","execution":{"provides":{"resources":[{"name":"resource","description":"Resource Description","title":"Resource Provider Resource","configs":[{"name":"test-string","description":"Test string config.","title":"Test String","type":"string"}],"instance_id_fields":["name"],"linked":{"configs":["test-uint32"],"secrets":["test-bool"],"services":[{"postgres":{"server":"postgres"}}]},"prefix":"RESOURCE","requirements":{"properties":{"name":{"type":"string"}},"required":["name"]},"secrets":[{"name":"name","description":"Name of resource","title":"Name","type":"string"}],"transport":{"rest":{"service":"rest","path":"/resources"}}}],"services":[{"name":"rest","http":8000}]},"requires":{"configs":[{"name":"test-uint32","description":"Test unsigned int and linked config.","title":"Test Number","type":"uint32"}],"secrets":[{"name":"test-bool","description":"Test bool and linked secret.","title":"Test Bool","type":"bool"}],"services":[{"postgres":{"server":"postgres"}}]}},"type":{"docker_image":{"image":"hello-world:latest"}}}'
                    },
                    "labels": {
                        "app.kubernetes.io/instance": "resource-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "resource",
                        "app.kubernetes.io/part-of": "resource-provider",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/resource": "true",
                    },
                    "name": "resource-provider-resource",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app.kubernetes.io/name": "resource",
                            "app.kubernetes.io/part-of": "resource-provider",
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
                                "app.kubernetes.io/instance": "resource-1",
                                "app.kubernetes.io/managed-by": "Ballista",
                                "app.kubernetes.io/name": "resource",
                                "app.kubernetes.io/part-of": "resource-provider",
                                "app.kubernetes.io/version": "1",
                                "ballista.build/environment": "test",
                                "ballista.build/environment-tier": "development",
                                "ballista.build/resource": "true",
                            },
                            "name": "resource-provider-resource",
                            "namespace": "test",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "env": [
                                        {
                                            "name": "POSTGRES_SERVER_POSTGRES_HOST",
                                            "value": "postgres-server-postgres.test.svc.cluster.local",
                                        },
                                        {"name": "POSTGRES_SERVER_POSTGRES_PORT", "value": "5432"},
                                        {"name": "POSTGRES_SERVER_POSTGRES_SECURE", "value": "false"},
                                        {"name": "REST_SERVICE_PORT", "value": "8000"},
                                        {
                                            "name": "REST_SERVICE_HOST",
                                            "value": "test.ballista.build",
                                        },
                                        {"name": "REST_SERVICE_SECURE", "value": "false"},
                                        {"name": "REST_SERVICE_PATH", "value": "/"},
                                    ],
                                    "envFrom": [
                                        {"configMapRef": {"name": "resource-provider-resource", "optional": True}},
                                        {"secretRef": {"name": "resource-provider-resource", "optional": False}},
                                    ],
                                    "image": "hello-world:latest",
                                    "name": "resource",
                                    "ports": [{"containerPort": 8000, "name": "rest"}],
                                    "resources": {
                                        "limits": {
                                            "memory": "1.0Gi",
                                        },
                                        "requests": {"cpu": "250m", "memory": "0.1Gi"},
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
                    "annotations": {"ballista.build/service-json": '{"name":"rest","http":8000}'},
                    "labels": {
                        "app.kubernetes.io/instance": "resource-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "resource",
                        "app.kubernetes.io/part-of": "resource-provider",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "rest",
                    },
                    "name": "resource-provider-resource-rest",
                    "namespace": "test",
                },
                "spec": {
                    "selector": {
                        "app.kubernetes.io/name": "resource",
                        "app.kubernetes.io/part-of": "resource-provider",
                        "ballista.build/environment": "test",
                    },
                    "ports": [{"port": 8000, "name": "rest", "targetPort": "rest"}],
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/instance": "resource-1",
                        "app.kubernetes.io/managed-by": "Ballista",
                        "app.kubernetes.io/name": "resource",
                        "app.kubernetes.io/part-of": "resource-provider",
                        "app.kubernetes.io/version": "1",
                        "ballista.build/environment": "test",
                        "ballista.build/environment-tier": "development",
                        "ballista.build/service": "rest",
                    },
                    "name": "resource-provider-resource-rest",
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
                                                "name": "resource-provider-resource-rest",
                                                "port": {"number": 8000},
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
        ],
    }


@pytest.mark.integration
async def test_generate_resources(
    request,
    bolt: Bolt,
    environment_config: KubernetesEnvironmentConfig,
    environment_with_kubernetes_api_adapter: tuple[KubernetesAPIEnvironment, KubernetesAPIInfrastructureAdapter],
    execution_parameters: ExecutionParameters,
):
    environment, kubernetes_api_adapter = environment_with_kubernetes_api_adapter

    bolt_name = request.node.callspec.params.get("bolt_yaml").replace("-", "_")
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


@pytest.mark.integration
async def test_determine_execution_parameters(
    bolt: Bolt,
    environment_with_kubernetes_api_adapter: tuple[KubernetesAPIEnvironment, KubernetesAPIInfrastructureAdapter],
):
    environment, kubernetes_api_adapter = environment_with_kubernetes_api_adapter

    execution_parameters = await kubernetes_api_adapter.determine_execution_parameters(bolt, environment)

    expected_execution_parameters = ExecutionParameters.model_validate(
        {"environments": {"test": {"external_service": {"host": "ballista.build", "secure": True}}}}
    )

    assert execution_parameters.model_dump() == expected_execution_parameters.model_dump()


@pytest.mark.integration
async def test_list_environments(
    kubernetes_api_adapter: KubernetesAPIInfrastructureAdapter,
):
    environments = await kubernetes_api_adapter.list_environments()

    expected_environments = [
        KubernetesAPIEnvironment(
            name="test",
            tier=EnvironmentTier.DEVELOPMENT,
            title="Test Environment",
            kubeconfig_file="ballista-test.kubeconfig",
            kubeconfig_context=None,
        )
    ]

    assert environments == expected_environments
