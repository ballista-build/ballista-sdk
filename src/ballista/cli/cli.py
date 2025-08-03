import os.path
from enum import StrEnum
from typing import Annotated

import prettytable
import typer
import yaml
from pydantic import BaseModel

from ballista.adapters.docker_compose import DockerComposeExecutionEnvironmentAdapter

# from ballista.adapters.kubernetes import KubernetesExecutionEnvironmentAdapter
from ballista.adapters.types import EnvironmentExecutionAdapter, EnvironmentWithExecutionAdapter
from ballista.bolts import v1_service
from ballista.types import Bolt, Environment, EnvironmentArtifactExecutionParameters


class LocalEnvironment(BaseModel):
    hostname: str
    id: str
    name: str


class LocalEnvironmentArtifactExecutionResources(BaseModel):
    max_cpu: float | None = None
    max_memory: float | None = None
    min_cpu: float | None = None
    min_memory: float | None = None


class LocalEnvironmentArtifactExecutionScaling(BaseModel):
    max_replicas: int | None = None
    min_replicas: int | None = None


class LocalEnvironmentArtifactExecutionVolume(BaseModel):
    max_capacity: float | None = None
    min_capacity: float | None = None
    path: str | None = None
    type: str | None = None


class LocalEnvironmentArtifactExecutionParameters(BaseModel):
    resources: LocalEnvironmentArtifactExecutionResources
    scaling: LocalEnvironmentArtifactExecutionScaling
    volumes: dict[str, LocalEnvironmentArtifactExecutionVolume]


def get_local_bolt(origin: str, environment: Environment, adapter: EnvironmentExecutionAdapter) -> Bolt:
    """Get a Bolt from local path."""
    filename = "./ballista.yaml" if os.path.isfile("./ballista.yaml") else None
    if not filename:
        raise ValueError("NO BALLISTA.YAML")

    with open(filename, "r") as f:
        ballista_yaml = yaml.load(f, Loader=yaml.Loader)

    if ballista_yaml is None:
        raise ValueError()

    api_version = ballista_yaml.get("api_version")
    bolt_service = None

    if api_version == "v1":
        bolt_service = v1_service.BoltService(adapter.list_resources(environment))

    if bolt_service:
        return bolt_service.get_bolt(ballista_yaml)

    raise ValueError()


def get_local_environment() -> tuple[EnvironmentExecutionAdapter, Environment, EnvironmentArtifactExecutionParameters]:
    # Create ephemeral DockerCompose environment for local development
    adapter = DockerComposeExecutionEnvironmentAdapter()
    # adapter = KubernetesExecutionEnvironmentAdapter()

    environment = LocalEnvironment(hostname="localhost", id="local", name="Local")

    # TODO: Need a mechanism to get defaults for these
    execution_parameters = LocalEnvironmentArtifactExecutionParameters(
        resources=LocalEnvironmentArtifactExecutionResources(),
        scaling=LocalEnvironmentArtifactExecutionScaling(),
        volumes={},
    )

    return adapter, environment, execution_parameters


def get_origin() -> str:
    """Get the Ballista origin."""
    return "http://localhost:8000"


cli = typer.Typer()


@cli.command(short_help="initialize a new ballista powered project")
def init(project: Annotated[str, typer.Argument(help="Name of new project.")]):
    # TODO: Need to pick an api, so just use v1 for now. We'll probably want a default version with compatibility for old ones up to a certain date.
    adapter, environment, _ = get_local_environment()

    if True:
        resources = adapter.list_resources(environment)
        bolt_service = v1_service.BoltService(resources)

    # Check if that project (folder) already exists
    if os.path.exists(project):
        raise ValueError(f'Path "{project}" already exists.')

    os.makedirs(project)
    new_bolt = bolt_service.create_bolt(project_id=project)
    with open(os.path.join(project, "ballista.yaml"), "w") as f:
        yaml.dump(new_bolt.to_dict(), f)


