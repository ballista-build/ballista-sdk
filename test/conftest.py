import pytest
import yaml

from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactReference,
    ArtifactTypeRequirement,
    Bolt,
    ComputeExecutionParameters,
    DefaultExecutionParameters,
    Environment,
    EnvironmentTier,
    ExecAction,
    ExecutionParameters,
    ExecutionRequirements,
    ExternalizedServiceParameters,
    HealthcheckProbe,
    HealthcheckRequirements,
    Project,
    Resource,
    ResourceConfig,
    ResourceRequirementSchema,
    ResourceSecret,
    ScalingExecutionParameters,
    SecretRequirement,
    ServiceRequirement,
    SettingDataType,
    VolumeExecutionParameters,
    VolumeRequirement,
)


@pytest.fixture(scope="session")
def project():
    return Project(name="typical", title="Typical Project")


@pytest.fixture(scope="session")
def docker_image_artifact_type_need() -> ArtifactTypeRequirement:
    return ArtifactTypeRequirement.model_validate({"docker_image": {"image": "hello-world:latest"}})


TEST_BOLTS: dict[str, str] = {
    "simple": """
api_version: "v1"
artifacts:
      - name: api
        execution:
            configs:
              - name: "option_a"
                data_type: "string"
            healthchecks:
                ready:
                    http:
                        path: "/healthz"
                        service: "http"
            resources:
              - postgres:
                    database:
                        name: "testdatabase"
            secrets:
              - name: "secret_a"
                data_type: "string"
            services:
              - name: http
                http: 80
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
    "resource_provider": """
api_version: "v1"
artifacts:
      - name: "server"
        execution: {}
        provides:
          - configs:
              - data_type: "string"
                description: "Host of Database server."
                name: "host"
                shared: True
                title: "Host"
              - data_type: "uint32"
                description: "Port Database server listens on."
                name: "port"
                shared: True
                title: "Port"
            description: "Resource Description"
            name: "resource_provider-resource1"
            instance_id_fields: ["name"]
            prefix: "RESOURCE1"
            requirements:
                properties:
                    name:
                        type: string
                required: ["name"]
            secrets:
              - data_type: "string"
                description: "Name of database"
                name: "name"
                shared: False
                title: "Database"
              - data_type: "string"
                description: "Login username to access database"
                name: "username"
                shared: False
                title: "Username"
              - data_type: "string"
                description: "Login password to access database"
                name: "password"
                shared: False
                title: "Password"
            title: "Resource Provider Resource"
        type:
            docker_image:
                image: "hello-world:latest"
project: "resource_provider"
version: "1"
    """,
}


@pytest.fixture(scope="session", params=["simple", "resource_provider"])
def bolt_yaml(request) -> dict[str, str | dict]:
    return yaml.safe_load(TEST_BOLTS[request.param])


@pytest.fixture(scope="session")
def postgres_bolt() -> Bolt:
    # Fake Postgres
    postgres_probe = HealthcheckProbe(exec=ExecAction(commands=["pg_isready -U $POSTGRES_USER"], shell=True))
    postgres = Artifact(
        execution=ExecutionRequirements(
            healthchecks=HealthcheckRequirements(alive=postgres_probe, ready=postgres_probe, started=postgres_probe),
            secrets=[
                SecretRequirement(
                    # alias="POSTGRES_USER",
                    description="Username for the default/root login.",
                    name="root_username",
                    title="Root username",
                    data_type=SettingDataType.STRING,
                ),
                SecretRequirement(
                    # alias="POSTGRES_PASSWORD",
                    description="Password for the default/root login",
                    name="root_password",
                    title="Root Password",
                    data_type=SettingDataType.STRING,
                ),
            ],
            services=[ServiceRequirement(name="postgres", tcp=5432)],
            volumes=[
                VolumeRequirement(
                    capacity=0.1,
                    name="data",
                    path="/var/lib/postgresql/data",
                    persistent=True,
                    title="PostgreSQL Data",
                )
            ],
        ),
        name="server",
        provides=[
            Resource(
                name="database",
                configs=[
                    ResourceConfig(
                        description="Host of Postgres server.",
                        name="host",
                        shared=True,
                        title="Host",
                        data_type=SettingDataType.STRING,
                    ),
                    ResourceConfig(
                        description="Port Postgres server listens on.",
                        name="port",
                        shared=True,
                        title="Port",
                        data_type=SettingDataType.INT32,
                    ),
                ],
                description="Postgres Database",
                instance_id_fields=["name"],
                prefix="POSTGRES",
                requirements=ResourceRequirementSchema.model_validate(
                    {"properties": {"name": {"type": "string"}}, "required": ["name"]}
                ),
                secrets=[
                    ResourceSecret(
                        data_type=SettingDataType.STRING,
                        description="Name of postgres database",
                        name="name",
                        shared=False,
                        title="Database Name",
                    ),
                    ResourceSecret(
                        data_type=SettingDataType.STRING,
                        description="Login username to access database",
                        name="username",
                        shared=False,
                        title="Username",
                    ),
                    ResourceSecret(
                        data_type=SettingDataType.STRING,
                        description="Login password to access database",
                        name="password",
                        shared=False,
                        title="Password",
                    ),
                ],
                title="Postgres Database",
            )
        ],
        type=ArtifactTypeRequirement.model_validate({"docker_image": {"image": "postgres:18.1"}}),
    )

    return Bolt(api_version="v1", artifacts=[postgres], project="postgres", version="18.1.0")


@pytest.fixture(scope="session")
def artifact_reference() -> ArtifactReference:
    return ArtifactReference(project_name="simple", artifact_name="api", version="1")


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
