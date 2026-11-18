"""The IAM policy the operator's user has: the course's, renamed for PayrollCheck, with
what the runbook's tag checks need."""

import json
from fnmatch import fnmatchcase

import pytest

from deploy import names
from deploy.settings import REPO

POLICY = json.loads((REPO / "deploy" / "operator_policy.json").read_text())
ACCOUNT = "123456789012"
IN = f"us-east-1:{ACCOUNT}"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/{names.APP_ROLE}"
FUNCTION = f"arn:aws:lambda:{IN}:function:{names.APP_FUNCTION}"
LOG_GROUP = f"arn:aws:logs:{IN}:log-group:{names.log_group(names.APP_FUNCTION)}"
AGENTCORE = f"arn:aws:bedrock-agentcore:{IN}:gateway/{names.GATEWAY}-a1b2c3"
STACK = f"arn:aws:cloudformation:{IN}:stack/{names.STACK}/x"
# The statements the course gave every resource in the account, each a read or
# a service the runbook drives as a whole. Widening another one fails a test.
ACCOUNT_WIDE = {
    "WhoAmI",
    "AccountChecks",
    "AgentCoreEverything",
    "CloudFormationStacks",
    "ListRolesForTeardown",
    "ServiceLinkedRoles",
    "ListLambdas",
    "ListBuckets",
    "EcrLogin",
    "EncryptionKeys",
    "Logs",
    "TraceSetup",
    "ListSecretsForTeardown",
    "ReadMetrics",
    "FindEverythingByTag",
    "FindEverythingInTheAccount",
    "BudgetsAndCosts",
}

# Each call the runbook makes, on what.
CALLS = [
    ("sts:GetCallerIdentity", "*"),
    ("lambda:CreateFunction", FUNCTION),
    ("lambda:UpdateFunctionCode", FUNCTION),
    ("lambda:CreateFunctionUrlConfig", FUNCTION),
    ("lambda:AddPermission", FUNCTION),
    ("lambda:ListTags", FUNCTION),
    ("lambda:DeleteFunction", FUNCTION),
    ("iam:CreateRole", ROLE),
    ("iam:GetRole", ROLE),
    ("iam:PutRolePolicy", ROLE),
    ("iam:ListRoleTags", ROLE),
    ("iam:ListRolePolicies", ROLE),
    ("iam:DeleteRolePolicy", ROLE),
    ("iam:DeleteRole", ROLE),
    ("iam:PassRole", ROLE),
    ("iam:ListRoles", "*"),
    ("logs:CreateLogGroup", LOG_GROUP),
    ("logs:PutRetentionPolicy", LOG_GROUP),
    ("logs:TagResource", LOG_GROUP),
    ("logs:ListTagsForResource", LOG_GROUP),
    ("logs:FilterLogEvents", LOG_GROUP),
    ("logs:DeleteLogGroup", LOG_GROUP),
    ("bedrock-agentcore:CreateGateway", AGENTCORE),
    ("bedrock-agentcore:CreatePolicy", AGENTCORE),
    ("bedrock-agentcore:CreateMemory", AGENTCORE),
    ("bedrock-agentcore:InvokeAgentRuntime", AGENTCORE),
    ("bedrock-agentcore:InvokeGateway", AGENTCORE),
    ("cloudformation:DescribeStacks", STACK),
    ("cloudformation:DeleteStack", STACK),
    ("cloudwatch:GetMetricStatistics", "*"),
    (
        "secretsmanager:GetSecretValue",
        f"arn:aws:secretsmanager:{IN}:secret:bedrock-agentcore-identity!default/k",
    ),
]


def as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def allows(action: str, resource: str) -> bool:
    """Whether a statement allows the action on the resource, ignoring conditions."""
    return any(
        statement["Effect"] == "Allow"
        and any(fnmatchcase(action, a) for a in as_list(statement["Action"]))
        and any(fnmatchcase(resource, r) for r in as_list(statement["Resource"]))
        for statement in POLICY["Statement"]
    )


def test_the_policy_names_nothing_of_undercovers():
    assert "undercover" not in json.dumps(POLICY).lower()


@pytest.mark.parametrize(("action", "resource"), CALLS)
def test_the_policy_allows_each_call_the_runbook_makes(action, resource):
    assert allows(action, resource)


def test_only_the_courses_account_wide_statements_cover_every_resource():
    every = {
        statement["Sid"]
        for statement in POLICY["Statement"]
        if "*" in as_list(statement["Resource"])
    }
    assert every == ACCOUNT_WIDE


def test_the_policy_allows_nothing_on_another_projects_resources():
    assert not allows("lambda:DeleteFunction", FUNCTION.replace("payrollcheck", "x"))
    assert not allows("iam:DeleteRole", ROLE.replace("payrollcheck", "x"))
    assert not allows("logs:DeleteLogGroup", LOG_GROUP.replace("payrollcheck", "x"))
