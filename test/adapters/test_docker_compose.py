import pytest

from ballista_sdk.adapters.docker_compose import DockerComposeInfrastructureAdapter
from ballista_sdk.adapters.docker_compose.generation import (
    DockerComposeProject,
    DockerComposeProjectVolume,
    DockerComposeService,
    DockerComposeServiceVolume,
)
from ballista_sdk.adapters.infrastructure import resolve_artifact_requirements
from ballista_sdk.api.v1 import (
    Bolt,
    Environment,
    ExecutionParameters,
)
from ballista_sdk.bolts.v1 import BoltV1Factory


@pytest.fixture
def simple_docker_compose_project():
    return DockerComposeProject(
        name="simple",
        networks={
            "project-simple": {"internal": True, "name": "project-simple"},
            "env-test": {"internal": True, "name": "env-test"},
            "external-test.ballista.build": {"name": "external-test.ballista.build"},
        },
        services={
            "simple-api": DockerComposeService(
                container_name="simple-api",
                depends_on={
                    "postgres-resource-providers": {"condition": "service_healthy"},
                    "postgres-server": {"condition": "service_healthy"},
                },
                deploy={
                    "resources": {
                        "limits": {"memory": "1.0g"},
                        "reservations": {"cpus": "0.25", "memory": "0.1g"},
                    }
                },
                environment={
                    "HTTP_SERVICE_HOST": "test.ballista.build",
                    "HTTP_SERVICE_PATH": "/",
                    "HTTP_SERVICE_SECURE": "false",
                    "HTTP_SERVICE_PORT": "80",
                    "RENAMED_HOST": "postgres",
                    "OTHER_PORT": "5432",
                    "RETITLED_SECURE": "false",
                },
                env_file=[
                    {"format": "raw", "path": "simple-api-configs.env", "required": False},
                    {"format": "raw", "path": "simple-api-secrets.env", "required": True},
                ],
                healthcheck={
                    "start_interval": "1s",
                    "start_period": "60s",
                    "test": ["CMD-SHELL", "curl -f http://localhost:80/healthz"],
                },
                image="hello-world:latest",
                networks={
                    "project-simple": {},
                    "env-test": {},
                    "external-test.ballista.build": {"aliases": ["test.ballista.build"]},
                },
                ports=[{"name": "http", "published": "80", "target": "80"}],
                volumes=[
                    DockerComposeServiceVolume(
                        source="simple-api-volume-a",
                        target="/var/volume-a",
                        type="volume",
                        volume={"subpath": "/custom/path"},
                    ),
                ],
            ),
        },
        volumes={"simple-api-volume-a": DockerComposeProjectVolume(driver="local", name="Volume-A")},
    )


@pytest.fixture
def small_app_docker_compose_project() -> DockerComposeProject:
    return DockerComposeProject(
        name="small-app",
        networks={
            "env-test": {"internal": True, "name": "env-test"},
            "external-test.ballista.build": {"name": "external-test.ballista.build"},
            "project-small-app": {"internal": True, "name": "project-small-app"},
        },
        services={
            "small-app-backend": DockerComposeService(
                container_name="small-app-backend",
                environment={
                    "API_SERVICE_HOST": "test.ballista.build",
                    "API_SERVICE_PATH": "/",
                    "API_SERVICE_PORT": "8000",
                    "API_SERVICE_SECURE": "false",
                },
                deploy={
                    "resources": {"limits": {"memory": "1.0g"}, "reservations": {"cpus": "0.25", "memory": "0.1g"}}
                },
                image="hello-world:latest",
                networks={
                    "env-test": {},
                    "external-test.ballista.build": {"aliases": ["test.ballista.build"]},
                    "project-small-app": {},
                },
                ports=[{"name": "api", "published": "8000", "target": "8000"}],
            ),
            "small-app-ui": DockerComposeService(
                container_name="small-app-ui",
                depends_on={"small-app-backend": {"condition": "service_healthy"}},
                deploy={
                    "resources": {"limits": {"memory": "1.0g"}, "reservations": {"cpus": "0.25", "memory": "0.1g"}}
                },
                environment={
                    "HTTP_SERVICE_HOST": "test.ballista.build",
                    "HTTP_SERVICE_PATH": "/",
                    "HTTP_SERVICE_PORT": "80",
                    "HTTP_SERVICE_SECURE": "false",
                    "ALIASED_HOST": "api",
                    "ALIASED_PORT": "8000",
                    "ALIASED_SECURE": "false",
                },
                image="hello-world:latest",
                networks={
                    "env-test": {},
                    "external-test.ballista.build": {"aliases": ["test.ballista.build"]},
                    "project-small-app": {},
                },
                ports=[{"name": "http", "published": "80", "target": "80"}],
            ),
        },
    )


