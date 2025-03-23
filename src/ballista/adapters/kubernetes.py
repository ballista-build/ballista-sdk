from typing import Any

from ballista.adapters.types import ExecutionEnvironment, ExecutionEnvironmentAdapter
from ballista.types import BallistaArtifact


class KubernetesExecutionEnvironmentAdapter(ExecutionEnvironmentAdapter):
    def deploy_artifact(self, environment: ExecutionEnvironment, artifact: BallistaArtifact):
        # generate yaml for artifact
        pass

    def _make_yaml(self, environment: ExecutionEnvironment, artifact: BallistaArtifact) -> dict[str, Any]:
        d = {}

        return d


class ArgoCDGitOpsKubernetesExecutionEnvironmentAdapter(KubernetesExecutionEnvironmentAdapter):
    pass
