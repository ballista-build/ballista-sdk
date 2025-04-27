from pydantic import BaseModel


class ArtifactType(BaseModel):
    id: str
    name: str


docker_image = ArtifactType(id="docker_image", name="Docker Image")
python_wheel = ArtifactType(id="python_wheel", name="Python Wheel")
