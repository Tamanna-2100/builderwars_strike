from unittest.mock import Mock, patch

import pytest

from verifier import run_spec


def test_runs_steps_and_checks_final_response():
    spec = {
        "steps": [
            {"as": "alice", "method": "POST", "path": "/notes", "body": {"text": "test"}},
            {"as": "none", "method": "GET", "path": "/notes/1"},
        ],
        "expected_outcome": {"status": 401, "body_contains": "unauthorized"},
    }
    responses = [Mock(status_code=201, text="created"), Mock(status_code=401, text="unauthorized")]
    with patch("requests.Session.request", side_effect=responses) as send:
        result = run_spec(spec, "http://localhost:5000")

    assert result == {
        "confirmed": True,
        "request": {"method": "GET", "url": "http://localhost:5000/notes/1", "headers": {}},
        "response": {"status": 401, "body": "unauthorized"},
    }
    assert send.call_args_list[0].kwargs["headers"] == {"X-Token": "alice-token"}
    assert send.call_args_list[0].kwargs["json"] == {"text": "test"}
    assert send.call_args_list[1].kwargs["headers"] == {}
    assert all(call.kwargs["allow_redirects"] is False for call in send.call_args_list)


@pytest.mark.parametrize("status,body", [(403, "expected"), (200, "different")])
def test_rejects_mismatched_response(status, body):
    spec = {
        "steps": [{"as": "bob-token", "method": "GET", "path": "/"}],
        "expected_outcome": {"status": 200, "body_contains": "expected"},
    }
    with patch("requests.Session.request", return_value=Mock(status_code=status, text=body)) as send:
        assert not run_spec(spec, "http://127.0.0.1:5000")["confirmed"]
    assert send.call_args.kwargs["headers"] == {"X-Token": "bob-token"}


@pytest.mark.parametrize("base_url", ["http://example.com", "http://localhost.example.com", "http://localhost@evil.test", "file://localhost", "http://localhost/base"])
def test_rejects_nonlocal_or_invalid_origins(base_url):
    with patch("requests.Session.request") as send:
        with pytest.raises(ValueError):
            run_spec({"steps": []}, base_url)
    send.assert_not_called()


@pytest.mark.parametrize("path", ["notes", "//example.com/", "/\\example.com/", "/\nexample.com"])
def test_rejects_invalid_paths_before_sending(path):
    spec = {
        "steps": [
            {"as": "alice", "method": "GET", "path": "/notes"},
            {"as": "bob", "method": "GET", "path": path},
        ],
    }
    with patch("requests.Session.request") as send:
        with pytest.raises(ValueError):
            run_spec(spec, "http://localhost:5000")
    send.assert_not_called()


def test_invalid_expected_outcome_is_rejected_before_sending():
    spec = {"steps": [{"as": "alice", "method": "GET", "path": "/notes/1"}]}
    with patch("requests.Session.request", return_value=Mock(status_code=200, text="example")) as send:
        with pytest.raises((KeyError, ValueError)):
            run_spec(spec, "http://localhost:5000")
    send.assert_not_called()