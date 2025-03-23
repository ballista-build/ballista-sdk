import os.path
from enum import StrEnum
from typing import Annotated

import typer
import yaml

from ballista.adapters.docker_compose import DockerComposeExecutionEnvironmentAdapter
from ballista.adapters.types import ExecutionEnvironment
from ballista.bolts import v1alpha_service
from ballista.types import BallistaBolt


def get_local_bolt(origin: str) -> BallistaBolt:
    """Get a Bolt from local path."""
    filename = "./ballista.yaml" if os.path.isfile("./ballista.yaml") else None
    if not filename:
        raise ValueError("NO BALLISTA.YAML")

    with open(filename, "r") as f:
        ballista_yaml = yaml.load(f, Loader=yaml.Loader)

    api_version = ballista_yaml.get("api_version")
    bolt_service = None
    if api_version == "v1alpha":
        bolt_service = v1alpha_service.BoltService()

    if bolt_service:
        return bolt_service.get_bolt(ballista_yaml)

    raise ValueError()


def get_local_environment() -> ExecutionEnvironment:
    # Create ephemeral DockerCompose environment for local development
    local_adapter = DockerComposeExecutionEnvironmentAdapter()

    env = ExecutionEnvironment(adapter=local_adapter, cluster="local", name="local", namespace="local")

    return env


def get_origin() -> str:
    """Get the Ballista origin."""
    return "http://localhost:8000"


cli = typer.Typer()


@cli.command(short_help="initialize a new ballista powered project")
def init(project: Annotated[str, typer.Argument(help="Name of new project.")]):
    # TODO: Need to pick an api, so just use v1alpha for now. We'll probably want a default version with compatibility for old ones up to a certain date.
    if True:
        bolt_service = v1alpha_service.BoltService()

    # Check if that project (folder) already exists
    if os.path.exists(project):
        raise ValueError(f'Path "{project}" already exists.')

    os.makedirs(project)
    new_bolt = bolt_service.create_bolt(project=project)
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
    ballista_bolt = get_local_bolt(origin)
    version = ballista_bolt.version

    for artifact in ballista_bolt.artifacts:
        if not (dockerfile_stage := artifact.dockerfile_stage):
            # Artifact is not buildable; skip
            continue

        artifact_name = artifact.name
        if artifacts and artifact_name not in artifacts:
            continue

        image_name = f"build_{artifact_name}:{version}"

        path = "."
        dockerfile = artifact.dockerfile or "Dockerfile"
        # Process possible path for the Dockerfile
        dockerfile_pieces = dockerfile.rsplit("/", 2)
        if len(dockerfile_pieces) > 1:
            path, dockerfile = dockerfile_pieces

        # TODO: Get cache setup from ballista instance
        # cache_from = ""
        # cache_to = []
        cmd = f"docker build {path} -t {image_name} -f {dockerfile} --target {dockerfile_stage}"
        print(cmd)
        # os.system(cmd)


@cli.command(short_help="start ballista environment")
def up():
    origin = get_origin()
    ballista_bolt = get_local_bolt(origin)

    env = get_local_environment()


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
    bolt = get_local_bolt(origin)
