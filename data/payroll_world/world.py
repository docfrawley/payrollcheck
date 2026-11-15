"""A world of payrolls drawn from a seed: its projects, its subcontractors with
their engagement windows, their workers with their established crafts, their
registrations and the apprentices' registrations. The same spec and seed always
draw the same world."""

from dataclasses import dataclass
from datetime import date, timedelta

from context import registrations
from context.wage_rules import APPRENTICE, FOREMAN, JOURNEYMAN
from data.payroll_world.draws import digits, draw

# Wages for a week are paid on the Monday after it ends.
WAGES_PAID_AFTER = timedelta(days=1)
FIRST_NAMES = [
    "Adriana",
    "Alex",
    "Andre",
    "Angela",
    "Ana",
    "Ben",
    "Carlos",
    "Chen",
    "Dana",
    "Darius",
    "Elena",
    "Eli",
    "Farah",
    "Felix",
    "Gina",
    "Grace",
    "Hector",
    "Imani",
    "Ivan",
    "Jamal",
    "Janelle",
    "Jorge",
    "Kevin",
    "Kim",
    "Lena",
    "Luis",
    "Malik",
    "Maria",
    "Mateo",
    "Mei",
    "Nadia",
    "Nikolai",
    "Omar",
    "Owen",
    "Paul",
    "Priscilla",
    "Quinn",
    "Rafael",
    "Rosa",
    "Sam",
    "Sean",
    "Shanice",
    "Tariq",
    "Teresa",
    "Tomas",
    "Uma",
    "Victor",
    "Wei",
    "Xavier",
    "Yara",
    "Yusuf",
    "Zoe",
]
LAST_NAMES = [
    "Abara",
    "Alvarez",
    "Bianchi",
    "Brennan",
    "Castillo",
    "Chowdhury",
    "Costa",
    "DeLuca",
    "Diallo",
    "Dimitrov",
    "Esposito",
    "Fernandes",
    "Fitzgerald",
    "Gallo",
    "Gomez",
    "Haddad",
    "Hoang",
    "Ibrahim",
    "Jablonski",
    "Kaplan",
    "Kowalski",
    "Lindqvist",
    "Lopez",
    "Mahoney",
    "Medina",
    "Nakamura",
    "Novak",
    "Okafor",
    "Oliveira",
    "Petrov",
    "Quintero",
    "Reyes",
    "Romano",
    "Russo",
    "Santos",
    "Schultz",
    "Sharma",
    "Silva",
    "Sullivan",
    "Tanaka",
    "Torres",
    "Vargas",
    "Walsh",
    "Washington",
    "Yilmaz",
    "Zielinski",
]


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    county: str
    location: str
    public_body: str
    contract_no: str
    award_date: date
    reviewer: str


@dataclass(frozen=True)
class SubcontractorSpec:
    """A subcontractor as a world's spec gives it: its crafts, who signs its
    payrolls and its first week on each of the world's projects, or none."""

    id: str
    legal_name: str
    crafts: tuple[str, ...]
    signer: str
    contact: str
    domain: str
    starts: tuple[int | None, ...]


@dataclass(frozen=True)
class ApprenticeSpec:
    """An apprentice in a crew: their craft, and their levels by date when they are
    registered, or none and the level their payrolls give when they aren't, with the
    weeks they work."""

    pair: int
    craft: str
    levels: tuple[tuple[int, str], ...]
    weeks: tuple[int, int] | None = None
    unregistered_level: int | None = None


@dataclass(frozen=True)
class Spec:
    """Everything a world is drawn from."""

    name: str
    seed: int
    first_week_ending: date
    weeks: int
    # Whether the weeks before the last are history, decided by a reviewer, or
    # every case still waits, as in a set kept for evaluation.
    history: bool
    case_week_offset: int
    first_worker: int
    business_date: date
    compliance_manager: str
    # Registrations other than the lapsed one start in the 30 weeks from this date.
    registered_from: date
    projects: tuple[Project, ...]
    subcontractors: tuple[SubcontractorSpec, ...]
    apprentices: tuple[ApprenticeSpec, ...]
    # The subcontractor whose registration lapses, and the dates it lapses between.
    lapse: tuple[str, str, str]
    # The worlds whose workers' names this world's workers never share.
    apart_from: tuple["Spec", ...] = ()


