"""Primitives"""

from typing import Any, NotRequired, TypedDict

METADATA_MANAGED_BY = "Ballista"
METADATA_DOMAIN = "ballista.build"
METADATA_LABEL_ENVIRONMENT = f"{METADATA_DOMAIN}/environment"
METADATA_LABEL_ENVIRONMENT_TIER = f"{METADATA_DOMAIN}/environment-tier"
METADATA_LABEL_RESOURCE = f"{METADATA_DOMAIN}/resource"
METADATA_ANNOTATION_RESOURCE = f"{METADATA_DOMAIN}/resource-json"


KubernetesMetadataLabels = dict[str, str]


class KubernetesMetadata(TypedDict):
    annotations: NotRequired[dict[str, str]]
    labels: KubernetesMetadataLabels
    name: str
    namespace: str


class KubernetesResource(TypedDict):
    apiVersion: str
    kind: str
    metadata: KubernetesMetadata
    spec: NotRequired[dict[str, Any]]
