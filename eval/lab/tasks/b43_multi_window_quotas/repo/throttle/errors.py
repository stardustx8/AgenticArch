class ThrottleError(Exception):
    """Base class for rate limiter errors."""


class QuotaError(ThrottleError, ValueError):
    """Raised for invalid quota configuration."""


class UnknownTierError(QuotaError):
    """Raised when a user maps to a tier that was never defined."""