@dataclass(frozen=True)
class Subcontractor:
    id: str
    legal_name: str
    fein: str
    registration_no: str
    signer: str
    contact_name: str
    contact_email: str


@dataclass(frozen=True)
class Engagement:
    """A subcontractor's engagement window on a project, and the pair's number, which
    the pair's case ids carry."""

    pair: int
    subcontractor_id: str
    project_id: str
    first_week: int
    last_week: int


@dataclass(frozen=True)
class Worker:
    """A worker on a pair's crew, with their established craft and classification,
    the weeks they work when they don't work them all, and an unregistered
    apprentice's level as their payrolls give it."""

    id: str
    name: str
    pair: int
    craft: str
    classification: str
    weeks: tuple[int, int] | None = None
    unregistered_level: int | None = None


@dataclass(frozen=True)
class Registration:
    """A subcontractor's public works contractor registration and the periods it was
    active, from its effective date to its expiry date."""

    registration_no: str
    subcontractor_id: str
    legal_name: str
    fein: str
    periods: tuple[tuple[date, date], ...]

    def active_on(self, day: date) -> bool:
        return registrations.active_on(list(self.periods), day)


@dataclass(frozen=True)
class ApprenticeRegistration:
    worker_id: str
    sponsor: str
    program: str
    registered_on: date
    levels: tuple[tuple[int, date], ...]

    def level_on(self, day: date) -> int | None:
        """Their level on a date, or none before they were registered."""
        return registrations.level_on(list(self.levels), day)


@dataclass(frozen=True)
class World:
    spec: Spec
    subcontractors: tuple[Subcontractor, ...]
    engagements: tuple[Engagement, ...]
    workers: tuple[Worker, ...]
    registrations: tuple[Registration, ...]
    apprentices: tuple[ApprenticeRegistration, ...]

    def week_ending(self, week: int) -> date:
        return self.spec.first_week_ending + timedelta(weeks=week - 1)

    def project(self, project_id: str) -> Project:
        [found] = [p for p in self.spec.projects if p.id == project_id]
        return found

    def subcontractor(self, subcontractor_id: str) -> Subcontractor:
        [found] = [s for s in self.subcontractors if s.id == subcontractor_id]
        return found

    def registration(self, subcontractor_id: str) -> Registration:
        [found] = [
            r for r in self.registrations if r.subcontractor_id == subcontractor_id
        ]
        return found

    def apprentice(self, worker_id: str) -> ApprenticeRegistration | None:
        found = [a for a in self.apprentices if a.worker_id == worker_id]
        return found[0] if found else None

    def worker(self, worker_id: str) -> Worker:
        [found] = [w for w in self.workers if w.id == worker_id]
        return found

    def crew(self, pair: int) -> list[Worker]:
        return [worker for worker in self.workers if worker.pair == pair]

    def wage_payment_date(self, week_ending: date) -> date:
        return week_ending + WAGES_PAID_AFTER

    def case_id(self, engagement: Engagement, week: int) -> str:
        return f"PC-{week + self.spec.case_week_offset:02d}{engagement.pair:02d}"


def subcontractor(spec: Spec, found: SubcontractorSpec) -> Subcontractor:
    source = draw(spec.seed, "subcontractor", found.id)
    return Subcontractor(
        found.id,
        found.legal_name,
        f"{source.randrange(20, 99)}-{digits(source, 7)}",
        f"{source.randrange(1, 10)}{digits(source, 5)}",
        found.signer,
        found.contact,
        f"payroll@{found.domain}",
    )


def engagements(spec: Spec) -> list[Engagement]:
    """Each subcontractor's windows on the projects, the pairs numbered project by
    project, each window running to the world's last week."""
    count = len(spec.subcontractors)
    return [
        Engagement(p * count + s + 1, sub.id, project.id, start, spec.weeks)
        for p, project in enumerate(spec.projects)
        for s, sub in enumerate(spec.subcontractors)
        if (start := sub.starts[p]) is not None
    ]


def crew_classifications(
    spec: Spec, engagement: Engagement, crafts: tuple[str, ...]
) -> list[tuple[str, str]]:
    """A pair's journeymen and foreman: two of them, or three with a foreman, never
    more than two beside an apprentice, each of the subcontractor's crafts in turn."""
    apprenticed = any(a.pair == engagement.pair and a.levels for a in spec.apprentices)
    with_foreman = not apprenticed and draw(spec.seed, "crew", engagement.pair).choice(
        (True, False)
    )
    classifications = [FOREMAN] * with_foreman + [JOURNEYMAN] * 2
    return [(crafts[i % len(crafts)], c) for i, c in enumerate(classifications)]


