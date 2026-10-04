"""Routing API (v2 catalog). The v1 compatibility layer was removed 2026-09-25."""
from .routing_v2 import (eligible_routes, request_parts, resolve_advice, effort_options,
                         validate_catalog, ROLES, METHODS)
