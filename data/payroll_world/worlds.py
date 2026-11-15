"""The specs of the worlds the generator draws: the development world, Pinelands
Builders' three projects and eight subcontractors over twelve weeks, and the
held-out world, three other projects in the same counties with five other
subcontractors over the last eight of those weeks, kept for evaluation."""

from datetime import date

from data.payroll_world.world import ApprenticeSpec, Project, Spec, SubcontractorSpec

DANA = "dana.whitfield@payrollcheck.example"

MARCUS = "marcus.oyelaran@payrollcheck.example"
PRIYA = "priya.raman@payrollcheck.example"
LINCOLN = "PRJ-01"
MUNICIPAL = "PRJ-02"
ROAD = "PRJ-03"
GARDEN_STATE = "SUB-01"
# The case the Copilot is asked to draft a send-back notice for.
NOTICE_CASE = "PC-0311"

DEVELOPMENT = Spec(
    name="development",
    seed=20260906,
    first_week_ending=date(2026, 9, 6),
    weeks=12,
    history=True,
    case_week_offset=0,
    first_worker=1,
    business_date=date(2026, 11, 23),
    compliance_manager=DANA,
    registered_from=date(2026, 1, 5),
    projects=(
        Project(
            LINCOLN,
            "Lincoln School renovation",
            "Middlesex",
            "Lincoln Elementary School, New Brunswick",
            "New Brunswick Board of Education",
            "NBBOE-2026-014",
            date(2026, 4, 15),
            MARCUS,
        ),
        Project(
            MUNICIPAL,
            "Municipal building",
            "Monmouth",
            "Freehold Township Municipal Building, Freehold",
            "Township of Freehold",
            "FT-2026-07",
            date(2026, 5, 20),
            MARCUS,
        ),
        Project(
            ROAD,
            "Road resurfacing",
            "Ocean",
            "County Route 571, Toms River to Lakehurst",
            "County of Ocean",
            "OC-2026-RD-112",
            date(2026, 6, 10),
            PRIYA,
        ),
    ),
    subcontractors=(
        SubcontractorSpec(
            GARDEN_STATE,
            "Garden State Electric LLC",
            ("electrician",),
            "Rosa Medina, Payroll Manager",
            "Rosa Medina",
            "gardenstateelectric.example",
            (1, 2, 8),
        ),
        SubcontractorSpec(
            "SUB-02",
            "Raritan Valley Carpentry Inc.",
            ("carpenter",),
            "Thomas Brennan, President",
            "Kelly Brennan",
            "raritanvalleycarpentry.example",
            (1, 3, 8),
        ),
        SubcontractorSpec(
            "SUB-03",
            "Shore Point Plumbing & Heating LLC",
            ("plumber",),
            "Anil Sharma, Owner",
            "Anil Sharma",
            "shorepointplumbing.example",
            (2, 1, 9),
        ),
        SubcontractorSpec(
            "SUB-04",
            "Liberty Steel Erectors Inc.",
            ("ironworker",),
            "Grace Okafor, Controller",
            "Grace Okafor",
            "libertysteelerectors.example",
            (5, 1, 9),
        ),
        SubcontractorSpec(
            "SUB-05",
            "Pine Barrens Painting Co.",
            ("painter",),
            "Luis Quintero, Owner",
            "Marta Quintero",
            "pinebarrenspainting.example",
            (6, 4, 9),
        ),
        SubcontractorSpec(
            "SUB-06",
            "Delaware Valley Masonry LLC",
            ("bricklayer",),
            "Frank Esposito, Managing Member",
            "Frank Esposito",
            "delawarevalleymasonry.example",
            (2, 9, 9),
        ),
        SubcontractorSpec(
            "SUB-07",
            "Meadowlands Site Services LLC",
            ("laborer",),
            "Imani Washington, Payroll Administrator",
            "Imani Washington",
            "meadowlandssite.example",
            (1, 3, 1),
        ),
        SubcontractorSpec(
            "SUB-08",
            "Turnpike Paving & Equipment Inc.",
            ("operating_engineer",),
            "Victor Kowalski, Vice President",
            "Dana Kowalski",
            "turnpikepaving.example",
            (6, 2, 1),
        ),
    ),
    apprentices=(
        ApprenticeSpec(1, "electrician", ((2, "2025-09-02"), (3, "2026-10-19"))),
        ApprenticeSpec(9, "electrician", ((1, "2026-03-02"),)),
        ApprenticeSpec(2, "carpenter", ((2, "2025-06-02"),)),
        ApprenticeSpec(11, "plumber", ((3, "2024-09-03"),)),
        ApprenticeSpec(5, "painter", ((1, "2026-02-02"),)),
        ApprenticeSpec(10, "carpenter", (), weeks=(12, 12), unregistered_level=1),
    ),
    lapse=("SUB-06", "2026-10-11", "2026-10-18"),
)

