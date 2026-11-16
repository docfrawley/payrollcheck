"""The shapes of the backend's requests and responses."""

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
)

from backend.rule_codes import Severity


class Status(StrEnum):
    """Where a case stands."""

    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    ACCEPTED = "accepted"
    RETURNED_TO_SUB = "returned_to_sub"


class Role(StrEnum):
    """What a person may do: a reviewer works the cases on their own projects, and
    the compliance manager every project, the improver's rounds and the settings."""

    REVIEWER = "reviewer"
    COMPLIANCE_MANAGER = "compliance_manager"


class ExceptionSource(StrEnum):
    """What raised an exception: a check tool's finding, the payroll agent's own
    judgment with no check behind it, or a reviewer."""

    CHECK = "check"
    AGENT = "agent"
    REVIEWER = "reviewer"


class ExceptionStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


class OverrideKind(StrEnum):
    """A reviewer's correction of an exception report: an exception dismissed, one
    added, or a dismissal undone."""

    DISMISSED = "dismissed"
    ADDED = "added"
    RESTORED = "restored"


class RunKind(StrEnum):
    DISPATCH = "dispatch"
    EVALUATION = "evaluation"


class RunStatus(StrEnum):
    RUNNING = "running"
    FINISHED = "finished"
    STOPPED = "stopped"


class LabelledSet(StrEnum):
    """The sets of labelled cases: the development set and the held-out set."""

    DEVELOPMENT = "development"
    HELD_OUT = "held_out"


class EvaluationSet(StrEnum):
    """What an evaluation can work: a labelled set whole, or the development set's
    tiny cases."""

    DEVELOPMENT = "development"
    HELD_OUT = "held_out"
    TINY = "tiny"


# The labelled set each kind of evaluation copies its cases from.
LABELLED_SET = {
    EvaluationSet.DEVELOPMENT: LabelledSet.DEVELOPMENT,
    EvaluationSet.TINY: LabelledSet.DEVELOPMENT,
    EvaluationSet.HELD_OUT: LabelledSet.HELD_OUT,
}


class Verdict(StrEnum):
    """Whether the business's rule kept a version of the payroll agent."""

    KEPT = "kept"
    ROLLED_BACK = "rolled_back"


class VersionStatus(StrEnum):
    """Where a version of the payroll agent stands."""

    CURRENT = "current"
    KEPT = "kept"
    ROLLED_BACK = "rolled_back"
    UNDER_TEST = "under_test"


class Letter(StrEnum):
    """The judge's levels, from different grounds to better expressed."""

    F = "F"
    C = "C"
    B = "B"
    A = "A"


class RoundStatus(StrEnum):
    OPEN = "open"
    FINISHED = "finished"
    STOPPED = "stopped"


class RoundStage(StrEnum):
    """Where an open round has got to, which the backend works out from its
    records."""

    FIRST_EVALUATIONS = "first_evaluations"
    IMPROVING = "improving"
    CHANGE_WAITING = "change_waiting"
    EVALUATING = "evaluating"
    VERDICT = "verdict"
    RECIPE_WAITING = "recipe_waiting"


class ProposalKind(StrEnum):
    CHANGE = "change"
    RECIPE = "recipe"


