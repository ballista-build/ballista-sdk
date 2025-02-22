import os.path
from enum import StrEnum

import typer
import yaml

from ballista.bolts import get_ballista_bolt
from ballista.drivers.docker_compose import DockerComposeBallistaEnvironment
from ballista.types import BallistaBolt


def get_local_bolt() -> BallistaBolt:
    """Get a Bolt from the current directory."""
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

    return get_ballista_bolt(ballista_yaml)


cli = typer.Typer()


@cli.command(short_help="initialize a new ballista powered project")
def init():
    pass


@cli.command(short_help="start ballista environment")
def up():
    ballista_bolt = get_local_bolt()

    driver = DockerComposeBallistaEnvironment()
    driver.start(ballista_bolt)


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
