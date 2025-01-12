from dataclasses import dataclass


@dataclass
class TestReportArtifactType:
    format: str
    path: str


@dataclass
class DockerArtifactType:
    pass


@dataclass
class AvailableArtifactTypes:
    docker: DockerArtifactType | None = None
    test_report: list[TestReportArtifactType] | None = None

    def which(self) -> DockerArtifactType | list[TestReportArtifactType] | None:
        if self.docker:
            return self.docker
        elif self.test_report:
            return self.test_report
        else:
            return None


@dataclass
class LocalResources:
    max_cpu_cores: float | None = None
    max_memory_mb: int | None = None
    min_cpu_cores: float | None = None
    min_memory_mb: int | None = None

@dataclass
class ArtifactExecution:
    local_resources: LocalResources | None = None
    platform_resources: list | None = None


@dataclass
class BallistaArtifact:
    name: str
    dockerfile_stage: str
    type: AvailableArtifactTypes
    dockerfile: str | None = None
    execution: ArtifactExecution | None = None


@dataclass
class BallistaProject:
    api_version: str
    artifacts: list[BallistaArtifact]
    name: str
    version: str


@dataclass
class LaunchTarget:
    pass