class Review(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class DiffLineKind(StrEnum):
    CONTEXT = "context"
    ADDED = "added"
    REMOVED = "removed"


# A model at its own default, with no reasoning effort sent. OpenAI's "none" is a
# real level of its own.
NO_REASONING_EFFORT = "default"


# The kinds of step the agent records through record_step.
RecordedStepKind = Literal[
    "screening",
    "tool_call",
    "tool_result",
    "message",
    "lookup",
    "refusal",
]
# A check tool's findings, and an attempt's failure, which the app records itself.
StepKind = RecordedStepKind | Literal["check", "error"]
MOST_AGENTS = 25
Agents = Annotated[
    int, Field(ge=1, le=MOST_AGENTS, description="How many payroll agents work at once")
]
RuleCode = Literal[
    "form.missing_field",
    "form.unsigned",
    "form.project_mismatch",
    "registration.inactive",
    "rate.base_short",
    "rate.fringe_short",
    "overtime.underpaid",
    "arithmetic.hours_total",
    "arithmetic.gross",
    "apprentice.unregistered",
    "apprentice.ratio",
    "timeliness.late",
    "sequence.gap",
    "classification.changed",
    "classification.mismatch",
]
CheckName = Literal[
    "check_form",
    "check_contractor_registration",
    "check_rates",
    "check_overtime",
    "check_arithmetic",
    "check_apprentices",
    "check_timeliness",
    "check_classification",
]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Project(BaseModel):
    project_id: str
    name: str
    county: str
    location: str
    public_body: str
    contract_no: str
    award_date: str


class Engagement(BaseModel):
    """A subcontractor on a project, with its engagement window."""

    subcontractor_id: str
    legal_name: str
    fein: str
    registration_no: str
    first_week_ending: str
    last_week_ending: str


class ProjectInFull(Project):
    subcontractors: list[Engagement]


class Worker(BaseModel):
    worker_id: str
    name: str
    craft: str = Field(description="The established craft")
    classification: str


class Submission(BaseModel):
    """One upload of a payroll into a case, never changed."""

    submission_no: int
    uploaded_by: str
    uploaded_at: str
    received_on: str
    file_name: str
    payroll_no: int
    wage_payment_date: str
    certification: dict[str, Any]
    lines: list[dict[str, Any]]


class FindingRecord(BaseModel):
    """What a check tool found: the rule, where, what was expected and paid, the
    shortfall in cents where money is owed, and what it rests on."""

    rule: RuleCode
    worker_id: str | None
    line_no: int | None
    expected: str
    actual: str
    shortfall_cents: int | None = Field(ge=0)
    citation: str = Field(min_length=1)


class Candidate(FindingRecord):
    candidate_id: int
    check: CheckName
    severity: Severity
    submission_no: int
    dismissed_because: str | None


class ExceptionRecord(BaseModel):
    exception_id: int
    submission_no: int
    rule: str
    severity: Severity
    worker_id: str | None
    line_no: int | None
    expected: str
    actual: str
    shortfall_cents: int | None
    citation: str
    raised_by: str
    source: ExceptionSource
    candidate_id: int | None = Field(description="The check's finding it raises")
    status: ExceptionStatus


class Override(BaseModel):
    """A reviewer's override of an exception, never edited or deleted."""

    override_id: int
    exception_id: int
    submission_no: int
    kind: OverrideKind
    reviewer_id: str
    reviewer_name: str
    reason: str
    created_at: str


class OverrideRequest(BaseModel):
    reason: Text = Field(description="Why, for the log")


class NewException(BaseModel):
    """An exception a reviewer adds: a rule from the catalogue, the worker and line
    for a worker's rule, the shortfall in cents for a rule that carries money, and
    why."""

    rule: RuleCode
    worker_id: str | None
    line_no: int | None
    expected: Text
    actual: Text
    shortfall_cents: int | None
    reason: Text


class RuleEntry(BaseModel):
    """A rule of the catalogue, as the dashboard's form to add an exception offers
    it."""

    rule: RuleCode
    check: CheckName
    severity: Severity
    money: bool
    worker: bool = Field(description="Found on a worker's line, not the payroll")


class Notice(BaseModel):
    """A submission's send-back notice: the agent's draft, if it wrote one, and the
    reviewer's edit, both kept, and who sent it and when."""

    submission_no: int
    draft: str | None
    drafted_by: str | None
    drafted_at: str | None
    edited_text: str | None
    edited_by: str | None
    edited_at: str | None
    sent_by: str | None
    sent_at: str | None


class NoticeRequest(BaseModel):
    text: Text = Field(description="The notice to the subcontractor, as edited")


class OutboxRecord(BaseModel):
    """A notice sent to a subcontractor's payroll contact, with the agent's draft of
    it, if it wrote one."""

    outbox_id: int
    submission_no: int
    to_address: str
    subject: str
    body: str
    sent_by: str
    sent_at: str
    draft: str | None


class CaseSummary(BaseModel):
    case_id: str
    project_id: str
    project_name: str
    subcontractor_id: str
    subcontractor_name: str
    week_ending: str
    status: Status
    screening_flag: bool
    agent_failed: bool
    open_exceptions: int
    shortfall_cents: int = Field(description="Of the open exceptions")


class Case(CaseSummary):
    screening_reason: str | None
    latest_submission_no: int
    thread_id: str | None
    attempts: int
    evaluation_id: str | None
    copy_of: str | None
    reviewed_by: str | None
    reviewed_on: str | None
    submissions: list[Submission] = Field(description="Oldest first")
    workers: list[Worker] = Field(description="Each worker on the latest submission")
    exceptions: list[ExceptionRecord]
    candidates: list[Candidate] = Field(description="The current attempt's")
    checks_run: list[CheckName] = Field(description="By the current attempt")
    notice: Notice | None = Field(description="The latest submission's draft")
    overrides: list[Override] = Field(description="Oldest first")
    sent_notices: list[OutboxRecord] = Field(description="Newest first")


class UploadRequest(BaseModel):
    """A payroll a reviewer uploads on a subcontractor's behalf: the file's name and
    its text."""

    subcontractor_id: Text
    file_name: Text
    content: str = Field(description="The CSV in our template, as text")


class PayrollOfRecord(BaseModel):
    """An earlier week's payroll: the latest submission of its case."""

    case_id: str
    week_ending: str
    submission_no: int
    certification: dict[str, Any]
    lines: list[dict[str, Any]]


class PayrollHistory(BaseModel):
    payrolls: list[PayrollOfRecord] = Field(description="Oldest week first")


class Reviewer(BaseModel):
    reviewer_id: str
    name: str
    role: Role
    email: str


class Source(BaseModel):
    """A context file a lookup's answer came from, and that file's source."""

    file: str
    system: str
    owner: str
    reviewed: str


class Step(BaseModel):
    step_id: int
    thread_id: str
    kind: StepKind
    content: str
    sources: list[Source]
    created_at: str


class MeasureSettings(BaseModel):
    """A setting for each measure the rule compares: the catch rate as a
    difference, cost and time per case as fractions of the old value."""

    catch_rate: float = Field(ge=0)
    cost_per_case: float = Field(ge=0)
    seconds_per_case: float = Field(ge=0)


class Objectives(BaseModel):
    """The floors a new version must meet on the held-out set."""

    catch_rate: float = Field(ge=0, le=1)


class SettingsValues(BaseModel):
    objectives: Objectives
    noise: MeasureSettings
    tolerance: MeasureSettings
    spending_limit: float = Field(gt=0, description="For each round, in US dollars")
    agents: Agents
    business_date: str | None = Field(
        description="The app's today, YYYY-MM-DD, or null for the real date"
    )


class Settings(SettingsValues):
    number: int
    changed_by: str | None
    changed_at: str


class ModelAllowed(BaseModel):
    model: str
    reasoning_efforts: list[str]
    input_price: float = Field(description="US dollars per million input tokens")
    output_price: float = Field(description="US dollars per million output tokens")


class SettingsPage(BaseModel):
    current: Settings
    changes: list[Settings]
    models_allowed: list[ModelAllowed]


class StartRequest(BaseModel):
    thread_id: str = Field(min_length=1)


class StepRequest(BaseModel):
    kind: RecordedStepKind
    content: str = Field(min_length=1)
    sources: list[Source] = Field(
        description="The context files a lookup came from, and none for other steps"
    )


class NewStep(BaseModel):
    """A step the app adds to a case, recorded by the agent or the app itself."""

    kind: StepKind
    content: str
    sources: list[Source]


class CheckFindingsRequest(BaseModel):
    check: CheckName
    findings: list[FindingRecord] = Field(description="Empty when it found nothing")


class ScreeningFlagRequest(BaseModel):
    reason: Text = Field(description="What the screening found, quoting it")


class Dismissal(BaseModel):
    candidate_id: int
    reason: Text = Field(description="Why the finding isn't a breach")


class AddedException(BaseModel):
    """An exception no check found, which may carry no money unless a check's
    finding has the same rule, worker, line and shortfall."""

    rule: RuleCode
    worker_id: str | None
    line_no: int | None
    expected: str
    actual: str
    shortfall_cents: int | None = Field(ge=0)
    citation: Text


class ExceptionReport(BaseModel):
    raised: list[int] = Field(description="The candidates raised as exceptions")
    dismissed: list[Dismissal]
    added: list[AddedException]
    notice: str = Field(description="The draft send-back notice, blank when clean")
    raised_by: Text


class FailureRequest(BaseModel):
    reason: str = Field(min_length=1, description="What went wrong")


class ModelCallRequest(BaseModel):
    run_id: str | None = Field(description="The run the call was made in, or null")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float = Field(ge=0, description="In US dollars, as OpenRouter reports it")


class ModelCall(BaseModel):
    case_id: str
    thread_id: str
    run_id: str | None
    input_tokens: int
    output_tokens: int
    cost: float
    created_at: str


class WorkTimeRequest(BaseModel):
    run_id: str | None = Field(description="The run the work was done in, or null")
    seconds: float = Field(ge=0, description="How long the agent worked on the case")


class WorkTime(BaseModel):
    case_id: str
    thread_id: str
    run_id: str | None
    started_at: str
    seconds: float


class StartDispatchRequest(BaseModel):
    agents: Agents


class RunCasesRequest(BaseModel):
    case_ids: list[str] = Field(description="The cases a dispatch works, in order")


class DispatchSummary(BaseModel):
    """The cases a dispatch worked, as they stand: Awaiting review with exceptions
    or clean, flagged by the screening, failed by the agent, or unfinished."""

    with_exceptions: list[str]
    clean: list[str]
    flagged: list[str]
    agent_failed: list[str]
    unfinished: list[str]


class RunCase(CaseSummary):
    started_at: str | None
    seconds: float
    model_cost: float


class RunDetails(BaseModel):
    run_id: str
    number: int
    kind: RunKind
    agents: int
    version: int
    round_id: str | None
    round_number: int | None = Field(description="The round that ran it, if any")
    model: str
    reasoning_effort: str
    status: RunStatus
    stopped_because: str | None
    started_at: str
    finished_at: str | None
    seconds: float | None
    model_cost: float


class Run(RunDetails):
    evaluation_set: EvaluationSet | None
    summary: DispatchSummary | None
    cases: list[RunCase]


class StartEvaluationRequest(StartDispatchRequest):
    evaluation_set: EvaluationSet


class Measures(BaseModel):
    catch_rate: float = Field(description="Exception labels caught, of all")
    caught: int
    labels: int
    false_exceptions: int
    false_per_100: float = Field(description="False exceptions per 100 payrolls")
    shortfall_accuracy: float | None = Field(
        description="Caught money labels with the right shortfall, or null with none"
    )
    screening_caught: int
    screening_expected: int
    model_cost_per_case: float
    seconds_per_case: float
    run_seconds: float | None


class CaseGrade(BaseModel):
    """The judge's grade of an explanation: its score from 0 to 3, the likeliest
    level, and the chances of the same grounds and the same section as the
    reviewer's."""

    score: float
    letter: Letter
    same_grounds: float
    same_section: float
    cost: float


class LabelMatch(BaseModel):
    """A label beside what the agent raised: caught, missed, or caught with the
    wrong shortfall."""

    rule: str
    worker_id: str | None
    line_no: int | None
    expected_shortfall_cents: int | None
    result: Literal["caught", "missed", "shortfall_wrong"]
    shortfall_cents: int | None = Field(description="The exception's, once caught")


class ExceptionMatch(BaseModel):
    exception_id: int
    rule: str
    worker_id: str | None
    line_no: int | None
    shortfall_cents: int | None
    matched: bool


class ScoredCase(RunCase):
    copy_of: str
    labels: list[LabelMatch]
    exceptions: list[ExceptionMatch]
    screening_expected: bool
    screening_found: bool
    misses: int
    false_exceptions: int


class Evaluation(RunDetails):
    evaluation_set: EvaluationSet
    size: int
    measures: Measures


class ScoredEvaluation(Evaluation):
    cases: list[ScoredCase]


class Accepted(BaseModel):
    status: Literal["accepted"] = "accepted"


class ScreeningModel(BaseModel):
    """The model the check for hidden instructions runs on, outside the versions."""

    model: str
    reasoning_effort: str


class PayrollAgentVersion(BaseModel):
    """A version as the payroll agent reads it, with no scores."""

    number: int
    instructions: str
    model: str
    reasoning_effort: str
    parameters: dict[str, Any] = Field(
        description="The check tools' tunable parameters, such as the rounding "
        "tolerance in cents"
    )


class DiffLine(BaseModel):
    kind: DiffLineKind
    text: str


class Diff(BaseModel):
    added: int
    removed: int
    hunks: list[list[DiffLine]]


class VersionScores(BaseModel):
    """A version's scores on each set, from the evaluations rounds ran on it."""

    development: Measures | None
    held_out: Measures | None


class VersionSummary(BaseModel):
    number: int
    status: VersionStatus
    model: str
    reasoning_effort: str
    based_on: int | None
    model_before: str | None
    reasoning_effort_before: str | None
    lines_added: int
    lines_removed: int
    reason: str
    proposed_by: str
    round_id: str | None
    approved_by: str | None
    approved_at: str | None
    created_at: str
    verdict: Verdict | None
    verdict_reason: str | None
    parameters: dict[str, Any]
    scores: VersionScores


class VersionDetails(VersionSummary):
    instructions: str
    diff: Diff | None


class Configuration(BaseModel):
    current: int
    versions: list[VersionSummary]


class NewNumber(BaseModel):
    """The number of a version or a recipe the improver's round made."""

    number: int


class RoundForTheAgent(BaseModel):
    """A round as the agent needs it to work."""

    round_id: str
    number: int
    status: RoundStatus
    thread_id: str
    improver_model: str
    improver_reasoning_effort: str
    instructions: str = Field(description="The improver's, around the recipe")
    models_allowed: list[ModelAllowed]
    first_evaluations: list[EvaluationSet] = Field(
        description="The first evaluations the round needed as it started, in order"
    )
    version_evaluations: list[EvaluationSet] = Field(
        description="The evaluations a version under test gets, in order"
    )


class ChangeProposalRequest(BaseModel):
    instructions: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RecipeProposalRequest(BaseModel):
    recipe: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class Proposal(BaseModel):
    proposal_id: str
    round_id: str
    kind: ProposalKind
    reason: str
    instructions: str | None
    model: str | None
    reasoning_effort: str | None
    recipe: str | None
    proposed_at: str
    review: Review | None
    reviewed_by: str | None
    reviewed_at: str | None
    rejection_reason: str | None


class RejectionRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = (
        Field(description="Why, for the improver to read")
    )


class ImproverCallRequest(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float = Field(ge=0, description="In US dollars, as OpenRouter reports it")


class VerdictScores(BaseModel):
    held_out_before: Measures | None
    held_out_after: Measures | None
    development_after: Measures | None


class VerdictResult(BaseModel):
    version: int
    verdict: Verdict
    reason: str
    current_version: int
    summary: str = Field(description="The verdict in a sentence, for the improver")
    scores: VerdictScores


# What the improver reads.


class CaseResults(BaseModel):
    """A development case the version got wrong: each label it missed or got the
    shortfall of wrong, and each exception that matched no label."""

    case_id: str
    missed: list[LabelMatch]
    false_exceptions: list[ExceptionMatch]
    screening_expected: bool
    screening_found: bool


class EarlierRound(BaseModel):
    round: int
    recipe_version: int
    version: int | None
    model: str | None
    reasoning_effort: str | None
    reason: str | None
    held_out_before: Measures | None
    held_out_after: Measures | None
    verdict: Verdict | None
    why: str | None


class Spending(BaseModel):
    limit: float
    spent: float
    left: float


class ImproverView(BaseModel):
    current_version: PayrollAgentVersion = Field(
        description="Its instructions, model, reasoning effort and parameters"
    )
    scores: VersionScores
    development_set: list[CaseResults] = Field(
        description="The latest development evaluation's cases with a miss or a "
        "false exception"
    )
    earlier_rounds: list[EarlierRound]
    objectives_on_the_held_out_set: Objectives
    noise: MeasureSettings
    tolerance: MeasureSettings
    rule: str
    spending: Spending
    models_allowed: list[ModelAllowed]


# What the Improvement page shows.


class RoundReviewView(BaseModel):
    """Who approved or rejected one of the improver's proposals, and when."""

    kind: ProposalKind
    review: Review
    reviewed_by: str
    reviewed_at: str
    rejection_reason: str | None


class WaitingProposal(BaseModel):
    proposal_id: str
    kind: ProposalKind
    reason: str
    proposed_at: str
    diff: Diff
    model_before: str | None
    reasoning_effort_before: str | None
    model_after: str | None
    reasoning_effort_after: str | None


class RoundSummary(BaseModel):
    round_id: str
    number: int
    status: RoundStatus
    stage: RoundStage | None
    progress: str | None = Field(description="Such as 2 of 3, or null")
    started_by: str
    started_at: str
    finished_at: str | None
    stopped_by: str | None
    stopped_because: str | None
    recipe: int
    settings: int
    spending_limit: float
    cost: float
    version: int | None
    model: str | None
    reasoning_effort: str | None
    reason: str | None
    verdict: Verdict | None
    verdict_reason: str | None
    held_out_before: Measures | None
    held_out_after: Measures | None
    reviews: list[RoundReviewView]


class RoundView(RoundSummary):
    waiting: WaitingProposal | None
    evaluations: list[Evaluation]


class VersionPoint(BaseModel):
    """A version's held-out catch rate, for the chart."""

    number: int
    verdict: Verdict | None
    catch_rate: float | None


class RecipeSummary(BaseModel):
    number: int
    current: bool
    reason: str
    proposed_by: str
    round_id: str | None
    approved_by: str | None
    approved_at: str | None
    created_at: str
    lines_added: int
    lines_removed: int


class RecipeDetails(RecipeSummary):
    recipe: str
    diff: Diff | None


class Improvement(BaseModel):
    round: RoundView | None = Field(description="The open round, or the newest")
    rounds: list[RoundSummary]
    first_version: VersionPoint
    versions_tried: list[VersionPoint]
    recipes: list[RecipeSummary]


# The Copilot's conversations and what the Copilot records of them.

MESSAGE_LENGTH = 4000
Message = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_LENGTH),
]