@cli.command(
    short_help="Build artifacts defined in ballista.yaml",
    help="""Build a path containing a ballista.yaml into a Launch-able Bolt.

Defined artifacts contained in a ballista.yaml will be built and ready to be Launched.
""",
)
def build(
    artifacts: Annotated[list[str] | None, typer.Argument(help="List of artifacts to buid.")] = None,
    artifact_types: Annotated[list[str] | None, typer.Option(help="List of specified Artifact Types to build.")] = None,
):
    origin = get_origin()
    adapter, environment, _ = get_local_environment()
    ballista_bolt = get_local_bolt(origin, environment, adapter)

    for artifact in ballista_bolt.artifacts:
        if not (build := artifact.build):
            # Artifact is not buildable; skip
            continue

        artifact_id = artifact.id
        if artifacts and artifact_id not in artifacts:
            continue

        image_name = f"{ballista_bolt.project_id}_{artifact_id}:{ballista_bolt.version}"

        path = "."
        dockerfile = build.dockerfile or "Dockerfile"
        # Process possible path for the Dockerfile
        dockerfile_pieces = dockerfile.rsplit("/", 2)
        if len(dockerfile_pieces) > 1:
            path, dockerfile = dockerfile_pieces

        # TODO: Auth to registries
        # TODO: Get cache setup from ballista instance
        # cache_from = ""
        # cache_to = []
        cmd = f"docker build {path} -t {image_name} -f {dockerfile} --target {build.dockerfile_target}"
        os.system(cmd)


@cli.command(short_help="start ballista environment")
def up():
    origin = get_origin()
    adapter, environment, execution_parameters = get_local_environment()
    ballista_bolt = get_local_bolt(origin, environment, adapter)

    executable_artifacts = [a for a in ballista_bolt.artifacts if a.execution]
    adapter.deploy(
        bolt=ballista_bolt,
        artifacts=executable_artifacts,
        environment=environment,
        execution_parameters=execution_parameters,
    )


@cli.command(short_help="teardown ballista environment")
def down():
    print("BALLISTA DOWN")


class GenerationTypes(StrEnum):
    LAUNCH = "launch"
    SETTINGS = "settings"


@cli.command(short_help="generate files from ballista dependencies")
def generate(type: GenerationTypes):
    print("GENERATE")


@cli.command(short_help="launch")
def launch(launch_target_url: str):
    origin = get_origin()
    adapter, environment, _ = get_local_environment()
    bolt = get_local_bolt(origin, environment, adapter)


class ListTypes(StrEnum):
    artifact_types = "artifact_types"
    executable_artifacts = "executable_artifacts"
    resources = "resources"


@cli.command(name="list", short_help="list available stuff from environments")
def list_items(type: ListTypes, environment: str | None = None, verbose: bool = False):
    environments: list[EnvironmentWithExecutionAdapter] = []

    # TODO: Add remote environments
    # environments.append((RemoteEnvironmentExecutionAdapter(), remote_environment))

    # Add local environment to list of environments to check
    local = get_local_environment()
    environments.append((local[0], local[1]))

    if environment:
        environments = [e for e in environments if e[1].id == environment]
    if not environments:
        print(f'Unknown environment "{environment}".')
        typer.Exit(1)

    table = prettytable.PrettyTable()
    table.align = "l"
    match type:
        case type.artifact_types:
            table.field_names = ["Artifact Type", "Configs"]

            for adapter, environment in environments:
                for artifact_type in adapter.list_artifact_types(environment):
                    table.add_row([f"{artifact_type.name} ({artifact_type.id})", "NYI"], divider=True)

        case type.executable_artifacts:
            table.field_names = ["Artifact", "Project"]

            for adapter, environment in environments:
                for artifact, artifact_version, project_id in adapter.list_executable_artifacts(environment):
                    table.add_row([f"{artifact.id} v{artifact_version}", project_id])

        case type.resources:
            table.field_names = ["Resource", "Configs", "Secrets", "Requirements"]

            for adapter, environment in environments:
                for resource, _ in adapter.list_resources(environment):
                    configs = None
                    if resource.configs:
                        configs = prettytable.PrettyTable(align="l")
                        configs.set_style(prettytable.TableStyle.PLAIN_COLUMNS)
                        configs.header = False
                        if verbose:
                            configs.add_rows(
                                [[f"{c.name} ({c.id})", c.description, c.shared] for c in resource.configs]
                            )
                        else:
                            configs.add_rows([[f"{c.name} ({c.id})"] for c in resource.configs])

                    secrets = None
                    if resource.secrets:
                        secrets = prettytable.PrettyTable(align="l")
                        secrets.set_style(prettytable.TableStyle.PLAIN_COLUMNS)
                        secrets.header = False
                        if verbose:
                            secrets.add_rows(
                                [[f"{s.name} ({s.id})", s.description, s.shared] for s in resource.secrets]
                            )
                        else:
                            secrets.add_rows([[f"{s.name} ({s.id})"] for s in resource.secrets])
                    requirements = None
                    if resource.requirements:
                        requirements = "NYI"

                    table.add_row(
                        [
                            f"{resource.name} ({resource.id})",
                            configs,
                            secrets,
                            requirements,
                        ],
                        divider=True,
                    )

    print(table.get_string())
