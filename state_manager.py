import fcntl
import json
import os
import re
import tempfile
from pathlib import Path


RUNS_DIR = Path(__file__).resolve().parent / "runs"
STATUSES = {"pending", "running", "done", "failed"}
STAGES = ("scan", "verify", "patch", "replay", "test")


def run_dir(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
        raise ValueError("invalid run ID")
    directory = (RUNS_DIR / run_id).resolve()
    if directory.parent != RUNS_DIR.resolve():
        raise ValueError("invalid run directory")
    return directory


def write_state(directory, state):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as output:
            temporary = Path(output.name)
            json.dump(state, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, directory / "state.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_run(run_id):
    directory = run_dir(run_id)
    directory.mkdir(parents=True, exist_ok=False)
    state = {
        "run_id": run_id,
        "status": "pending",
        "stats": {"hypotheses": 0, "verified": 0, "fixed": 0, "discarded": 0},
        "steps": [{"name": name, "status": "pending", "detail": "Not started"} for name in STAGES],
        "findings": [],
    }
    write_state(directory, state)
    return state


def read_state(run_id):
    return json.loads((run_dir(run_id) / "state.json").read_text(encoding="utf-8"))


def update_stage(run_id, name, status, detail):
    if not isinstance(name, str) or not name.strip() or status not in STATUSES:
        raise ValueError("invalid stage name or status")
    if not isinstance(detail, str) or "\n" in detail or "\r" in detail:
        raise ValueError("stage detail must be one line")
    directory = run_dir(run_id)
    if not directory.is_dir():
        raise FileNotFoundError("run not found")
    with (directory / ".state.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read_state(run_id)
        stage = next((step for step in state["steps"] if step["name"] == name), None)
        if stage is None:
            stage = {"name": name}
            state["steps"].append(stage)
        stage.update(status=status, detail=detail)
        write_state(directory, state)
    return state