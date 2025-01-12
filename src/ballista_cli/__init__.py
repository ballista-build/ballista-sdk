import os.path

import cattrs
import yaml
import typer

from .types import BallistaProject
from .drivers.docker_compose import DockerComposeBallistaEnvironment


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


@cli.command(short_help="launch")
def launch(launch_target_url: str):
    pass
