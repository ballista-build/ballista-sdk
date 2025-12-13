from typing import Protocol

from ballista_sdk.api.v1 import Bolt as BoltV1

SupportedBolt = BoltV1


class BoltFactory(Protocol):
    def create_bolt(self, project: str, version: str) -> SupportedBolt:
        """Create a new, empty Bolt."""
        ...

    def get_bolt(self, data) -> SupportedBolt:
        """Get a Bolt from some kind of data."""
        ...
