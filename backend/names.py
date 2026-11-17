"""Finding records by the words in a name, ignoring case, as the Copilot finds
subcontractors and projects."""

from typing import Annotated

from fastapi import Query
from sqlalchemy import ColumnElement, Select, func

# A name to look for, with something in it besides spaces.
Name = Annotated[str, Query(pattern=r"\S", description="Words in the name")]


def holding_every_word(query: Select, column: ColumnElement[str], name: str) -> Select:
    """The query, keeping only the rows whose column holds every word of the name."""
    for word in name.lower().split():
        query = query.where(func.lower(column).contains(word, autoescape=True))
    return query
