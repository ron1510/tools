from __future__ import annotations


class MongoMigratorError(Exception):
    """Base error for operator-facing failures."""


class ConfigurationError(MongoMigratorError):
    """Raised when the supplied CLI or YAML configuration is invalid."""


class ConnectionError(MongoMigratorError):
    """Raised when a MongoDB endpoint cannot be reached."""


class PlanningError(MongoMigratorError):
    """Raised when a job cannot be converted into an executable plan."""


class CopySafetyError(MongoMigratorError):
    """Raised when a copy would overwrite target data without explicit approval."""


class CheckpointError(MongoMigratorError):
    """Raised when persisted execution state is invalid."""


class VerificationError(MongoMigratorError):
    """Raised when post-run verification fails."""
