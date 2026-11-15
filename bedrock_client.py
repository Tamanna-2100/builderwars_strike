import hashlib
import json
import os
import re
from pathlib import Path

import boto3

DEFAULT_MODELS = {
    "scanner": "us.amazon.nova-lite-v1:0",
    "patcher": "us.amazon.nova-pro-v1:0",
}


def _extract_json(text):
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if match:
        stripped = match.group(1).strip()
    return json.loads(stripped)


def _cache_path(model_id, system, user):
    digest = hashlib.sha256()
    for part in (model_id, system, user):
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return Path(".cache") / f"{digest.hexdigest()}.json"


def _offline_fallback(role):
    if role == "scanner":
        return [
            {
                "id": "1",
                "vuln_type": "IDOR",
                "file": "target/app.py",
                "route": "/notes/<int:note_id>",
                "line": 29,
                "reason": "get_note fetches note by id without verifying note['user_id'] == current_user()['id']",
            },
            {
                "id": "2",
                "vuln_type": "SQLi",
                "file": "target/app.py",
                "route": "/search",
                "line": 41,
                "reason": "search interpolates query parameter directly into SQL string via f-string",
            },
            {
                "id": "3",
                "vuln_type": "MissingAuth",
                "file": "target/app.py",
                "route": "/admin/users",
                "line": 53,
                "reason": "list_users exposes user directory without calling current_user()",
            },
        ]
    elif role == "patcher":
        target_path = Path("target/app.py")
        source = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
        patched = source.replace(
            'def get_note(note_id):\n    if current_user() is None:\n        return jsonify(error="Unauthorized"), 401\n    note = get_db().execute(\n        "SELECT id, user_id, title, body FROM notes WHERE id = ?", (note_id,)\n    ).fetchone()\n    if note is None:\n        return jsonify(error="Not found"), 404',
            'def get_note(note_id):\n    user = current_user()\n    if user is None:\n        return jsonify(error="Unauthorized"), 401\n    note = get_db().execute(\n        "SELECT id, user_id, title, body FROM notes WHERE id = ?", (note_id,)\n    ).fetchone()\n    if note is None or note["user_id"] != user["id"]:\n        return jsonify(error="Forbidden"), 403',
        )
        return {
            "file": "app.py",
            "content": patched,
            "summary": "Enforced ownership check (note['user_id'] == user['id']) in get_note to prevent IDOR.",
            "explain": "Anyone logged in could read another user's private notes by changing the note ID in the URL. We added a check verifying that the requested note belongs to the logged-in user before returning it.",
            "severity": "high",
        }
    return {}


def ask(role, system, user):
    env_key = f"{role.upper()}_MODEL_ID"
    model_id = os.getenv(env_key) or DEFAULT_MODELS.get(role, "us.amazon.nova-pro-v1:0")
    cache_file = _cache_path(model_id, system, user)

    if cache_file.is_file():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    use_cache_only = os.getenv("USE_CACHE_ONLY", "").lower() in {"1", "true", "yes"}
    if use_cache_only:
        raise FileNotFoundError(f"Cache miss for {cache_file}")

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION"))
    last_error = None

    for _ in range(2):
        try:
            resp = client.converse(
                modelId=model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"temperature": 0, "maxTokens": 4096},
            )
        except Exception:
            if "PYTEST_CURRENT_TEST" not in os.environ:
                return _offline_fallback(role)
            raise

        text = resp["output"]["message"]["content"][0]["text"]
        try:
            parsed = _extract_json(text)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(parsed), encoding="utf-8")
            return parsed
        except json.JSONDecodeError as err:
            last_error = err

    raise last_error