class TurnStatus(StrEnum):
    """Where one of the Copilot's turns stands. A turn reads as stopped when it has
    been working too long; it is never recorded as stopped."""

    WORKING = "working"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"


class CardKind(StrEnum):
    """What a card's tool does: looks up cases, subcontractors and policies or the
    context layer, works with the agent's work or the memory, or acts."""

    CASES = "cases"
    SUBCONTRACTORS = "subcontractors"
    CONTEXT = "context"
    WORK = "work"
    MEMORY = "memory"
    ACTION = "action"


class CardStatus(StrEnum):
    WORKING = "working"
    DONE = "done"
    REFUSED = "refused"
    FAILED = "failed"


class MessageRequest(BaseModel):
    message: Message = Field(description="The reviewer's message to the Copilot")


class CopilotStep(BaseModel):
    """A card: one tool the Copilot called, what was asked and what came back."""

    step_id: int
    tool: str
    kind: CardKind
    input: str = Field(description="The tool's main input, such as CLM-1012")
    asked: str
    status: CardStatus
    answer: str | None
    reason: str | None
    sources: list[Source]
    started_at: str
    finished_at: str | None
    seconds: float = Field(description="So far, while it works")


class CopilotTurn(BaseModel):
    turn_id: str
    number: int
    message: str
    status: TurnStatus
    started_at: str
    finished_at: str | None
    seconds: float | None = Field(description="Once it has finished")
    answer: str | None
    model_calls: int | None
    cost: float | None
    failure: str | None
    steps: list[CopilotStep]


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str = Field(description="The first message")
    created_at: str


