from typing import Protocol


class ResourceProviderTransport(Protocol):
    """Transports communication between a Resource Provider and Ballista."""

    pass


class RESTResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via REST API."""

    pass


class GRPCResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via GRPC."""

    pass


class TCPResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via TCP socket."""

    pass


class QueueResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via message queue."""

    pass
