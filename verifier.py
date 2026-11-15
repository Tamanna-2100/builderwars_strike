import json
from urllib.parse import urlsplit

import requests

ROLES = {
    "alice": "alice-token",
    "alice-token": "alice-token",
    "bob": "bob-token",
    "bob-token": "bob-token",
    "anon": None,
    "none": None,
}


def _validate_spec_and_url(spec, base_url, review_mode=False):
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

    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")

    steps = spec["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("spec must contain at least one step")

    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("step must be a dict")
        path = step["path"]
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or path.startswith("//")
            or "\\" in path
            or any(ord(character) < 32 or ord(character) == 127 for character in path)
        ):
            raise ValueError("step paths must be local absolute paths")
        if step["as"] not in ROLES:
            raise ValueError("unknown role")
        method = step.get("method")
        if not isinstance(method, str) or not method:
            raise ValueError("invalid method")
        if review_mode:
            if method != "GET" or "body" in step:
                raise ValueError("reviewed spec only allows GET steps without body")

    expected = spec["expected_outcome"]
    if (
        not isinstance(expected, dict)
        or type(expected.get("status")) is not int
        or not isinstance(expected.get("body_contains"), str)
    ):
        raise ValueError("invalid expected_outcome")


def run_spec(spec, base_url):
    _validate_spec_and_url(spec, base_url, review_mode=False)
    steps = spec["steps"]
    expected = spec["expected_outcome"]

    with requests.Session() as session:
        session.trust_env = False
        for step in steps:
            token = ROLES[step["as"]]
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

    return {
        "confirmed": response.status_code == expected["status"]
        and expected["body_contains"] in response.text,
        "request": request,
        "response": {"status": response.status_code, "body": response.text},
    }


def run_reviewed_spec(spec, base_url):
    _validate_spec_and_url(spec, base_url, review_mode=True)
    print(json.dumps(spec, indent=2))
    decision = input("Approve spec execution? Type 'approve' to continue: ").strip().lower()
    if decision != "approve":
        return None
    return run_spec(spec, base_url)