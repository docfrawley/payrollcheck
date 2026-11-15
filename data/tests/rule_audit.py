"""A reference audit of a submission against every rule, written apart from the
generator on the one rate logic, so the tests can check that each seeded error
breaks its rule and no other, and that everything else breaks none."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from context import wage_rules
from context.payroll_files import DUE_DAYS, RATES
from context.wage_rules import APPRENTICE, JOURNEYMAN, Rate, Work
from data.payroll_world import rules
from data.payroll_world.classifications import classification_of
from data.payroll_world.lifecycle import Case, Submission
from data.payroll_world.template import Line
from data.payroll_world.weeks import week_days
from data.payroll_world.world import Project, World


@dataclass(frozen=True, order=True)
class Finding:
    """A rule a submission breaks, on a worker's line or the whole payroll, with
    the dollars it leaves unpaid in cents where it leaves any."""

    rule: str
    worker_id: str | None = None
    line_no: int | None = None
    shortfall: int | None = None


@dataclass(frozen=True)
class LineAudit:
    """One line as the rules read it: the worker's days, and what each worked day
    requires as the line is classified and as the worker's established craft."""

    line: Line
    line_no: int
    craft: str
    classification: str
    hours: list[tuple[date, Decimal]]
    claimed: dict[date, Rate]
    established: dict[date, Rate]

    def finding(self, rule: str, shortfall: int | None = None) -> Finding:
        return Finding(rule, self.line.worker_id, self.line_no, shortfall)

    @property
    def fringe_paid(self) -> int:
        return self.line.fringe_rate + self.line.fringe_cash


