"""The payroll agent's own API document: the OpenAPI document of the seven operations
its route calls, which the Gateway turns into tools."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute, iter_route_contexts

# Where the app serves the document, for the Gateway's target to be made from.
PATH = "/api/agent/openapi.json"
OPERATIONS = {
    "get_case",
    "get_project",
    "list_subcontractors",
    "get_payroll_history",
    "record_check_findings",
    "record_screening_flag",
    "record_exception_report",
}


def document(app: FastAPI) -> dict[str, Any]:
    """Build the document of the payroll agent's operations from the app's own routes,
    with no servers, which the deployment adds, and no security schemes, which a
    Gateway's OpenAPI target doesn't support: its credential provider sends the
    key instead."""
    routes = [
        context
        for context in iter_route_contexts(app.routes)
        if isinstance(context.route, APIRoute)
        and context.route.operation_id in OPERATIONS
    ]
    agents = get_openapi(
        title=f"{app.title} payroll agent", version=app.version, routes=routes
    )
    del agents["components"]["securitySchemes"]
    for operations in agents["paths"].values():
        for operation in operations.values():
            del operation["security"]
    return agents
