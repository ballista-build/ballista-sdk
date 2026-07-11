import pytest

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.adapters.resources.transports import RESTResourceProviderTransport
from ballista_sdk.api.v1 import Environment, ProvidedResourceWithArtifactReference


@pytest.mark.unit
def test_resolve_resource_provider_transports(
    environment: Environment,
    infrastructure_adapter: InfrastructureAdapter,
    provided_resource_with_artifact: ProvidedResourceWithArtifactReference,
):
    transport = infrastructure_adapter.resolve_resource_provider_transport(environment, provided_resource_with_artifact)

    assert isinstance(transport, RESTResourceProviderTransport)
