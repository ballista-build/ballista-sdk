import pytest
import yaml

from ballista_sdk.adapters.infrastructure import ArtifactReference, ProvidedResourceWithArtifactReference
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactTypeRequirement,
    Bolt,
    ComputeExecutionParameters,
    DefaultExecutionParameters,
    Environment,
    EnvironmentTier,
    ExecutionParameters,
    ExternalizedServiceParameters,
    Project,
    ScalingExecutionParameters,
    VolumeExecutionParameters,
)


@pytest.fixture(scope="session")
def project():
    return Project(name="typical", title="Typical Project")


@pytest.fixture(scope="session")
def docker_image_artifact_type_need() -> ArtifactTypeRequirement:
    return ArtifactTypeRequirement.model_validate({"docker_image": {"image": "hello-world:latest"}})


# yaml
TEST_BOLTS: dict[str, str] = {
    "simple": """
api_version: "v1"
artifacts:
      - name: api
        execution:
            provides:
                healthchecks:
                    ready:
                        http:
                            path: "/healthz"
                            service: "http"
                services:
                  - name: http
                    http: 80
            requires:
                configs:
                    - name: "option_a"
                      type: "string"
                resources:
                    - postgres:
                        database:
                            name: "testdatabase"
                            name_alias: "BUG_DATABASE"
                secrets:
                    - name: "secret_a"
                      type: "string"
                volumes:
                    - name: "volume_a"
                      capacity: 0.01
                      path: "/var/volume_a"
                      persistent: True
                      title: "Volume A"
        type:
            docker_image:
                image: "hello-world:latest"
project: "simple"
version: "1"
""",
    #     "typical": """
    # YAML
    # """,
    "project": """
api_version: "v1"
artifacts:
      - name: "resource-providers"
        execution:
            provides:
                resources:
                  - configs:
                      - type: "string"
                        description: "Host of Database server."
                        name: "host"
                        shared: True
                        title: "Host"
                      - type: "uint32"
                        description: "Port Database server listens on."
                        name: "port"
                        shared: True
                        title: "Port"
                    description: "Resource Description"
                    name: "project-resource1"
                    instance_id_fields: ["name"]
                    prefix: "RESOURCE1"
                    requirements:
                        properties:
                            name:
                                type: string
                        required: ["name"]
                    secrets:
                      - type: "string"
                        description: "Name of database"
                        name: "name"
                        shared: False
                        title: "Database"
                      - type: "string"
                        description: "Login username to access database"
                        name: "username"
                        shared: False
                        title: "Username"
                      - type: "string"
                        description: "Login password to access database"
                        name: "password"
                        shared: False
                        title: "Password"
                    title: "Resource Provider Resource"
                    transport:
                        rest:
                            path: "/resources"
                            service: "resource-providers"
                services:
                  - name: "resource-providers"
                    http: 80
        type:
            docker_image:
                image: "hello-world:latest"
project: "project"
version: "1"
    """,
}


@pytest.fixture(scope="session", params=["simple", "project"])
def bolt_yaml(request) -> dict[str, str | dict]:
    return yaml.safe_load(TEST_BOLTS[request.param])


@pytest.fixture(scope="session")
def postgres_bolt() -> Bolt:
    # Fake Postgres
    postgres_probe = {"exec": {"commands": ["pg_isready -U $POSTGRES_USER"], "shell": True}}
    server_artifact = Artifact.model_validate(
        {
            "execution": {
                "provides": {
                    "healthchecks": {"alive": postgres_probe, "ready": postgres_probe, "started": postgres_probe},
                    "services": [{"name": "postgres", "tcp": 5432}],
                },
                "requires": {
                    "secrets": [
                        {
                            "description": "Username for the default/root login.",
                            "name": "root_username",
                            "title": "Root Username",
                            "type": "string",
                        },
                        {
                            "description": "Password for the default/root login.",
                            "name": "root_password",
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
        }
    )
    resource_providers_artifact = Artifact.model_validate(
        {
            "name": "resource-providers",
            "execution": {
                "provides": {
                    "resources": [
                        {
                            "name": "database",
                            "configs": [
                                {
                                    "description": "Host of Postgres server.",
                                    "name": "host",
                                    "shared": True,
                                    "title": "Host",
                                    "type": "string",
                                },
                                {
                                    "description": "Port Postgres server listens on.",
                                    "name": "port",
                                    "shared": True,
                                    "title": "Port",
                                    "type": "uint32",
                                },
                            ],
                            "description": "Postgres Database",
                            "instance_id_fields": ["name"],
                            "prefix": "POSTGRES",
                            "requirements": {"properties": {"name": {"type": "string"}}, "required": ["name"]},
                            "secrets": [
                                {
                                    "type": "string",
                                    "description": "Name of Postgres database.",
                                    "name": "name",
                                    "shared": False,
                                    "title": "Database Name",
                                },
                                {
                                    "type": "string",
                                    "description": "Login username to access database.",
                                    "name": "username",
                                    "shared": False,
                                    "title": "Username",
                                },
                                {
                                    "type": "string",
                                    "description": "Login password to access database.",
                                    "name": "password",
                                    "shared": False,
                                    "title": "Password",
                                },
                            ],
                            "title": "Postgres Database",
                            "transport": {"rest": {"path": "/resources", "service": "resource-providers"}},
                        },
                    ],
                    "services": [{"name": "resource-providers", "http": 345}],
                },
                "requires": {"services": [{"postgres": {"server": "postgres"}}]},
            },
            "type": {"docker_image": {"image": ""}},
        }
    )

    return Bolt(
        api_version="v1", artifacts=[server_artifact, resource_providers_artifact], project="postgres", version="18.1.0"
    )


@pytest.fixture(scope="session")
def artifact_reference() -> ArtifactReference:
    return ArtifactReference(project_name="simple", artifact_name="api", version="1")


@pytest.fixture(scope="session")
def provided_resource_with_artifact(postgres_bolt: Bolt) -> ProvidedResourceWithArtifactReference:
    artifact = postgres_bolt.artifacts[1]

    return ProvidedResourceWithArtifactReference(
        artifact.execution.provides.resources[0],
        ArtifactReference(
            project_name=postgres_bolt.project, artifact_name=artifact.name, version=postgres_bolt.version
        ),
    )


@pytest.fixture(scope="session")
def environment() -> Environment:
    return Environment(name="test", title="Test Environment", tier=EnvironmentTier.DEVELOPMENT)


@pytest.fixture(scope="session")
def execution_parameters() -> ExecutionParameters:
    return ExecutionParameters(
        initial=DefaultExecutionParameters(
            compute=ComputeExecutionParameters(max_memory=1.0, min_cpu=0.25, min_memory=0.1),
            external_service=ExternalizedServiceParameters(host="test.ballista.build"),
            scaling=ScalingExecutionParameters(),
            volume=VolumeExecutionParameters(max_capacity=1.0, path="/custom/path", type="generic-storage"),
        )
    )
