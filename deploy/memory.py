"""Step 6, the Copilot's Memory: payrollcheck_copilot_memory, whose two strategies turn
each conversation into notes under the reviewer's own namespace, how they like to
work and the facts they mention, as Ed's Copilot Memory had them for handlers. The
payroll agent keeps no memory, so it has none."""

from typing import Any

from agent.copilot.memory import REVIEWERS
from deploy import names, resources
from deploy.aws import Aws

EVENT_DAYS = 7
# Ed's wait for a new Memory, every 10 seconds, here for up to 10 minutes, since
# botocore's own gives up after 2.
EVERY_10S = {"Delay": 10, "MaxAttempts": 60}
STRATEGIES = [
    {
        "userPreferenceMemoryStrategy": {
            "name": "reviewer_preferences",
            "namespaceTemplates": [f"/{REVIEWERS}/{{actorId}}/preferences/"],
        }
    },
    {
        "semanticMemoryStrategy": {
            "name": "reviewer_facts",
            "namespaceTemplates": [f"/{REVIEWERS}/{{actorId}}/facts/"],
        }
    },
]


def make_memory(aws: Aws) -> dict[str, Any]:
    """The Copilot's Memory, made the first time, which takes about two and a half
    minutes. Returns it once it's active."""
    control = resources.control(aws)
    found = resources.find_memory(aws)
    if found:
        memory_id = found["id"]
        print(f"Memory {names.MEMORY}: unchanged")
    else:
        memory_id = control.create_memory(
            name=names.MEMORY,
            description="The PayrollCheck Copilot's memory of each reviewer",
            eventExpiryDuration=EVENT_DAYS,
            memoryStrategies=STRATEGIES,
            tags=names.TAGS,
        )["memory"]["id"]
        print(f"Memory {names.MEMORY}: created")
    control.get_waiter("memory_created").wait(
        memoryId=memory_id, WaiterConfig=EVERY_10S
    )
    return control.get_memory(memoryId=memory_id)["memory"]


def run(aws: Aws) -> None:
    """Step 6: the Copilot's Memory, with its id printed."""
    print(f"The Copilot's Memory: {make_memory(aws)['id']}")
