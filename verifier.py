import json
from urllib.parse import urlsplit

import requests


def run_reviewed_spec(spec, base_url):
    try:
        snapshot = json.loads(json.dumps(spec, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError("spec must contain JSON data") from error

    fields = {"id", "title", "vuln_type", "file", "steps", "expected_outcome"}
    if not isinstance(snapshot, dict) or set(snapshot) != fields:
        raise ValueError("invalid TestSpec fields")
    if any(not isinstance(snapshot[field], str) or not snapshot[field] for field in ("id", "title", "vuln_type", "file")):
        raise ValueError("TestSpec identifiers must be nonempty strings")
    steps = snapshot["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("spec must contain at least one step")
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"as", "method", "path"}:
            raise ValueError("invalid read-only step fields")
        if step["as"] not in ("alice", "bob", "anon") or step["method"] not in ("GET", "HEAD"):
            raise ValueError("invalid role or read-only method")
        if not isinstance(step["path"], str) or not step["path"].startswith("/") or step["path"].startswith("//") or "\\" in step["path"] or any(ord(character) < 32 or ord(character) == 127 for character in step["path"]):
            raise ValueError("step paths must be local absolute paths")
    expected = snapshot["expected_outcome"]
    if not isinstance(expected, dict) or set(expected) != {"status", "body_contains"}:
        raise ValueError("invalid expected outcome")
    if type(expected["status"]) is not int or not 100 <= expected["status"] <= 599 or not isinstance(expected["body_contains"], str):
        raise ValueError("invalid expected outcome values")

    print(json.dumps({"base_url": base_url, "spec": snapshot}, indent=2))
    if input('Type "approve" to run this test: ').strip() != "approve":
        return None
    return run_spec(snapshot, base_url)


def run_spec(spec, base_url):
    base = urlsplit(base_url)
    if (
        base.scheme not in {"http", "https"}
        or base.hostname not in {"localhost", "127.0.0.1", "::1"}
        or base.username is not None
        or base.password is not None
        or base.path not in {"", "/"}
        or base.query
        or base.fragment
    ):
        raise ValueError("base_url must be a localhost HTTP origin")
    try:
        base.port
    except ValueError as error:
        raise ValueError("base_url has an invalid port") from error

    roles = {
        "alice": "alice-token",
        "alice-token": "alice-token",
        "bob": "bob-token",
        "bob-token": "bob-token",
        "anon": None,
        "none": None,
    }
    steps = spec["steps"]
    if not steps:
        raise ValueError("spec must contain at least one step")
    for step in steps:
        path = step["path"]
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or path.startswith("//")
            or "\\" in path
            or any(ord(character) < 32 or ord(character) == 127 for character in path)
        ):
            raise ValueError("step paths must be local absolute paths")
        if step["as"] not in roles:
            raise ValueError("unknown role")

    with requests.Session() as session:
        session.trust_env = False
        for step in steps:
            token = roles[step["as"]]
            headers = {"X-Token": token} if token is not None else {}
            request = {
                "method": step["method"],
                "url": base_url.rstrip("/") + step["path"],
                "headers": headers,
            }
            if "body" in step:
                request["body"] = step["body"]
            response = session.request(
                request["method"],
                request["url"],
                headers=headers,
                json=step.get("body"),
                allow_redirects=False,
                timeout=10,
            )

    expected = spec["expected_outcome"]
    return {
        "confirmed": response.status_code == expected["status"]
        and expected["body_contains"] in response.text,
        "request": request,
        "response": {"status": response.status_code, "body": response.text},
    }


if __name__ == "__main__":
    import json
    from unittest.mock import patch

    spec = {
        "steps": [{"as": "alice-token", "method": "GET", "path": "/notes/1"}],
        "expected_outcome": {"status": 200, "body_contains": "example"},
    }
    with patch("requests.Session.request") as send:
        send.return_value.status_code = 200
        send.return_value.text = "example note"
        result = run_spec(spec, "http://localhost:5000")
        assert result["confirmed"]
        assert send.call_args.kwargs["headers"] == {"X-Token": "alice-token"}
        assert send.call_args.kwargs["allow_redirects"] is False
    print(json.dumps(result))