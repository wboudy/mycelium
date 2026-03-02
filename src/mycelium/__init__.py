# mycelium package
"""Multi-agent workflow framework for AI-assisted development."""

from mycelium.llm import complete
from mycelium.models import (
    ErrorObject,
    OutputEnvelope,
    WarningObject,
    error_envelope,
    make_envelope,
)

__version__ = "0.2.0"
__all__ = [
    "complete",
    "ErrorObject",
    "OutputEnvelope",
    "WarningObject",
    "error_envelope",
    "make_envelope",
]
