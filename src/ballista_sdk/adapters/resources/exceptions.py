class ResourceProviderException(Exception):
    pass


class ResourceNotFound(ResourceProviderException):
    """Resource not found."""

    pass


class ResourceAlreadyExists(ResourceProviderException):
    """Resource already exists."""

    pass


class ResourceHasDependencies(ResourceProviderException):
    """Resource has dependencies."""

    pass
