from unittest.mock import Mock, patch

import pytest

from verifier import run_reviewed_spec


@pytest.fixture
def spec():
    return {
        "id": "test-1",
        "title": "Inspect notes",
        "vuln_type": "access",
        "file": "target/app.py",
        "steps": [{"as": "alice", "method": "GET", "path": "/notes/1"}],
        "expected_outcome": {"status": 200, "body_contains": "example"},
    }


def test_reviewed_spec_requires_approval(spec, capsys):
    with patch("builtins.input", return_value="no"), patch("requests.Session.request") as send:
        assert run_reviewed_spec(spec, "http://localhost:5000") is None
    send.assert_not_called()
    assert '"/notes/1"' in capsys.readouterr().out


def test_reviewed_spec_runs_after_approval(spec):
    with patch("builtins.input", return_value="approve"), patch(
        "requests.Session.request", return_value=Mock(status_code=200, text="example")
    ) as send:
        assert run_reviewed_spec(spec, "http://localhost:5000")["confirmed"]
    send.assert_called_once()


@pytest.mark.parametrize("step", [
    {"as": "alice", "method": "POST", "path": "/notes"},
    {"as": "alice", "method": "GET", "path": "/notes", "body": {}},
    {"as": "other", "method": "GET", "path": "/notes"},
    {"as": "alice", "method": "GET", "path": "//example.com"},
])
def test_invalid_steps_are_rejected_before_review(spec, step):
    spec["steps"] = [step]
    with patch("builtins.input") as approve, patch("requests.Session.request") as send:
        with pytest.raises(ValueError):
            run_reviewed_spec(spec, "http://localhost:5000")
    approve.assert_not_called()
    send.assert_not_called()


def test_invalid_schema_is_rejected_before_review(spec):
    spec["expected_outcome"]["status"] = True
    with patch("builtins.input") as approve:
        with pytest.raises(ValueError):
            run_reviewed_spec(spec, "http://localhost:5000")
    approve.assert_not_called()