HELD_OUT = Spec(
    name="held_out",
    seed=20261004,
    first_week_ending=date(2026, 10, 4),
    weeks=8,
    history=False,
    case_week_offset=50,
    first_worker=501,
    business_date=date(2026, 11, 23),
    compliance_manager=DANA,
    registered_from=date(2026, 2, 2),
    projects=(
        Project(
            "PRJ-51",
            "Library expansion",
            "Middlesex",
            "Edison Public Library, Edison",
            "Township of Edison",
            "TE-2026-031",
            date(2026, 5, 4),
            MARCUS,
        ),
        Project(
            "PRJ-52",
            "Fire station",
            "Monmouth",
            "Fire Station 3, Long Branch",
            "City of Long Branch",
            "LB-2026-09",
            date(2026, 4, 27),
            MARCUS,
        ),
        Project(
            "PRJ-53",
            "Bridge deck repair",
            "Ocean",
            "Route 37 bridge over the Toms River, Toms River",
            "County of Ocean",
            "OC-2026-BR-047",
            date(2026, 6, 1),
            PRIYA,
        ),
    ),
    subcontractors=(
        SubcontractorSpec(
            "SUB-51",
            "Hudson Line Electric LLC",
            ("electrician",),
            "Oscar Lindqvist, Treasurer",
            "Oscar Lindqvist",
            "hudsonlineelectric.example",
            (1, 1, 3),
        ),
        SubcontractorSpec(
            "SUB-52",
            "Palisades Building Trades Inc.",
            ("carpenter", "ironworker"),
            "Helen Romano, President",
            "Helen Romano",
            "palisadesbuilding.example",
            (1, 2, 4),
        ),
        SubcontractorSpec(
            "SUB-53",
            "Barnegat Mechanical LLC",
            ("plumber",),
            "Desmond Walsh, Owner",
            "Desmond Walsh",
            "barnegatmechanical.example",
            (2, 1, 5),
        ),
        SubcontractorSpec(
            "SUB-54",
            "Ironbound Finishes Co.",
            ("painter", "bricklayer"),
            "Ana Costa, Office Manager",
            "Ana Costa",
            "ironboundfinishes.example",
            (1, 3, 2),
        ),
        SubcontractorSpec(
            "SUB-55",
            "Navesink Heavy Civil Inc.",
            ("laborer", "operating_engineer"),
            "Ray Sullivan, Controller",
            "Ray Sullivan",
            "navesinkheavycivil.example",
            (4, 6, 1),
        ),
    ),
    apprentices=(
        ApprenticeSpec(1, "electrician", ((2, "2025-10-06"),)),
        ApprenticeSpec(6, "electrician", ((4, "2023-09-05"),)),
        ApprenticeSpec(3, "plumber", ((1, "2026-01-12"), (2, "2026-11-02"))),
        ApprenticeSpec(11, "electrician", (), weeks=(8, 8), unregistered_level=2),
    ),
    lapse=("SUB-55", "2026-10-11", "2026-10-18"),
    apart_from=(DEVELOPMENT,),
)
