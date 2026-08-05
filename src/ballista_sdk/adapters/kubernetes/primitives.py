"""Primitives"""

from typing import Any, NotRequired, TypedDict

# The standard kubernetes app labels
METADATA_APP_DOMAIN = "app.kubernetes.io"
METADATA_LABEL_APP_INSTANCE = f"{METADATA_APP_DOMAIN}/instance"
METADATA_LABEL_APP_MANAGED_BY = f"{METADATA_APP_DOMAIN}/managed-by"
METADATA_LABEL_APP_NAME = f"{METADATA_APP_DOMAIN}/name"
METADATA_LABEL_APP_PART_OF = f"{METADATA_APP_DOMAIN}/part-of"
METADATA_LABEL_APP_VERSION = f"{METADATA_APP_DOMAIN}/version"

METADATA_MANAGED_BY = "Ballista"
# ballista.build labels
METADATA_BALLISTA_DOMAIN = "ballista.build"
METADATA_LABEL_ENVIRONMENT = f"{METADATA_BALLISTA_DOMAIN}/environment"
METADATA_LABEL_ENVIRONMENT_TIER = f"{METADATA_BALLISTA_DOMAIN}/environment-tier"
METADATA_LABEL_RESOURCE = f"{METADATA_BALLISTA_DOMAIN}/resource"
METADATA_LABEL_SERVICE = f"{METADATA_BALLISTA_DOMAIN}/service"

# These are for stuffing JSON into annotations because we're monsters
METADATA_ANNOTATION_DEFAULT_EXECUTION_PARAMETERS = f"{METADATA_BALLISTA_DOMAIN}/default-execution-parameters-json"
METADATA_ANNOTATION_EXTERNALIZED_SERVICE = f"{METADATA_BALLISTA_DOMAIN}/externalized-service-json"
METADATA_ANNOTATION_RESOURCE = f"{METADATA_BALLISTA_DOMAIN}/resource-json"
METADATA_ANNOTATION_SERVICE = f"{METADATA_BALLISTA_DOMAIN}/service-json"


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
