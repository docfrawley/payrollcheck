"""The rule codes an error can be seeded under and the kinds of decoy, each named
once: the manifest reads them, the corruptions and the decoys apply them, and the
lifecycle knows which errors a correction can't undo."""

BASE_SHORT = "rate.base_short"
FRINGE_SHORT = "rate.fringe_short"
OVERTIME = "overtime.underpaid"
HOURS_TOTAL = "arithmetic.hours_total"
GROSS = "arithmetic.gross"
UNREGISTERED = "apprentice.unregistered"
MISMATCH = "classification.mismatch"
CHANGED = "classification.changed"
MISSING_FIELD = "form.missing_field"
UNSIGNED = "form.unsigned"
INACTIVE = "registration.inactive"
RATIO = "apprentice.ratio"
LATE = "timeliness.late"
GAP = "sequence.gap"

# The rules about a worker's line, and those about the whole payroll.
LINE_RULES = (
    BASE_SHORT,
    FRINGE_SHORT,
    OVERTIME,
    HOURS_TOTAL,
    GROSS,
    UNREGISTERED,
    MISMATCH,
    CHANGED,
)
CASE_RULES = (MISSING_FIELD, UNSIGNED, INACTIVE, RATIO, LATE, GAP)
# Errors a correction can't undo: a payroll filed late, or work done unregistered.
UNCORRECTABLE = (LATE, INACTIVE)

DAILY_OVERTIME = "daily_overtime"
SATURDAY_OVERTIME = "saturday_overtime"
RATE_INCREASE_WEEK = "rate_increase_week"
CLASSIFICATION_NOTE = "classification_note"
CORRECTED_RESUBMISSION = "corrected_resubmission"
CASH_IN_LIEU = "cash_in_lieu"
APPRENTICE_AT_LEVEL = "apprentice_at_level"
LATER_DETERMINATION = "later_determination"
NO_WORK_WEEK = "no_work_week"
NAME_VARIANT = "name_variant"

# The decoys that shape one worker's line, and those that shape the whole payroll.
LINE_DECOYS = (
    DAILY_OVERTIME,
    SATURDAY_OVERTIME,
    RATE_INCREASE_WEEK,
    CLASSIFICATION_NOTE,
    CORRECTED_RESUBMISSION,
    CASH_IN_LIEU,
    APPRENTICE_AT_LEVEL,
)
PAYROLL_DECOYS = (LATER_DETERMINATION, NO_WORK_WEEK, NAME_VARIANT)
