"""Fixtures for the runbook's tests: an AWS session on the stand-in credentials the
root conftest gives every test, with each service's client answered by botocore's
Stubber, so no test reaches AWS, and no pause in any wait."""

import boto3
import pytest
from botocore.stub import Stubber

from deploy import waits
from deploy.aws import Aws

ACCOUNT = "123456789012"
REGION = "us-east-1"
OPERATOR = f"arn:aws:iam::{ACCOUNT}:user/payrollcheck"


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch):
    """Take the time out of every wait, keeping how long each would have been."""
    pauses: list[float] = []
    monkeypatch.setattr(waits, "pause", pauses.append)
    return pauses


@pytest.fixture
def aws():
    """A session as the operator, in the stand-in account and region."""
    session = Aws(boto3.Session(region_name=REGION))
    session.identity = {"Account": ACCOUNT, "Arn": OPERATOR, "UserId": "AIDATEST"}
    return session


@pytest.fixture
def stub(aws):
    """A Stubber for one service's client in the session, checked at the end of the
    test to have had every call it expected."""
    stubbers: list[Stubber] = []

    def stubbed(service: str) -> Stubber:
        stubber = Stubber(aws.client(service))
        stubber.activate()
        stubbers.append(stubber)
        return stubber

    yield stubbed
    for stubber in stubbers:
        stubber.assert_no_pending_responses()
        stubber.deactivate()