def worker_names(spec: Spec, count: int) -> list[str]:
    """The names of a world's workers, drawn once for the whole world from the
    names no world it is kept apart from has drawn."""
    taken = {
        name
        for other in spec.apart_from
        for name in worker_names(other, len(build_world(other).workers))
    }
    names = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
    return draw(spec.seed, "names").sample([n for n in names if n not in taken], count)


def workers(spec: Spec, pairs: list[Engagement]) -> list[Worker]:
    """Every crew's workers, then the apprentices in theirs, with names drawn once
    for the whole world."""
    crafts = {sub.id: sub.crafts for sub in spec.subcontractors}
    places = [
        (engagement.pair, craft, classification, None, None)
        for engagement in pairs
        for craft, classification in crew_classifications(
            spec, engagement, crafts[engagement.subcontractor_id]
        )
    ] + [
        (a.pair, a.craft, APPRENTICE, a.weeks, a.unregistered_level)
        for a in spec.apprentices
    ]
    chosen = worker_names(spec, len(places))
    return [
        Worker(f"W-{spec.first_worker + i:03d}", name, *place)
        for i, (name, place) in enumerate(zip(chosen, places, strict=True))
    ]


def registration(spec: Spec, sub: Subcontractor) -> Registration:
    """A subcontractor's registration, active for a year from a date before the
    world's first week, or with the spec's lapse and its renewal."""
    holder, lapsed, renewed = spec.lapse
    if sub.id == holder:
        expiry, renewal = date.fromisoformat(lapsed), date.fromisoformat(renewed)
        periods = (
            (expiry - timedelta(days=364), expiry),
            (renewal, renewal + timedelta(days=364)),
        )
    else:
        start = spec.registered_from + timedelta(
            weeks=draw(spec.seed, "registered", sub.id).randrange(30)
        )
        periods = ((start, start + timedelta(days=364)),)
    return Registration(sub.registration_no, sub.id, sub.legal_name, sub.fein, periods)


SPONSORS = {
    "electrician": ("Central Jersey Electrical JATC", "Inside wireman"),
    "carpenter": ("Shore Carpenters Training Fund", "Carpenter"),
    "plumber": ("Raritan Bay Plumbers JATC", "Plumber and pipefitter"),
    "ironworker": ("Garden State Ironworkers JATC", "Structural ironworker"),
    "painter": ("Finishing Trades Institute of NJ", "Painter and decorator"),
    "bricklayer": ("Masonry Craft Training Center", "Bricklayer"),
    "laborer": ("NJ Laborers Training Center", "Construction craft laborer"),
    "operating_engineer": ("Operating Engineers Training Program", "Heavy equipment"),
}


def apprentice_registrations(
    spec: Spec, crew: list[Worker]
) -> list[ApprenticeRegistration]:
    """The registrations of the spec's registered apprentices, in the order of their
    places in the crews."""
    apprentices = [w for w in crew if w.classification == APPRENTICE]
    found = []
    for worker, apprentice in zip(apprentices, spec.apprentices, strict=True):
        if not apprentice.levels:
            continue
        sponsor, trade = SPONSORS[apprentice.craft]
        levels = tuple(
            (level, date.fromisoformat(day)) for level, day in apprentice.levels
        )
        number = digits(draw(spec.seed, "program", worker.id), 4)
        program = (
            f"{trade} apprenticeship, USDOL program NJ-{levels[0][1].year}-{number}"
        )
        found.append(
            ApprenticeRegistration(worker.id, sponsor, program, levels[0][1], levels)
        )
    return found


def build_world(spec: Spec) -> World:
    """The world a spec and its seed draw."""
    subs = [subcontractor(spec, found) for found in spec.subcontractors]
    pairs = engagements(spec)
    crew = workers(spec, pairs)
    return World(
        spec,
        tuple(subs),
        tuple(pairs),
        tuple(crew),
        tuple(registration(spec, sub) for sub in subs),
        tuple(apprentice_registrations(spec, crew)),
    )
