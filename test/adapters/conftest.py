import pytest

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.adapters.docker_compose import DockerComposeInfrastructureAdapter
from ballista_sdk.adapters.kubernetes import KubernetesAPIInfrastructureAdapter
from ballista_sdk.adapters.kubernetes.environments import KubernetesAPIEnvironment
from ballista_sdk.api.v1 import Bolt, Environment


@pytest.fixture(scope="session")
def postgres_bolt() -> Bolt:
    postgres_probe = {"exec": {"commands": ["pg_isready -U $POSTGRES_USER"], "shell": True}}

    return Bolt.model_validate(
        {
            "api_version": "v1",
            "artifacts": [
                {
                    "execution": {
                        "provides": {
                            "healthchecks": {
                                "alive": postgres_probe,
                                "ready": postgres_probe,
                                "started": postgres_probe,
                            },
                            "services": [{"name": "postgres", "tcp": 5432}],
                        },
                        "requires": {
                            "secrets": [
                                {
                                    "description": "Username for the default/root login.",
                                    "name": "root-username",
                                    "title": "Root Username",
                                    "type": "string",
                                },
                                {
                                    "description": "Password for the default/root login.",
                                    "name": "root-password",
                                    "title": "Root Password",
                                    "type": "string",
                                },
                            ],
                            "volumes": [
                                {
                                    "capacity": 0.1,
                                    "name": "data",
                                    "path": "/var/lib/postgresql/data",
                                    "persistent": True,
                                    "title": "PostgreSQL Data",
                                }
                            ],
                        },
                    },
                    "name": "server",
                    "type": {"docker_image": {"image": "postgres:18.1"}},
                },
                {
                    "name": "resource-providers",
                    "execution": {
                        "provides": {
                            "resources": [
                                {
                                    "name": "database",
                                    "description": "Postgres Database",
                                    "instance_id_fields": ["name"],
                                    "linked": {"services": [{"postgres": {"server": "postgres"}}]},
                                    "prefix": "POSTGRES",
                                    "requirements": {"properties": {"name": {"type": "string"}}, "required": ["name"]},
                                    "secrets": [
                                        {
                                            "type": "string",
                                            "description": "Name of Postgres database.",
                                            "name": "name",
                                            "title": "Database Name",
                                        },
                                        {
                                            "type": "string",
                                            "description": "Login username to access database.",
                                            "name": "username",
                                            "title": "Username",
                                        },
                                        {
                                            "type": "string",
                                            "description": "Login password to access database.",
                                            "name": "password",
                                            "title": "Password",
                                        },
                                    ],
                                    "services": [{"postgres": {"server": "postgres"}}],
                                    "title": "Postgres Database",
                                    "transport": {"rest": {"path": "/resources", "service": "rest"}},
                                },
                            ],
                            "services": [{"name": "rest", "http": 8000}],
                        },
                        "requires": {"services": [{"postgres": {"server": "postgres"}}]},
                    },
                    "type": {"docker_image": {"image": ""}},
                },
            ],
            "project": "postgres",
            "version": "18.1",
        }
    )


@pytest.fixture(scope="session")
def expected_bolts(postgres_bolt: Bolt) -> list[Bolt]:
    """Bolts that are expected to be available in environments."""

    return [postgres_bolt]


@pytest.fixture(scope="session")
def environment_with_docker_compose_adapter(
    expected_bolts: list[Bolt],
) -> tuple[Environment, DockerComposeInfrastructureAdapter]:
    adapter = DockerComposeInfrastructureAdapter(_bolts=expected_bolts)
    return adapter.get_development_environment(name="test", title="Test Environment"), adapter


@pytest.fixture(scope="session")
def kubernetes_api_adapter(expected_bolts: list[Bolt]) -> KubernetesAPIInfrastructureAdapter:
    return KubernetesAPIInfrastructureAdapter(_kubeconfig_file="ballista-test.kubeconfig")


@pytest.fixture(scope="session")
def environment_with_kubernetes_api_adapter(
    kubernetes_api_adapter: KubernetesAPIInfrastructureAdapter,
) -> tuple[KubernetesAPIEnvironment, KubernetesAPIInfrastructureAdapter]:
    return kubernetes_api_adapter.get_development_environment(
        name="test", title="Test Environment"
    ), kubernetes_api_adapter


@pytest.fixture(
    params=[
        pytest.param("docker-compose", marks=[pytest.mark.unit]),
        pytest.param("kubernetes-api", marks=[pytest.mark.integration]),
    ],
    scope="session",
)
def environment_with_infrastructure_adapter(
    request,
    environment_with_docker_compose_adapter: tuple[Environment, InfrastructureAdapter],
    environment_with_kubernetes_api_adapter: tuple[Environment, InfrastructureAdapter],
) -> tuple[Environment, InfrastructureAdapter]:
    if request.param == "docker-compose":
        return environment_with_docker_compose_adapter

    else:
        return environment_with_kubernetes_api_adapter