class Audit:
    """The rules, for the cases of one world."""

    def __init__(self, world: World, cases: Sequence[Case]):
        self.world = world
        self.by_week = {(c.filing.engagement.pair, c.filing.week): c for c in cases}

    def previous(self, case: Case) -> Submission | None:
        """The latest submission of the pair's case the week before."""
        before = self.by_week.get((case.filing.engagement.pair, case.filing.week - 1))
        return before.submissions[-1] if before else None

    def findings(self, case: Case, submission: Submission) -> list[Finding]:
        found = self.form(submission) + self.filing(case, submission)
        project = self.world.project(case.filing.engagement.project_id)
        for line_no, line in enumerate(submission.payroll.lines, start=1):
            audit = self.read_line(case, project, line, line_no)
            classified = self.classified(case, audit)
            found += self.arithmetic(audit) + classified
            if not any(f.rule == rules.MISMATCH for f in classified):
                found += self.pay(audit)
        return sorted(found + self.ratio(submission))

    def form(self, submission: Submission) -> list[Finding]:
        cert = submission.payroll.certification
        found = []
        if not all(
            (cert.contractor_name, cert.fein, cert.registration_no, cert.project_id)
        ):
            found.append(Finding(rules.MISSING_FIELD))
        if not cert.signed_by or cert.signed_on is None:
            found.append(Finding(rules.UNSIGNED))
        return found

    def filing(self, case: Case, submission: Submission) -> list[Finding]:
        """Registration on every work date, timeliness and the payroll number, which
        runs from 1 in the first week of the engagement window."""
        cert = submission.payroll.certification
        registration = self.world.registration(case.filing.engagement.subcontractor_id)
        worked = {
            day
            for line in submission.payroll.lines
            for day, hours in zip(week_days(cert.week_ending), line.hours, strict=True)
            if hours
        }
        found = []
        if not all(registration.active_on(day) for day in worked):
            found.append(Finding(rules.INACTIVE))
        if (submission.received_on - cert.wage_payment_date).days > DUE_DAYS:
            found.append(Finding(rules.LATE))
        if cert.payroll_no != case.filing.week - case.filing.engagement.first_week + 1:
            found.append(Finding(rules.GAP))
        return found

    def owed(
        self,
        project: Project,
        worker_id: str,
        craft: str,
        classification: str,
        day: date,
    ) -> Rate:
        """What a day paid as this craft and classification requires: an apprentice
        at their registered level, or the journeyman rate when they aren't
        registered."""
        county, award = project.county, project.award_date
        registration = self.world.apprentice(worker_id)
        level = registration.level_on(day) if registration else None
        if classification == APPRENTICE and level is not None:
            work = Work(craft, APPRENTICE, county, award, level)
        elif classification == APPRENTICE:
            work = Work(craft, JOURNEYMAN, county, award)
        else:
            work = Work(craft, classification, county, award)
        return wage_rules.required_rate(RATES, work, day)

    def read_line(
        self, case: Case, project: Project, line: Line, line_no: int
    ) -> LineAudit:
        worker = self.world.worker(line.worker_id)
        craft, classification = classification_of(line.classification)
        hours = list(zip(week_days(case.filing.week_ending), line.hours, strict=True))
        worked = [day for day, h in hours if h]
        return LineAudit(
            line,
            line_no,
            craft,
            classification,
            hours,
            {
                d: self.owed(project, worker.id, craft, classification, d)
                for d in worked
            },
            {
                d: self.owed(project, worker.id, worker.craft, worker.classification, d)
                for d in worked
            },
        )

    def arithmetic(self, audit: LineAudit) -> list[Finding]:
        line = audit.line
        total = sum(line.hours, Decimal(0))
        found = []
        if total != line.total_hours:
            found.append(audit.finding(rules.HOURS_TOTAL))
        expected = wage_rules.gross(line.base_rate, total, line.overtime_hours)
        if line.gross != expected:
            short = max(0, expected - line.gross) or None
            found.append(audit.finding(rules.GROSS, short))
        return found

    def classified(self, case: Case, audit: LineAudit) -> list[Finding]:
        """A lower-paid craft than the worker's established one, which owes them its
        rates, or else a change from last week's classification with no note."""
        worker = self.world.worker(audit.line.worker_id)
        if audit.craft != worker.craft and any(
            audit.claimed[day].wage + audit.claimed[day].fringe
            < rate.wage + rate.fringe
            for day, rate in audit.established.items()
        ):
            split = wage_rules.premium_split(RATES, worker.craft, audit.hours)
            wage = {day: rate.wage for day, rate in audit.established.items()}
            fringe = {day: rate.fringe for day, rate in audit.established.items()}
            short = wage_rules.base_shortfall(split, wage, audit.line.base_rate)
            short += wage_rules.fringe_shortfall(split, fringe, audit.fringe_paid)
            return [audit.finding(rules.MISMATCH, short)]
        before = self.previous(case)
        last_week = [
            ln
            for ln in (before.payroll.lines if before else ())
            if ln.worker_id == worker.id
        ]
        changed = last_week and last_week[0].classification != audit.line.classification
        if changed and not audit.line.line_notes:
            return [audit.finding(rules.CHANGED)]
        return []

    def pay(self, audit: LineAudit) -> list[Finding]:
        """The rates and overtime against what the line's classification requires,
        an unregistered apprentice's shortfall as a journeyman's."""
        line = audit.line
        split = wage_rules.premium_split(RATES, audit.craft, audit.hours)
        wage = {day: rate.wage for day, rate in audit.claimed.items()}
        fringe = {day: rate.fringe for day, rate in audit.claimed.items()}
        short_wage = wage_rules.base_shortfall(split, wage, line.base_rate)
        short_fringe = wage_rules.fringe_shortfall(split, fringe, audit.fringe_paid)
        registration = self.world.apprentice(line.worker_id)
        unregistered = audit.classification == APPRENTICE and registration is None
        found = []
        if unregistered and (short_wage or short_fringe):
            found.append(audit.finding(rules.UNREGISTERED, short_wage + short_fringe))
        else:
            if short_wage:
                found.append(audit.finding(rules.BASE_SHORT, short_wage))
            if short_fringe:
                found.append(audit.finding(rules.FRINGE_SHORT, short_fringe))
        if line.overtime_hours < wage_rules.premium_hours(split):
            short = wage_rules.overtime_shortfall(
                split, line.overtime_hours, line.base_rate, audit.fringe_paid
            )
            found.append(audit.finding(rules.OVERTIME, short))
        return found

    def ratio(self, submission: Submission) -> list[Finding]:
        """Each craft's apprentices against its journeymen and foremen."""
        crafts: dict[str, list[int]] = {}
        for line in submission.payroll.lines:
            craft, classification = classification_of(line.classification)
            counts = crafts.setdefault(craft, [0, 0])
            counts[0 if classification == APPRENTICE else 1] += 1
        if all(
            wage_rules.ratio_allows(RATES, craft, apprentices, journeymen)
            for craft, (apprentices, journeymen) in crafts.items()
        ):
            return []
        return [Finding(rules.RATIO)]
