from deploy import names

TAG_KEYS = {"TAG_KEY", "CLI_PROJECT_TAG"}


def test_every_name_is_ours():
    made = [
        value
        for name, value in vars(names).items()
        if name.isupper() and isinstance(value, str) and name not in TAG_KEYS
    ]
    assert names.GATEWAY in made
    assert names.STACK in made
    others = [name for name in made if name != names.STACK]
    assert all(names.is_ours(name, names.TAGS) for name in others)
    assert names.is_ours(names.STACK, {names.CLI_PROJECT_TAG: names.PROJECT})


def test_only_a_resource_named_and_tagged_for_us_is_ours():
    assert names.is_ours("payrollcheck-app", {"project": "payrollcheck"})
    assert names.is_ours(names.STACK, {"agentcore:project-name": "payrollcheck"})
    assert not names.is_ours(names.STACK, names.TAGS)
    assert not names.is_ours(names.STACK, {"agentcore:project-name": "undercover"})
    assert names.is_ours("/aws/lambda/payrollcheck-app", names.TAGS)
    assert names.is_ours("payrollcheck_copilot_memory-AbC123", names.TAGS)
    assert not names.is_ours("undercover-app", names.TAGS)
    assert not names.is_ours("payrollcheck-app", {})
    assert not names.is_ours("payrollcheck-app", {"project": "undercover"})
    assert not names.is_ours("/aws/lambda/other", names.TAGS)


def test_tags_as_a_list_of_keys_and_values():
    assert names.tag_list() == [{"Key": "project", "Value": "payrollcheck"}]
