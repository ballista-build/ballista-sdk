import pytest
import yaml

from ballista_sdk.adapters.infrastructure import ArtifactReference, ResolvedProvidedResource
from ballista_sdk.api.v1 import (
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
                    alive:
                        http:
                            path: "/healthz"
                            service: "http"
                    ready:
                        http:
                            path: "/healthz"
                            service: "http"
                    started:
                        http:
                            path: "/healthz"
                            service: "http"
                services:
                  - name: "http"
                    http: 80
            requires:
                configs:
                      - name: "option-a"
                        type: "string"
                resources:
                      - postgres:
                            database:
                                name: "testdatabase"
                                name-alias: "ALIASED_DATABASE"
                                host-alias: "RENAMED_HOST"
                                port-alias: "OTHER_PORT"
                                secure-alias: "RETITLED_SECURE"
                secrets:
                      - name: "secret-a"
                        type: "string"
                volumes:
                      - name: "volume-a"
                        capacity: 0.01
                        path: "/var/volume-a"
                        persistent: True
                        title: "Volume A"
        type:
            docker_image:
                image: "hello-world:latest"
project: "simple"
version: "1"
""",
    "small-app": """
api_version: v1
artifacts:
      - name: backend
        execution:
            provides:
                services:
                  - name: "api"
                    http: 8000
        type:
            docker_image:
                image: "hello-world:latest"
      - name: ui
        execution:
            provides:
                services:
                  - name: "http"
                    http: 80
            requires:
                services:
                  - small-app:
                        backend:
                            api:
                                host-alias: ALIASED_HOST
                                port-alias: ALIASED_PORT
                                secure-alias: ALIASED_SECURE
        type:
            docker_image:
                image: "hello-world:latest"
project: small-app
version: "1.2.3"
""",
    #     "typical": """
    # YAML
    # """,
    "resource-provider": """
api_version: "v1"
artifacts:
      - name: "resource"
        execution:
            provides:
                resources:
                  - configs:
                      - name: "test-string"
                        description: "Test string config."
                        title: "Test String"
                        type: "string"
                    description: "Resource Description"
                    instance_id_fields: ["name"]
                    linked:
                        configs:
                          - "test-uint32"
                        secrets:
                          - "test-bool"
                        services:
                          - postgres:
                                server: "postgres"
                    name: "resource"
                    prefix: "RESOURCE"
                    requirements:
                        properties:
                            name:
                                type: string
                        required: ["name"]
                    secrets:
                      - name: "name"
                        description: "Name of resource"
                        title: "Name"
                        type: "string"
                    title: "Resource Provider Resource"
                    transport:
                        rest:
                            path: "/resources"
                            service: "rest"
                services:
                  - name: "rest"
                    http: 8000
            requires:
                configs:
                  - name: "test-uint32"
                    description: "Test unsigned int and linked config."
                    title: "Test Number"
                    type: "uint32"
                secrets:
                  - name: "test-bool"
                    description: "Test bool and linked secret."
                    title: "Test Bool"
                    type: "bool"
                services:
                  - postgres:
                        server: postgres
        type:
            docker_image:
                image: "hello-world:latest"
      - name: "dependent"
        execution:
            requires:
                resources:
                  - resource-provider:
                        resource:
                            name: "mine"
                            name_alias: DIFFERENT_NAME
                            host_alias: DIFFERENT_HOST
                            port_alias: DIFFERENT_PORT
                            secure_alias: DIFFERENT_SECURE
        type:
            docker_image:
                image: "hello-world:latest"
project: "resource-provider"
version: "1"
    """,
}


@pytest.fixture(scope="session", params=["simple", "small-app", "resource-provider"])
def bolt_yaml(request) -> dict[str, str | dict]:
    return yaml.safe_load(TEST_BOLTS[request.param])


@pytest.fixture(scope="session")
def artifact_reference() -> ArtifactReference:
    return ArtifactReference(project_name="simple", artifact_name="api", version="1")


@pytest.fixture(scope="session")
def resolved_provided_resource(postgres_bolt: Bolt) -> ResolvedProvidedResource:
    artifact = postgres_bolt.artifacts[1]

    return ResolvedProvidedResource(
        artifact.execution.provides.resources[0],
        ArtifactReference(
            project_name=postgres_bolt.project, artifact_name=artifact.name, version=postgres_bolt.version
        ),
    )


@pytest.fixture(scope="session")
def environment() -> Environment:
    return Environment(name="test", tier=EnvironmentTier.DEVELOPMENT, title="Test Environment")


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
