"""Versioned routing API with the concurrently published v1 imports preserved.

New integrations use the v2 catalog and explicit v2 functions. The compatibility
API uses config/compat/model-routing-v1.json; neither version dispatches workers.
"""
from .routing_v2 import (eligible_routes, request_parts, resolve_advice, effort_options,
                         ROLES, METHODS)
from .routing_v2 import validate_catalog as _validate_catalog_v2
from .routing_compat import (Boundary, Capability, Task, RoutePlan, EffortLease,
    accept_effort, compile_effort, compile_route, eligible, lease_valid, quota_delta,
    resolve_route, digest, MENUS, BANDS, REVIEWERS, TRANSPORTS)
from .routing_compat import validate_catalog as _validate_catalog_v1


def validate_catalog(catalog: dict) -> None:
    """Validate the declared version, never silently translate model or auth policy."""
    if type(catalog.get('schema_version')) is int and catalog['schema_version'] == 1:
        return _validate_catalog_v1(catalog)
    return _validate_catalog_v2(catalog)
