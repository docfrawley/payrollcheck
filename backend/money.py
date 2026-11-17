"""Amounts in US dollars as people read them, such as $1,250.00."""


def dollars(amount: float) -> str:
    """Format an amount like $1,250.00."""
    return f"${amount:,.2f}"


def cents_in_dollars(cents: int) -> str:
    """Format an amount in cents like $1,250.00."""
    return dollars(cents / 100)


def cents_in_dollars_or_none(cents: int | None) -> str | None:
    """An amount in cents as dollars, or none when there is none."""
    return None if cents is None else cents_in_dollars(cents)
