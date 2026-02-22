from typing import Any, NotRequired, TypedDict


class KubernetesMetadata(TypedDict):
    annotations: NotRequired[dict[str, str]]
    labels: NotRequired[dict[str, str]]
    name: str
    namespace: str


class KubernetesResource(TypedDict):
    apiVersion: str
    kind: str
    metadata: KubernetesMetadata
    spec: NotRequired[dict[str, Any]]
