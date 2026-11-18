import pytest

from deploy import waits


def test_waiting_for_a_resource_that_is_changing(no_pauses, capsys):
    statuses = iter(["CREATING", "UPDATING", "READY"])
    resource = waits.wait_for(
        lambda: {"status": next(statuses), "statusReasons": ["fine"]}, "Gateway g-1"
    )
    assert resource["status"] == "READY"
    assert no_pauses == [3, 3]
    assert capsys.readouterr().out == "Gateway g-1: READY\n  fine\n"


def test_a_retry_waits_out_an_error_it_expects(no_pauses, capsys):
    attempts = iter([ValueError("The role isn't ready"), "made"])

    def attempt():
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    made = waits.retry(
        attempt, waits.says("ROLE"), tries=3, every=5, message="Waiting for the role"
    )
    assert made == "made"
    assert no_pauses == [5]
    assert capsys.readouterr().out == "Waiting for the role\n"


def test_a_retry_raises_an_error_it_doesnt_expect(no_pauses):
    def attempt():
        raise ValueError("something else")

    with pytest.raises(ValueError, match="something else"):
        waits.retry(attempt, waits.says("role"), tries=3, every=5, message="")
    assert no_pauses == []


def test_waiting_for_a_listing_to_empty(no_pauses):
    listings = iter([["one"], ["one"], []])
    waits.until_gone(lambda: next(listings), "targets")
    assert no_pauses == [3, 3]
    with pytest.raises(RuntimeError, match="targets didn't go"):
        waits.until_gone(lambda: ["one"], "targets", tries=3)


def test_a_retry_gives_up_after_its_tries(no_pauses):
    def attempt():
        raise ValueError("role")

    with pytest.raises(ValueError, match="role"):
        waits.retry(attempt, waits.says("role"), tries=3, every=5, message="")
    assert no_pauses == [5, 5]
