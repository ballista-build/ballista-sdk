import pytest

from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactTypeRequirement,
    Bolt,
    ComputeExecutionParameters,
    ConfigRequirement,
    DefaultExecutionParameters,
    Environment,
    EnvironmentTier,
    ExecAction,
    ExecutionParameters,
    ExecutionRequirements,
    ExternalizedServiceParameters,
    HealthcheckProbe,
    HealthcheckRequirements,
    HTTPGETAction,
    Project,
    ProjectResourceRequirement,
    Resource,
    ResourceConfig,
    ResourceRequirement,
    ResourceRequirementParameters,
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


@pytest.fixture(scope="session", params=["simple", "typical", "resource_provider"])
def bolt(
    docker_image_artifact_type_need: ArtifactTypeRequirement,
    postgres_bolt: Bolt,
    request,
) -> Bolt:
    match request.param:
        case "simple":
            # A simple project with one ExecutableArtifact.
            PostgresDatabaseResourceRequirement = (
                postgres_bolt.artifacts[0].provides[0].get_requirements_model("Postgres")
            )

            class ExecutionPostgresResourceNeed(ResourceRequirement):
                database: PostgresDatabaseResourceRequirement

            artifacts = [
                Artifact(
                    build=None,
                    execution=ExecutionRequirements(
                        configs=[ConfigRequirement(name="option_a", data_type=SettingDataType.STRING)],
                        healthchecks=HealthcheckRequirements(
                            ready=HealthcheckProbe(
                                http=HTTPGETAction(path="/healthz", service="http"),
                            ),
                        ),
                        resources=[
                            ProjectResourceRequirement(
                                {
                                    "postgres": ExecutionPostgresResourceNeed.model_validate(
                                        {"database": {"name": "testdatabase"}}
                                    )
                                }
                            )
                        ],
                        secrets=[SecretRequirement(name="secret_a", data_type=SettingDataType.STRING)],
                        services=[ServiceRequirement(http=80, name="http")],
                        volumes=[
                            VolumeRequirement(
                                capacity=0.01, name="volume_a", path="/var/volume_a", persistent=True, title="Volume A"
                            )
                        ],
                    ),
                    name="api",
                    type=docker_image_artifact_type_need,
                )
            ]
            return Bolt(
                api_version="v1",
                artifacts=artifacts,
                project="simple",
                version="1",
            )

        case "typical":
            # A typical project with two artifacts using various dependencies
            artifacts = [
                Artifact(
                    execution=ExecutionRequirements(
                        configs=[ConfigRequirement(name="option_a", data_type=SettingDataType.STRING)],
                        secrets=[SecretRequirement(name="secret_a", data_type=SettingDataType.STRING)],
                        volumes=[
                            VolumeRequirement(
                                capacity=0.01, name="volume_a", path="/var/volume_a", persistent=True, title="Volume A"
                            ),
                            VolumeRequirement(
                                capacity=0.25,
                                name="volume_b",
                                path="/var/volume_b",
                                persistent=False,
                                title="Volume B",
                            ),
                        ],
                    ),
                    name="api",
                    type=docker_image_artifact_type_need,
                ),
                Artifact(name="frontend", type=docker_image_artifact_type_need),
            ]
            return Bolt(
                api_version="v1",
                artifacts=artifacts,
                project="typical",
                version="1",
            )
        case "resource_provider":
            resource = Resource(
                configs=[
                    ResourceConfig(
                        data_type=SettingDataType.STRING,
                        description="Host of Database server.",
                        name="host",
                        shared=True,
                        title="Host",
                    ),
                    ResourceConfig(
                        description="Port Database server listens on.",
                        name="port",
                        shared=True,
                        data_type=SettingDataType.INTEGER,
                        title="Port",
                    ),
                ],
                description="Resource Description",
                name="resource_provider-resource1",
                instance_id_fields=["name"],
                prefix="RESOURCE1",
                requirements=ResourceRequirementParameters(properties={}, required=["name"]),
                secrets=[
                    ResourceSecret(
                        description="Name of database",
                        name="database",
                        shared=False,
                        title="Database",
                        data_type=SettingDataType.STRING,
                    ),
                    ResourceSecret(
                        description="Login username to access database",
                        name="username",
                        shared=False,
                        title="Username",
                        data_type=SettingDataType.STRING,
                    ),
                    ResourceSecret(
                        description="Login password to access database",
                        name="password",
                        shared=False,
                        title="Password",
                        data_type=SettingDataType.STRING,
                    ),
                ],
                title="Resource Provider Resource",
            )

            artifact = Artifact(
                execution=ExecutionRequirements(),
                name="server",
                provides=[resource],
                type=docker_image_artifact_type_need,
            )

            return Bolt(
                api_version="v1",
                artifacts=[artifact],
                project="resource_provider",
                version="1",
            )

        case _:
            raise Exception()


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
                        data_type=SettingDataType.INTEGER,
                    ),
                ],
                description="Postgres Database",
                instance_id_fields=["database"],
                prefix="POSTGRES",
                requirements=ResourceRequirementParameters(properties={}, required=["database"]),
                secrets=[
                    ResourceSecret(
                        data_type=SettingDataType.STRING,
                        description="Name of postgres database",
                        name="database",
                        shared=False,
                        title="Database",
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
