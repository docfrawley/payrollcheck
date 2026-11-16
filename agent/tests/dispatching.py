"""Runs the tests work, which a reviewer starts and the app creates, with payroll graphs
on a stub model."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from agent import dispatcher, harness
from agent.tests.stubs import agent_on
from backend.dependencies import API_KEY_HEADER
from backend.main import app
from backend.tests.run_requests import create_dispatch, create_evaluation
from backend.tests.sign_in import DANA


@contextmanager
def the_app() -> Iterator[TestClient]:
    """The app, called with the agent's key, as the agent and the backend's tests
    call it, and closed once the block's calls are done."""
    headers = {API_KEY_HEADER: os.environ["PAYROLLCHECK_API_KEY"]}
    with TestClient(app, headers=headers) as caller:
        yield caller


def new_dispatch(agents=3, email=DANA):
    """Start a dispatch as a reviewer does, which the app creates, and return it as
    the agent reads it."""
    with the_app() as caller:
        return create_dispatch(caller, agents, email).json()


def new_evaluation(evaluation_set="tiny", agents=5):
    """Start an evaluation as a reviewer does, which the app creates with its copies,
    and return it as the agent reads it."""
    with the_app() as caller:
        return create_evaluation(caller, evaluation_set, agents).json()


def dispatch(model, saver=None, agents=3, email=DANA):
    """Work a new dispatch, started by the reviewer with this email, with payroll
    graphs on the model, which share a saver as they share the database in the
    agent, and return its report lines."""
    saver = saver or InMemorySaver()
    work = partial(harness.work_in_run, new_agent=partial(agent_on, model, saver))
    return dispatcher.work_run(new_dispatch(agents, email), work)
