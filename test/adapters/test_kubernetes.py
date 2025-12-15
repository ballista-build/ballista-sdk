from typing import cast

import pytest

from ballista_sdk.adapters.kubernetes import (
    BoundSetting,
    KubernetesConfigsAdapter,
    KubernetesInfrastructureAdapter,
    KubernetesResource,
    KubernetesSecretsAdapter,
    _generate_bolt_resources,
)
from ballista_sdk.api.v1 import (
    ArtifactReference,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    SettingDataType,
)
from ballista_sdk.bolts.v1 import BoltV1Factory


@pytest.fixture(scope="session")
def kubernetes_adapter(fake_bolts: list[Bolt]):
    return KubernetesInfrastructureAdapter(fake_bolts)


@pytest.fixture(scope="session", params=[pytest.param("configmap", marks=[pytest.mark.integration])])
def configs_adapters(request) -> KubernetesConfigsAdapter:
    match request.param:
        case "configmap":
            return KubernetesConfigsAdapter()

    raise ValueError()


@pytest.fixture(scope="session")
def bolt(
    bolt_yaml: dict[str, dict | str],
    environment: Environment,
    kubernetes_adapter: KubernetesInfrastructureAdapter,
) -> Bolt:
    factory = BoltV1Factory(environment, kubernetes_adapter)

    bolt = factory.get_bolt(bolt_yaml)
    if bolt:
        return bolt

    raise Exception("WTF")


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
                                        {"name": "HTTP_SERVICE_PATH", "value": "/"},
                                    ],
                                    "envFrom": [
                                        # Service configs are always first
                                        {"configMapRef": {"name": "simple.api", "optional": True}},
                                        # Service secrets are either first or second
                                        {"secretRef": {"name": "simple.api", "optional": False}},
                                        # Shared configs and secrets are next
                                        {
                                            "prefix": "POSTGRES_",
                                            "configMapRef": {
                                                "name": "postgres.resources.database",
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
    }


@pytest.fixture(scope="session")
def resource_provider_bolt_resources():
    return [], {
        "server": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "annotations": {
                        "ballista.build/resource-json": '{"name":"resource_provider-resource1","description":"Resource Description","title":"Resource Provider Resource","configs":[{"name":"host","description":"Host of Database server.","title":"Host","data_type":"string","shared":true},{"name":"port","description":"Port Database server listens on.","title":"Port","data_type":"integer","shared":true}],"instance_id_fields":["name"],"prefix":"RESOURCE1","requirements":{"properties":{"name":{"type":"string"}},"required":["name"]},"secrets":[{"name":"name","description":"Name of database","title":"Database","data_type":"string","shared":false},{"name":"username","description":"Login username to access database","title":"Username","data_type":"string","shared":false},{"name":"password","description":"Login password to access database","title":"Password","data_type":"string","shared":false}]}'
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
    }


@pytest.mark.unit
def test_generate_resources(
    request,
    bolt: Bolt,
    environment: Environment,
    kubernetes_adapter: KubernetesInfrastructureAdapter,
    execution_parameters: ExecutionParameters,
):
    bolt_name = request.node.callspec.params.get("bolt_yaml")
    resources: tuple[list[KubernetesResource], dict[str, list[KubernetesResource]]] = request.getfixturevalue(
        f"{bolt_name}_bolt_resources"
    )
    executable_artifacts = [cast(ExecutableArtifact, a) for a in bolt.artifacts if a.execution is not None]
    assert (
        _generate_bolt_resources(
            artifacts=executable_artifacts,
            bolt=bolt,
            adapter=kubernetes_adapter,
            environment=environment,
            execution_parameters=execution_parameters,
        )
        == resources
    )


@pytest.mark.integration
def test_artifact_configs(
    bolt: Bolt,
    sample_artifact_configs: tuple,
    configs_adapters: KubernetesConfigsAdapter,
    environment: Environment,
):
    config, setting_value = sample_artifact_configs
    bound_config = BoundSetting(
        setting=config, artifact=ArtifactReference(bolt.project, bolt.executable_artifacts[0].name, bolt.version)
    )

    assert configs_adapters.exists(environment, bound_config) is False

    configs_adapters.write(environment, bound_config, setting_value)

    assert configs_adapters.read(environment, bound_config) == setting_value


@pytest.mark.unit
def test_kubernetes_configs_adapter_encoding():
    configs = [
        ("events_enabled", SettingDataType.BOOLEAN, True),
        ("events_disabled", SettingDataType.BOOLEAN, False),
        ("name", SettingDataType.STRING, "francis bombast"),
        ("key_material", SettingDataType.BYTES, b"some binary data"),
        ("max_limit_request", SettingDataType.INTEGER, 445),
    ]

    configs_adapter = KubernetesConfigsAdapter()

    assert configs_adapter._generate_configmap_data(configs) == {
        "binaryData": {"key_material": b"c29tZSBiaW5hcnkgZGF0YQ=="},
        "data": {
            "events_enabled": "True",
            "events_disabled": "False",
            "name": "francis bombast",
            "max_limit_request": "445",
        },
    }


@pytest.mark.unit
def test_kubernetes_secrets_adapter_encoding():
    secrets = [
        ("events_enabled", SettingDataType.BOOLEAN, True),
        ("events_disabled", SettingDataType.BOOLEAN, False),
        ("name", SettingDataType.STRING, "francis bombast"),
        ("key_material", SettingDataType.BYTES, b"some binary data"),
        ("max_limit_request", SettingDataType.INTEGER, 445),
    ]

    secrets_adapter = KubernetesSecretsAdapter()

    assert secrets_adapter._generate_secret_data(secrets) == {
        "data": {
            "events_enabled": b"VHJ1ZQ==",
            "events_disabled": b"RmFsc2U=",
            "key_material": b"c29tZSBiaW5hcnkgZGF0YQ==",
            "name": b"ZnJhbmNpcyBib21iYXN0",
            "max_limit_request": b"NDQ1",
        },
        "type": "Opaque",
    }