@pytest.fixture
def resource_provider_docker_compose_project():
    return DockerComposeProject(
        name="resource-provider",
        networks={
            "env-test": {"internal": True, "name": "env-test"},
            "external-test.ballista.build": {"name": "external-test.ballista.build"},
            "project-resource-provider": {"internal": True, "name": "project-resource-provider"},
        },
        services={
            "resource-provider-dependent": DockerComposeService(
                container_name="resource-provider-dependent",
                depends_on={
                    "postgres-server": {"condition": "service_healthy"},
                    "resource-provider-resource": {"condition": "service_healthy"},
                },
                deploy={
                    "resources": {
                        "limits": {"memory": "1.0g"},
                        "reservations": {"cpus": "0.25", "memory": "0.1g"},
                    }
                },
                environment={"DIFFERENT_HOST": "postgres", "DIFFERENT_PORT": "5432", "DIFFERENT_SECURE": "false"},
                env_file=[
                    {"format": "raw", "path": "resource-provider-dependent-configs.env", "required": False},
                    {"format": "raw", "path": "resource-provider-dependent-secrets.env", "required": True},
                ],
                image="hello-world:latest",
                networks={"env-test": {}, "project-resource-provider": {}},
            ),
            "resource-provider-resource": DockerComposeService(
                container_name="resource-provider-resource",
                depends_on={"postgres-server": {"condition": "service_healthy"}},
                deploy={
                    "resources": {
                        "limits": {"memory": "1.0g"},
                        "reservations": {"cpus": "0.25", "memory": "0.1g"},
                    }
                },
                environment={
                    "POSTGRES_SERVER_POSTGRES_HOST": "postgres",
                    "POSTGRES_SERVER_POSTGRES_PORT": "5432",
                    "POSTGRES_SERVER_POSTGRES_SECURE": "false",
                    "REST_SERVICE_HOST": "test.ballista.build",
                    "REST_SERVICE_PATH": "/",
                    "REST_SERVICE_SECURE": "false",
                    "REST_SERVICE_PORT": "8000",
                },
                env_file=[
                    {"format": "raw", "path": "resource-provider-resource-configs.env", "required": False},
                    {"format": "raw", "path": "resource-provider-resource-secrets.env", "required": True},
                ],
                image="hello-world:latest",
                networks={
                    "project-resource-provider": {},
                    "env-test": {},
                    "external-test.ballista.build": {"aliases": ["test.ballista.build"]},
                },
                ports=[{"name": "rest", "published": "8000", "target": "8000"}],
            ),
        },
        volumes={},
    )


@pytest.fixture(scope="session")
def bolt(
    bolt_yaml: dict[str, dict | str],
) -> Bolt:
    factory = BoltV1Factory()

    bolt = factory.get_bolt(bolt_yaml)
    if bolt:
        return bolt

    raise Exception("WTF")


@pytest.mark.unit
async def test_generate_docker_compose(
    request,
    bolt: Bolt,
    environment_with_docker_compose_adapter: tuple[Environment, DockerComposeInfrastructureAdapter],
    execution_parameters: ExecutionParameters,
):
    environment, docker_compose_adapter = environment_with_docker_compose_adapter
    bolt_name = request.node.callspec.params.get("bolt_yaml").replace("-", "_")
    docker_compose_project = request.getfixturevalue(f"{bolt_name}_docker_compose_project")

    resource_providers, service_providers = await resolve_artifact_requirements(
        docker_compose_adapter, environment, bolt
    )

    generated_docker_compose_project = docker_compose_adapter.generate_docker_compose_project_from_bolt(
        environment=environment,
        bolt=bolt,
        execution_parameters=execution_parameters,
        resource_providers=resource_providers,
        service_providers=service_providers,
    )

    assert generated_docker_compose_project.model_dump() == docker_compose_project.model_dump()
