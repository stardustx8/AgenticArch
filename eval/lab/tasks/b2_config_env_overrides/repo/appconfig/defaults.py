"""Built-in defaults. Treat DEFAULTS as read-only; load_config copies it."""

DEFAULTS = {
    "log_level": "info",
    "workers": 4,
    "db": {
        "host": "localhost",
        "port": 5432,
        "timeout": 2.5,
        "ssl": False,
    },
    "cache": {
        "enabled": True,
        "ttl": 300,
        "backend": "memory",
    },
}
