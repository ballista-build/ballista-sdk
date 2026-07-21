import pytest

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.adapters.infrastructure import ProvidedResourceWithArtifactReference
from ballista_sdk.adapters.resources.transports import RESTResourceProviderTransport
from ballista_sdk.api.v1 import Environment


@pytest.mark.unit
async def test_resolve_resource_provider_transports(
    environment: Environment,
    infrastructure_adapter: InfrastructureAdapter,
    provided_resource_with_artifact: ProvidedResourceWithArtifactReference,
):
    transport = await infrastructure_adapter.resolve_resource_provider_transport(
        environment, provided_resource_with_artifact
    )

    assert isinstance(transport, RESTResourceProviderTransport)