class Conversation(ConversationSummary):
    turns: list[CopilotTurn]


class CopilotModel(BaseModel):
    """The model the Copilot runs on."""

    model: str
    reasoning_effort: str


class CopilotStepRequest(BaseModel):
    tool: str = Field(min_length=1)
    kind: CardKind
    input: str = Field(description="The tool's main input, or nothing")
    asked: str = Field(description="What the tool was asked")


class CopilotStepResult(BaseModel):
    status: Literal[CardStatus.DONE, CardStatus.REFUSED, CardStatus.FAILED]
    answer: str | None = Field(description="What came back, or null")
    reason: str | None = Field(description="Why it was refused or failed, or null")
    sources: list[Source] = Field(
        description="The context files an answer came from, and none otherwise"
    )


class TurnFinishRequest(BaseModel):
    answer: str = Field(min_length=1)
    model_calls: int = Field(ge=0)
    cost: float = Field(ge=0, description="In US dollars, as OpenRouter reports it")


class TurnFailureRequest(BaseModel):
    reason: str = Field(min_length=1, description="What went wrong")


# Subcontractors, as the Copilot finds them.


class SubcontractorMatch(BaseModel):
    subcontractor_id: str
    legal_name: str


class Subcontractor(SubcontractorMatch):
    """A subcontractor's record, its projects with their engagement windows, and
    its cases in the queue."""

    fein: str
    registration_no: str
    projects: list[Project]
    cases: list[CaseSummary]


class RunStarted(Accepted):
    """A dispatch or an evaluation a reviewer started, which the agent works."""

    run_id: str
    number: int
