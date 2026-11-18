from deploy import memory, names
from deploy.tests.conftest import ACCOUNT

MEMORY_ID = f"{names.MEMORY}-AbCdEf1234"
MEMORY = {
    "arn": f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:memory/{MEMORY_ID}",
    "id": MEMORY_ID,
    "name": names.MEMORY,
    "eventExpiryDuration": 7,
    "status": "ACTIVE",
    "createdAt": "2026-11-18T00:00:00Z",
    "updatedAt": "2026-11-18T00:00:00Z",
}


def listing(*memories):
    return {
        "memories": [
            {
                "arn": m["arn"],
                "id": m["id"],
                "status": m["status"],
                "createdAt": m["createdAt"],
                "updatedAt": m["updatedAt"],
            }
            for m in memories
        ]
    }


def test_the_copilots_memory_files_notes_under_each_reviewer():
    assert memory.STRATEGIES == [
        {
            "userPreferenceMemoryStrategy": {
                "name": "reviewer_preferences",
                "namespaceTemplates": ["/reviewers/{actorId}/preferences/"],
            }
        },
        {
            "semanticMemoryStrategy": {
                "name": "reviewer_facts",
                "namespaceTemplates": ["/reviewers/{actorId}/facts/"],
            }
        },
    ]


def test_the_memory_is_made_tagged_and_waited_for(aws, stub, monkeypatch, capsys):
    assert memory.EVERY_10S == {"Delay": 10, "MaxAttempts": 60}
    monkeypatch.setattr(memory, "EVERY_10S", {"Delay": 0, "MaxAttempts": 60})
    control = stub("bedrock-agentcore-control")
    control.add_response("list_memories", listing())
    control.add_response(
        "create_memory",
        {"memory": MEMORY | {"status": "CREATING"}},
        {
            "name": names.MEMORY,
            "description": "The PayrollCheck Copilot's memory of each reviewer",
            "eventExpiryDuration": 7,
            "memoryStrategies": memory.STRATEGIES,
            "tags": names.TAGS,
        },
    )
    control.add_response(
        "get_memory",
        {"memory": MEMORY | {"status": "CREATING"}},
        {"memoryId": MEMORY_ID},
    )
    control.add_response("get_memory", {"memory": MEMORY}, {"memoryId": MEMORY_ID})
    control.add_response("get_memory", {"memory": MEMORY}, {"memoryId": MEMORY_ID})
    memory.run(aws)
    assert capsys.readouterr().out.splitlines() == [
        f"Memory {names.MEMORY}: created",
        f"The Copilot's Memory: {MEMORY_ID}",
    ]


def test_a_memory_thats_there_is_used_as_it_is(aws, stub, capsys):
    control = stub("bedrock-agentcore-control")
    control.add_response(
        "list_memories",
        listing(MEMORY | {"id": f"{names.MEMORY}-old", "status": "DELETING"}, MEMORY),
    )
    control.add_response("get_memory", {"memory": MEMORY})
    control.add_response("get_memory", {"memory": MEMORY})
    assert memory.make_memory(aws)["id"] == MEMORY_ID
    assert capsys.readouterr().out == f"Memory {names.MEMORY}: unchanged\n"
