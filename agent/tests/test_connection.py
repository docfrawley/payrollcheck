import re

import httpx
import pytest

from agent import connection


def test_the_key_is_read_as_each_request_is_sent(monkeypatch, agent_key):
    sent: list[str | None] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers.get(connection.API_KEY_HEADER))
        return httpx.Response(200, json={"status": "ok"})

    stand_in = httpx.Client(
        base_url=str(connection.backend.base_url),
        transport=httpx.MockTransport(answer),
    )
    monkeypatch.setattr(connection, "backend", stand_in)
    connection.call("GET", "/health")
    monkeypatch.setenv("PAYROLLCHECK_API_KEY", "a-key-set-after-the-import")
    connection.call("GET", "/health")
    assert sent == [agent_key, "a-key-set-after-the-import"]


def test_a_request_without_the_key_says_its_missing(monkeypatch):
    monkeypatch.delenv("PAYROLLCHECK_API_KEY")
    with pytest.raises(RuntimeError, match=re.escape(connection.MISSING_KEY)):
        connection.call("GET", "/health")


def backend_answering(monkeypatch, response: httpx.Response) -> None:
    stand_in = httpx.Client(
        base_url=str(connection.backend.base_url),
        transport=httpx.MockTransport(lambda _: response),
    )
    monkeypatch.setattr(connection, "backend", stand_in)


def test_a_request_turned_away_for_now_is_throttled(monkeypatch, agent_key):
    lambda_throttle = httpx.Response(429, json={"Message": "Rate Exceeded."})
    backend_answering(monkeypatch, lambda_throttle)
    with pytest.raises(connection.Throttled, match="Rate Exceeded"):
        connection.call("GET", "/health")


def test_a_refusal_gives_the_backends_reason(monkeypatch, agent_key):
    backend_answering(monkeypatch, httpx.Response(404, json={"detail": "No such case"}))
    with pytest.raises(connection.Refused) as refused:
        connection.call("GET", "/health")
    assert (refused.value.status_code, refused.value.detail) == (404, "No such case")


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(502, json={"Message": "Internal Server Error"}),
        httpx.Response(502, text="Bad Gateway"),
    ],
)
def test_a_refusal_from_in_front_of_the_backend_gives_its_body(
    monkeypatch, agent_key, answer
):
    backend_answering(monkeypatch, answer)
    with pytest.raises(connection.Refused) as refused:
        connection.call("GET", "/health")
    assert refused.value.status_code == 502
    assert refused.value.detail == answer.text
