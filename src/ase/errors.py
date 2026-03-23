"""Shared ASE exception hierarchy.

Keeping one root error type makes CLI and engine layers propagate contextual
failures consistently without depending on framework-specific exceptions.
"""

from __future__ import annotations


class ASEError(Exception):
    """Root of ASE's user-facing and internal error hierarchy."""


class CLIError(ASEError):
    """Raised when a CLI workflow cannot be completed as requested."""


class ConfigError(ASEError):
    """Raised when ASE configuration or environment loading fails."""


class AdapterError(ASEError):
    """Raised when adapter SDKs cannot emit or persist framework events."""


class AdapterProtocolError(ASEError):
    """Raised when adapter event streams are missing or malformed."""


class RuntimeModeError(ASEError):
    """Raised when direct runtime execution cannot produce a valid trace."""


class TraceSerializationError(ASEError):
    """Raised when native ASE traces cannot be parsed or written safely."""


class TraceError(ASEError):
    """Raised when trace construction or mutation violates ASE invariants."""


class TraceSchemaMigrationError(ASEError):
    """Raised when a stored trace cannot be interpreted by this schema version."""


class ConformanceError(ASEError):
    """Raised when certification inputs or outputs violate ASE contracts."""


class EvaluatorNotFoundError(ASEError):
    """Raised when a scenario references an unknown evaluator."""


class CacheError(ASEError):
    """Raised when the content-addressed response cache cannot be maintained."""


class OTelImportError(ASEError):
    """Raised when OTEL-like trace input cannot be converted into ASE format."""
