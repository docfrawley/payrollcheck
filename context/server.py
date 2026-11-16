"""The context layer's MCP server: its lookups as read-only tools over streamable
HTTP at /mcp, stateless and answering in JSON, the five on the payroll files.
handler is its entry point on AWS Lambda, behind a
Function URL."""

import datetime
from typing import Any

from mangum import Mangum
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from context import payroll_files

NAME = "payrollcheck-context"
# The port the context layer serves on the laptop, at /mcp.
PORT = 8006
READ_ONLY = ToolAnnotations(readOnlyHint=True)
# A Function URL's host would be refused as a DNS rebinding attack, and the
# Function URL's IAM auth guards the server there.
ON_LAMBDA = TransportSecuritySettings(enable_dns_rebinding_protection=False)


def build_server(security: TransportSecuritySettings | None = None) -> FastMCP:
    """Make the server with its tools, on the laptop's port, with FastMCP's
    protection for a local host unless the security given says otherwise."""
    server = FastMCP(
        NAME,
        port=PORT,
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )
    add_payroll_tools(server)
    return server


def add_payroll_tools(server: FastMCP) -> None:
    """The five lookups on the payroll files."""

    @server.tool(annotations=READ_ONLY)
    def get_wage_rate(
        craft: str,
        classification: str,
        county: str,
        award_date: datetime.date,
        work_date: datetime.date,
    ) -> dict[str, Any]:
        """Get the rate for a day's work: the award-date determination's latest row."""
        return payroll_files.get_wage_rate(
            craft, classification, county, award_date, work_date
        )

    @server.tool(annotations=READ_ONLY)
    def check_registration(registration_no: str, date: datetime.date) -> dict[str, Any]:
        """Check a contractor's public works registration and its status on a date."""
        return payroll_files.check_registration(registration_no, date)

    @server.tool(annotations=READ_ONLY)
    def check_apprentice(worker_id: str, date: datetime.date) -> dict[str, Any]:
        """Check whether a worker is a registered apprentice, and their level then."""
        return payroll_files.check_apprentice(worker_id, date)

    @server.tool(annotations=READ_ONLY)
    def get_filing_rules() -> dict[str, Any]:
        """Get the filing rules: when a payroll is due, its numbering, corrections."""
        return payroll_files.get_filing_rules()

    @server.tool(annotations=READ_ONLY)
    def lookup_payroll_term(term: str) -> dict[str, Any]:
        """Look up a payroll term in the compliance glossary: its definition."""
        return payroll_files.lookup_payroll_term(term)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda's entry point: a fresh server for each request, since Mangum runs
    an app's startup and shutdown around every request and a server's session
    manager runs only once."""
    app = build_server(ON_LAMBDA).streamable_http_app()
    return Mangum(app, lifespan="auto")(event, context)
