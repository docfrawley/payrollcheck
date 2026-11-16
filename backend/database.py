"""The PayrollCheck database: its tables, the views the API reads cases through,
and where it is. backend/seeding.py fills it from data/.

The same tables and queries serve Postgres on Supabase, when DATABASE_URL is set, and
SQLite otherwise, as in the tests.
"""

import os
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Engine,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    inspect,
    select,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

from backend.models import ExceptionStatus

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "payrollcheck"
CONNECTIONS = 4
CONNECTION_WAIT = 120

metadata = MetaData()

# The platform's settings, one row for each change; the newest row is in force.
settings = Table(
    "settings",
    metadata,
    Column("number", Integer, primary_key=True, autoincrement=False),
    Column("objectives", JSON, nullable=False),
    Column("noise", JSON, nullable=False),
    Column("tolerance", JSON, nullable=False),
    Column("spending_limit", Float, nullable=False),
    Column("agents", Integer, nullable=False),
    # The app's today, or none for the real date.
    Column("business_date", Text),
    Column("changed_by", Text),
    Column("changed_at", Text, nullable=False),
)
models_allowed = Table(
    "models_allowed",
    metadata,
    Column("model", Text, primary_key=True),
    Column("position", Integer, nullable=False),
    Column("reasoning_efforts", JSON, nullable=False),
    Column("input_price", Float, nullable=False),
    Column("output_price", Float, nullable=False),
)
reviewers = Table(
    "reviewers",
    metadata,
    Column("reviewer_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("email", Text, nullable=False, unique=True),
)
# The projects each reviewer reviews, which make their scope: every project for the
# compliance manager.
project_reviewers = Table(
    "project_reviewers",
    metadata,
    Column("reviewer_id", Text, ForeignKey("reviewers.reviewer_id"), primary_key=True),
    Column("project_id", Text, ForeignKey("projects.project_id"), primary_key=True),
)
projects = Table(
    "projects",
    metadata,
    Column("project_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("county", Text, nullable=False),
    Column("location", Text, nullable=False),
    Column("public_body", Text, nullable=False),
    Column("contract_no", Text, nullable=False),
    Column("award_date", Text, nullable=False),
    # The held-out world's records, which only its evaluations' copies read.
    Column("held_out", Boolean, nullable=False),
)
subcontractors = Table(
    "subcontractors",
    metadata,
    Column("subcontractor_id", Text, primary_key=True),
    Column("legal_name", Text, nullable=False),
    Column("fein", Text, nullable=False),
    Column("registration_no", Text, nullable=False),
    Column("contact_name", Text, nullable=False),
    Column("contact_email", Text, nullable=False),
    Column("held_out", Boolean, nullable=False),
)
# The subcontractors on each project, with their engagement windows and the number
# of the pair, which a case's id carries.
engagements = Table(
    "engagements",
    metadata,
    Column("project_id", Text, ForeignKey("projects.project_id"), primary_key=True),
    Column(
        "subcontractor_id",
        Text,
        ForeignKey("subcontractors.subcontractor_id"),
        primary_key=True,
    ),
    Column("pair", Integer, nullable=False),
    Column("first_week_ending", Text, nullable=False),
    Column("last_week_ending", Text, nullable=False),
)
workers = Table(
    "workers",
    metadata,
    Column("worker_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column(
        "subcontractor_id",
        Text,
        ForeignKey("subcontractors.subcontractor_id"),
        nullable=False,
    ),
    Column("craft", Text, nullable=False),
    Column("classification", Text, nullable=False),
    Column("held_out", Boolean, nullable=False),
)
cases = Table(
    "cases",
    metadata,
    Column("case_id", Text, primary_key=True),
    Column(
        "subcontractor_id",
        Text,
        ForeignKey("subcontractors.subcontractor_id"),
        nullable=False,
    ),
    Column("project_id", Text, ForeignKey("projects.project_id"), nullable=False),
    Column("week_ending", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("screening_flag", Boolean, nullable=False),
    Column("screening_reason", Text),
    Column("agent_failed", Boolean, nullable=False),
    Column("latest_submission_no", Integer, nullable=False),
    Column("thread_id", Text),
    Column("attempts", Integer, nullable=False),
    Column("evaluation_id", Text, ForeignKey("runs.run_id")),
    Column("copy_of", Text),
    # Who decided a case in the history, and when.
    Column("reviewed_by", Text),
    Column("reviewed_on", Text),
)
# One case for a subcontractor, project and week in the queue; an evaluation's copy
# sits beside its original.
Index(
    "one_case_a_week",
    cases.c.subcontractor_id,
    cases.c.project_id,
    cases.c.week_ending,
    unique=True,
    sqlite_where=cases.c.evaluation_id.is_(None),
    postgresql_where=cases.c.evaluation_id.is_(None),
)
submissions = Table(
    "submissions",
    metadata,
    Column("case_id", Text, ForeignKey("cases.case_id"), primary_key=True),
    Column("submission_no", Integer, primary_key=True, autoincrement=False),
    Column("uploaded_by", Text, nullable=False),
    Column("uploaded_at", Text, nullable=False),
    Column("received_on", Text, nullable=False),
    Column("file_name", Text, nullable=False),
    Column("payroll_no", Integer, nullable=False),
    Column("wage_payment_date", Text, nullable=False),
    Column("certification", JSON, nullable=False),
    Column("lines", JSON, nullable=False),
)
# A check tool's findings for the attempt on a thread, which an exception with a
# shortfall must match.
candidates = Table(
    "candidates",
    metadata,
    Column("candidate_id", Integer, primary_key=True),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False, index=True),
    Column("thread_id", Text, nullable=False),
    Column("submission_no", Integer, nullable=False),
    Column("check", Text, nullable=False),
    Column("rule", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("worker_id", Text),
    Column("line_no", Integer),
    Column("expected", Text, nullable=False),
    Column("actual", Text, nullable=False),
    Column("shortfall_cents", Integer),
    Column("citation", Text, nullable=False),
    Column("dismissed_because", Text),
)
# The checks each attempt ran, whether or not they found anything.
check_runs = Table(
    "check_runs",
    metadata,
    Column("case_id", Text, ForeignKey("cases.case_id"), primary_key=True),
    Column("thread_id", Text, primary_key=True),
    Column("check", Text, primary_key=True),
)
exceptions = Table(
    "exceptions",
    metadata,
    Column("exception_id", Integer, primary_key=True),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False, index=True),
    Column("submission_no", Integer, nullable=False),
    Column("rule", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("worker_id", Text),
    Column("line_no", Integer),
    Column("expected", Text, nullable=False),
    Column("actual", Text, nullable=False),
    Column("shortfall_cents", Integer),
    Column("citation", Text, nullable=False),
    Column("raised_by", Text, nullable=False),
    # What raised it: a check tool's finding, the payroll agent's own judgment, or
    # a reviewer.
    Column("source", Text, nullable=False),
    Column("candidate_id", Integer, ForeignKey("candidates.candidate_id")),
    Column("status", Text, nullable=False),
)
# A reviewer's dismissal, addition or restoring of an exception, never edited or
# deleted, read by date for the improver.
overrides = Table(
    "overrides",
    metadata,
    Column("override_id", Integer, primary_key=True),
    Column(
        "exception_id",
        Integer,
        ForeignKey("exceptions.exception_id"),
        nullable=False,
    ),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False),
    Column("submission_no", Integer, nullable=False),
    Column("kind", Text, nullable=False),
    Column("reviewer_id", Text, ForeignKey("reviewers.reviewer_id"), nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_at", Text, nullable=False, index=True),
)
# Each submission's send-back notice: the agent's draft, if it wrote one, the
# reviewer's edit, both kept, and who sent it and when.
notices = Table(
    "notices",
    metadata,
    Column("case_id", Text, ForeignKey("cases.case_id"), primary_key=True),
    Column("submission_no", Integer, primary_key=True, autoincrement=False),
    Column("draft", Text),
    Column("drafted_by", Text),
    Column("drafted_at", Text),
    Column("edited_text", Text),
    Column("edited_by", Text),
    Column("edited_at", Text),
    Column("sent_by", Text),
    Column("sent_at", Text),
)
# Each notice sent to a subcontractor, one for each submission: no real email is
# sent, and this is the record of it.
outbox = Table(
    "outbox",
    metadata,
    Column("outbox_id", Integer, primary_key=True),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False),
    Column("submission_no", Integer, nullable=False),
    Column("to_address", Text, nullable=False),
    Column("subject", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("sent_by", Text, nullable=False),
    Column("sent_at", Text, nullable=False),
    UniqueConstraint("case_id", "submission_no"),
)
# The labelled sets' cases, out of the queue, with their submissions as the
# generator wrote them, and their labels: the answer key only scoring reads.
labelled_cases = Table(
    "labelled_cases",
    metadata,
    Column("labelled_set", Text, primary_key=True),
    Column("case_id", Text, primary_key=True),
    Column("project_id", Text, nullable=False),
    Column("subcontractor_id", Text, nullable=False),
    Column("week_ending", Text, nullable=False),
    Column("tiny", Boolean, nullable=False),
    Column("submissions", JSON, nullable=False),
    # How many of its submissions it had before anyone reviewed it, which an
    # evaluation's copy holds: a history case's first, and a waiting case's all.
    Column("before_review", Integer, nullable=False),
)
labels = Table(
    "labels",
    metadata,
    Column("label_id", Integer, primary_key=True),
    Column("labelled_set", Text, nullable=False),
    Column("case_id", Text, nullable=False),
    # A rule code, or SCREENING for an expected screening flag.
    Column("rule", Text, nullable=False),
    Column("worker_id", Text),
    Column("line_no", Integer),
    Column("expected_shortfall_cents", Integer),
)
SCREENING = "screening"
steps = Table(
    "steps",
    metadata,
    Column("step_id", Integer, primary_key=True),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False),
    Column("thread_id", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("content", Text, nullable=False),
    # The context files a lookup came from, each with its source.
    Column("sources", JSON, nullable=False),
    Column("created_at", Text, nullable=False),
)
# The improver's rounds, each to the settings, the recipe and the version of the
# payroll agent in force when it started.
rounds = Table(
    "rounds",
    metadata,
    Column("number", Integer, primary_key=True),
    Column("round_id", Text, nullable=False, unique=True),
    Column("thread_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("settings", Integer, ForeignKey("settings.number"), nullable=False),
    Column("recipe", Integer, nullable=False),
    Column("starting_version", Integer, nullable=False),
    # The sets of the first evaluations the starting version still needed.
    Column("first_evaluations", JSON, nullable=False),
    Column("improver_model", Text, nullable=False),
    Column("improver_reasoning_effort", Text, nullable=False),
    Column("started_by", Text, nullable=False),
    Column("started_at", Text, nullable=False),
    Column("finished_at", Text),
    Column("stopped_by", Text),
    Column("stopped_because", Text),
    Column("held_out_before", JSON),
    Column("held_out_after", JSON),
    # When the app last heard of the round's work: as it started the round or
    # recorded a review, or from the agent's heartbeat.
    Column("heard_at", Text),
)
recipes = Table(
    "recipes",
    metadata,
    Column("number", Integer, primary_key=True, autoincrement=False),
    Column("recipe", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("proposed_by", Text, nullable=False),
    Column("round_id", Text, ForeignKey("rounds.round_id")),
    Column("approved_by", Text),
    Column("approved_at", Text),
    Column("created_at", Text, nullable=False),
)
# The improver's proposals, each waiting for a reviewer until it is reviewed.
proposals = Table(
    "proposals",
    metadata,
    Column("proposal_id", Text, primary_key=True),
    Column("round_id", Text, ForeignKey("rounds.round_id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("proposal", JSON, nullable=False),
    Column("proposed_at", Text, nullable=False),
    Column("review", Text),
    Column("reviewed_by", Text),
    Column("reviewed_at", Text),
    Column("rejection_reason", Text),
)
improver_calls = Table(
    "improver_calls",
    metadata,
    Column("improver_call_id", Integer, primary_key=True),
    Column("round_id", Text, ForeignKey("rounds.round_id"), nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost", Float, nullable=False),
    Column("created_at", Text, nullable=False),
)
versions = Table(
    "versions",
    metadata,
    Column("number", Integer, primary_key=True, autoincrement=False),
    Column("instructions", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("reasoning_effort", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("proposed_by", Text, nullable=False),
    # The version this one changes, which was current when it was proposed.
    Column("based_on", Integer, ForeignKey("versions.number")),
    Column("round_id", Text, ForeignKey("rounds.round_id")),
    Column("approved_by", Text),
    Column("approved_at", Text),
    Column("created_at", Text, nullable=False),
    Column("verdict", Text),
    Column("verdict_reason", Text),
    # The check tools' tunable parameters, such as the rounding tolerance.
    Column("parameters", JSON, nullable=False),
)
runs = Table(
    "runs",
    metadata,
    Column("number", Integer, primary_key=True),
    Column("run_id", Text, nullable=False, unique=True),
    Column("kind", Text, nullable=False),
    Column("agents", Integer, nullable=False),
    Column("version", Integer, ForeignKey("versions.number"), nullable=False),
    Column("round_id", Text, ForeignKey("rounds.round_id")),
    Column("model", Text, nullable=False),
    Column("reasoning_effort", Text, nullable=False),
    Column("evaluation_set", Text),
    Column("status", Text, nullable=False),
    Column("started_at", Text, nullable=False),
    Column("finished_at", Text),
    Column("summary", JSON),
    Column("stopped_because", Text),
    # When the app last heard of the run's work: as it created the run, or from
    # the agent's heartbeat.
    Column("heard_at", Text),
)
# One row, which a start of the agent's work updates first in its transaction, so
# two starts at the same moment take turns.
locks = Table(
    "locks",
    metadata,
    Column("name", Text, primary_key=True),
    Column("taken_at", Text),
)
AGENTS_WORK = "the agent's work"
run_cases = Table(
    "run_cases",
    metadata,
    Column("run_id", Text, ForeignKey("runs.run_id"), primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False),
)
model_calls = Table(
    "model_calls",
    metadata,
    Column("model_call_id", Integer, primary_key=True),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False),
    Column("thread_id", Text, nullable=False),
    Column("run_id", Text, ForeignKey("runs.run_id")),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost", Float, nullable=False),
    Column("created_at", Text, nullable=False),
)
work_times = Table(
    "work_times",
    metadata,
    Column("work_time_id", Integer, primary_key=True),
    Column("case_id", Text, ForeignKey("cases.case_id"), nullable=False),
    Column("thread_id", Text, nullable=False),
    Column("run_id", Text, ForeignKey("runs.run_id")),
    Column("started_at", Text, nullable=False),
    Column("seconds", Float, nullable=False),
)


# The Copilot's conversations, each its reviewer's, with how many turns it has, which
# a new turn moves on from n to n + 1 with a conditional update, so a conversation
# takes one message at a time.
conversations = Table(
    "conversations",
    metadata,
    Column("conversation_id", Text, primary_key=True),
    Column("reviewer_id", Text, ForeignKey("reviewers.reviewer_id"), nullable=False),
    Column("title", Text, nullable=False),
    Column("turns", Integer, nullable=False),
    Column("created_at", Text, nullable=False),
)
# Each message to the Copilot and its answer: where the turn stands and how it
# ended.
copilot_turns = Table(
    "copilot_turns",
    metadata,
    Column("turn_id", Text, primary_key=True),
    Column(
        "conversation_id",
        Text,
        ForeignKey("conversations.conversation_id"),
        nullable=False,
    ),
    Column("number", Integer, nullable=False),
    Column("message", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("started_at", Text, nullable=False),
    Column("finished_at", Text),
    Column("answer", Text),
    Column("model_calls", Integer),
    Column("cost", Float),
    Column("failure", Text),
    UniqueConstraint("conversation_id", "number"),
)
# The cards of a turn: each tool the Copilot called, what was asked and what came
# back.
copilot_steps = Table(
    "copilot_steps",
    metadata,
    Column("step_id", Integer, primary_key=True),
    Column(
        "turn_id",
        Text,
        ForeignKey("copilot_turns.turn_id"),
        nullable=False,
        index=True,
    ),
    Column("tool", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("input", Text, nullable=False),
    Column("asked", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("answer", Text),
    Column("reason", Text),
    Column("sources", JSON, nullable=False),
    Column("started_at", Text, nullable=False),
    Column("finished_at", Text),
)


def stamp(moment: datetime) -> str:
    """Write a moment in UTC to the second, as every record has it."""
    return moment.isoformat(timespec="seconds")


def now() -> str:
    """Return the current time in UTC, to the second."""
    return stamp(datetime.now(UTC))


def stamp_precisely(moment: datetime) -> str:
    """Write a moment in UTC to the millisecond, as the Copilot's turns and cards
    have it, since many of them take less than a second."""
    return moment.isoformat(timespec="milliseconds")


def now_precisely() -> str:
    """Return the current time in UTC, to the millisecond."""
    return stamp_precisely(datetime.now(UTC))


def database_url() -> URL:
    """Return Postgres at DATABASE_URL, through psycopg and in our own schema, or
    SQLite at PAYROLLCHECK_DB or payrollcheck.db."""
    if url := os.getenv("DATABASE_URL"):
        postgres = make_url(url).set(drivername="postgresql+psycopg")
        return postgres.update_query_dict({"options": f"-c search_path={SCHEMA}"})
    path = os.getenv("PAYROLLCHECK_DB", str(ROOT / "payrollcheck.db"))
    return URL.create("sqlite", database=path)


def on_postgres(url: URL) -> bool:
    """Say whether a database is Postgres rather than SQLite."""
    return url.get_backend_name() == "postgresql"


def on_lambda() -> bool:
    """Say whether the backend runs on AWS Lambda, which sets this for every
    function."""
    return "AWS_LAMBDA_FUNCTION_NAME" in os.environ


@cache
def engine_for(url: URL, for_lambda: bool) -> Engine:
    """Open a database: on Lambda, Postgres with a connection for each request and
    no prepared statements, for Supabase's transaction pooler, since each copy of
    the function would keep its own pool; elsewhere Postgres with at most
    CONNECTIONS connections, waiting up to CONNECTION_WAIT seconds for one, or
    SQLite with a connection for each request."""
    if on_postgres(url) and for_lambda:
        return create_engine(
            url, poolclass=NullPool, connect_args={"prepare_threshold": None}
        )
    if on_postgres(url):
        return create_engine(
            url,
            pool_size=CONNECTIONS,
            max_overflow=0,
            pool_timeout=CONNECTION_WAIT,
            pool_pre_ping=True,
        )
    return create_engine(url, poolclass=NullPool)


def engine() -> Engine:
    """Return the backend's database."""
    return engine_for(database_url(), on_lambda())


def location(db: Engine) -> str:
    """Say where a database is, for a person to read."""
    if on_postgres(db.url):
        return f"the {SCHEMA} schema on Postgres"
    return Path(str(db.url.database)).name


def is_seeded(db: Engine) -> bool:
    """Say whether the database has its tables."""
    return inspect(db).has_table("cases")


# The open exceptions on each case's latest submission: how many, and the shortfall.
open_on_latest = (
    select(
        exceptions.c.case_id,
        func.count().label("open_exceptions"),
        func.coalesce(func.sum(exceptions.c.shortfall_cents), 0).label("shortfall"),
    )
    .join(cases, cases.c.case_id == exceptions.c.case_id)
    .where(
        exceptions.c.status == ExceptionStatus.OPEN,
        exceptions.c.submission_no == cases.c.latest_submission_no,
    )
    .group_by(exceptions.c.case_id)
    .subquery()
)
# A case as the queue lists it: its row, its subcontractor's and project's names
# and its open exceptions.
case_view = (
    select(
        cases,
        subcontractors.c.legal_name.label("subcontractor_name"),
        projects.c.name.label("project_name"),
        func.coalesce(open_on_latest.c.open_exceptions, 0).label("open_exceptions"),
        func.coalesce(open_on_latest.c.shortfall, 0).label("shortfall_cents"),
    )
    .join(subcontractors, subcontractors.c.subcontractor_id == cases.c.subcontractor_id)
    .join(projects, projects.c.project_id == cases.c.project_id)
    .outerjoin(open_on_latest, open_on_latest.c.case_id == cases.c.case_id)
)
