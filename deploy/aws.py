"""The one AWS session the runbook works in, from the AWS CLI's profile, with each
service's client made once, and who the runbook runs as."""

from functools import cached_property
from typing import Any

import boto3

from deploy.settings import MissingSettings


class Aws:
    """An AWS session, its account and region, and a client for each service."""

    def __init__(self, session: boto3.Session) -> None:
        self.session = session
        self.clients: dict[str, Any] = {}

    def client(self, service: str) -> Any:
        """The session's client for a service, made the first time it's asked for."""
        if service not in self.clients:
            self.clients[service] = self.session.client(service)
        return self.clients[service]

    @cached_property
    def identity(self) -> dict[str, str]:
        """Who the session is, as STS says."""
        return self.client("sts").get_caller_identity()

    @property
    def account(self) -> str:
        return self.identity["Account"]

    @property
    def region(self) -> str:
        region = self.session.region_name
        if region is None:
            raise MissingSettings("Give the AWS CLI profile a region: aws configure")
        return region

    @property
    def operator(self) -> str:
        """The ARN of the identity the runbook runs as."""
        return self.identity["Arn"]


def connect() -> Aws:
    """The AWS CLI profile's session."""
    return Aws(boto3.Session())
