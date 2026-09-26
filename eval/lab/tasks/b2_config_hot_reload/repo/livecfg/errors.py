from __future__ import annotations


class ConfigError(Exception):
    """Raised when configuration cannot be parsed or fails validation."""

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        super().__init__(message)
        self.problems = list(problems or [])
