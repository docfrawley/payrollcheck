import boto3
import pytest
from botocore.stub import Stubber

from deploy import aws as deploy_aws
from deploy.aws import Aws
from deploy.settings import MissingSettings


def test_the_session_knows_its_account_region_and_operator():
    session = Aws(boto3.Session(region_name="us-east-1"))
    with Stubber(session.client("sts")) as sts:
        sts.add_response(
            "get_caller_identity",
            {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/payrollcheck",
                "UserId": "AIDATEST",
            },
        )
        assert session.account == "123456789012"
        assert session.operator == "arn:aws:iam::123456789012:user/payrollcheck"
    assert session.region == "us-east-1"


def test_a_profile_with_no_region_says_so(monkeypatch):
    monkeypatch.delenv("AWS_DEFAULT_REGION")
    with pytest.raises(MissingSettings, match="aws configure"):
        Aws(boto3.Session()).region  # noqa: B018 - reading it is the test


def test_each_service_has_one_client():
    session = Aws(boto3.Session(region_name="us-east-1"))
    assert session.client("lambda") is session.client("lambda")


def test_connecting_takes_the_aws_clis_region_from_the_environment():
    assert deploy_aws.connect().region == "us-east-1"
