import os.path
from enum import StrEnum

import cattrs
import typer
import yaml

from .drivers.docker_compose import DockerComposeBallistaEnvironment
from .types import BallistaProject


def _get_ballista_project() -> BallistaProject:
    filename = (
        "ballista.yaml"
        if os.path.isfile("ballista.yaml")
        else "ballista.yml"
        if os.path.isfile("ballista.yml")
        else None
    )
    if not filename:
        raise ValueError("NO BALLISTA.YAML")

    with open(filename, "r") as f:
        ballista_yaml = yaml.load(f, Loader=yaml.Loader)

    # TODO: Validate YAML with a JSON-Schema from ???

    return cattrs.structure(ballista_yaml, BallistaProject)


cli = typer.Typer()


@cli.command(short_help="initialize a new ballista powered project")
def init():
    pass


@cli.command(short_help="start ballista environment")
def up():
    ballista_project = _get_ballista_project()

    print(ballista_project)

    driver = DockerComposeBallistaEnvironment()
    driver.start(ballista_project)


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
    pass
