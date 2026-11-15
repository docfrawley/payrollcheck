"""The context layer's MCP server: its lookups as read-only tools over streamable
HTTP at /mcp, stateless and answering in JSON, the seven on the travel files and
the five on the payroll files. handler is its entry point on AWS Lambda, behind a
Function URL."""

import datetime
from typing import Annotated, Any

from mangum import Mangum
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import StringConstraints

from context import files, payroll_files

NAME = "payrollcheck-context"
# The port the context layer serves on the laptop, at /mcp.
PORT = 8006
# A search needs a word or phrase to look for.
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
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

    add_travel_tools(server)
    add_payroll_tools(server)
    return server


def add_travel_tools(server: FastMCP) -> None:
    """The seven lookups on the travel files, which stage 3 removes."""

    @server.tool(annotations=READ_ONLY)
    def lookup_term(term: str) -> dict[str, Any]:
        """Look up a term the policy wording defines: its definition and sections."""
        return files.lookup_term(term)

    @server.tool(annotations=READ_ONLY)
    def describe_fields(record: files.RecordName) -> dict[str, Any]:
        """Describe a record the payroll agent reads and the meaning of its fields."""
        return files.describe_fields(record)

    @server.tool(annotations=READ_ONLY)
    def get_plan(plan: files.PlanName) -> dict[str, Any]:
        """Get a plan's limits, waiting periods, deductible and the add-ons."""
        return files.get_plan(plan)

    @server.tool(annotations=READ_ONLY)
    def get_case_rules() -> dict[str, Any]:
        """Get the rules claims operations applies to every case."""
        return files.get_case_rules()

    @server.tool(annotations=READ_ONLY)
    def search_reference_data(query: Query) -> dict[str, Any]:
        """Find outside facts, such as storms, strikes and prices, with every word."""
        return files.search_reference_data(query)

    @server.tool(annotations=READ_ONLY)
    def search_documents(query: Query) -> dict[str, Any]:
        """Find sections of the wording and the manual containing a word or phrase."""
        return files.search_documents(query)

    @server.tool(annotations=READ_ONLY)
    def read_section(document: files.DocumentName, number: int) -> dict[str, Any]:
        """Read one section of the policy wording or the claims manual in full."""
        return files.read_section(document, number)


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
