from typing import Any

from .api.v1alpha.models import BoltInput as v1alphaBolt
from .types import BallistaBolt


def get_ballista_bolt(bolt_data: dict[str, Any]) -> BallistaBolt:
    """Get a BallistaBolt from a piece of possibly correct bolt data."""
    api_version = bolt_data.get("api_version")
    if api_version == "v1alpha" and (bolt := v1alphaBolt.from_dict(bolt_data)):
        return bolt

    raise ValueError("Invalid Bolt data")
