"""awavatar — Aither World Avatar.

The contracts of a character factory, and a thin client for one.
"""

__version__ = "0.0.1"

from .schemas import (  # noqa: F401
    RATING_ORDER,
    SchemaError,
    validate_character_spec,
    validate_companion_state,
    validate_scene_spec,
    validate_tf_event,
    validate_world_spec,
)
