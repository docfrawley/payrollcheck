import pytest

from deploy.__main__ import main, parser, steps


def test_help_lists_every_step(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    shown = capsys.readouterr().out
    assert all(step in shown for step in steps())


def test_a_step_that_cant_start_says_what_is_missing(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("REVIEWER_PASSWORD", raising=False)
    assert main(["supabase"]) == 1
    assert capsys.readouterr().out == (
        "Add SUPABASE_SECRET_KEY, REVIEWER_PASSWORD to .env\n"
    )


def test_the_teardown_lists_unless_told_yes():
    assert parser().parse_args(["teardown"]).yes is False
    assert parser().parse_args(["teardown", "--yes"]).yes is True
