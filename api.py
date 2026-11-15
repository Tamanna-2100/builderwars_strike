import os
import re
import threading
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from attacks import attack_idor
import pipeline
from sandbox import start_sandbox
import state_manager
import storage

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ORIGINAL_DIR = Path(__file__).resolve().parent / "target"

app = FastAPI()

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if os.environ.get("FRONTEND_URL"):
    ALLOWED_ORIGINS.extend([o.strip() for o in os.environ["FRONTEND_URL"].split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/config")
def get_config():
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip() or "Tamanna-2100/builderwars_strike"
    has_token = bool(os.environ.get("GITHUB_TOKEN"))
    return {
        "repository": repo,
        "branch": os.environ.get("GITHUB_BASE_BRANCH", "main"),
        "github_configured": has_token,
        "repo_url": f"https://github.com/{repo}",
    }


@app.get("/workspace/files")
def get_workspace_files():
    files = []
    if ORIGINAL_DIR.exists():
        for path in sorted(ORIGINAL_DIR.rglob("*")):
            if path.is_file() and not path.name.startswith(".") and "__pycache__" not in path.parts:
                try:
                    rel = path.relative_to(ORIGINAL_DIR).as_posix()
                    files.append({"name": rel, "content": path.read_text(encoding="utf-8")})
                except Exception:
                    pass
    return {"target_dir": str(ORIGINAL_DIR), "files": files}


@app.post("/workspace/upload")
def upload_workspace_file(payload: dict):
    filename = payload.get("filename", "app.py")
    content = payload.get("content", "")
    safe_name = Path(filename).name
    if not (safe_name.endswith(".py") or safe_name in {"Dockerfile", "requirements.txt"}):
        raise HTTPException(status_code=400, detail="Invalid file type")
    target_path = ORIGINAL_DIR / safe_name
    target_path.write_text(content, encoding="utf-8")
    return {"status": "ok", "filename": safe_name}


@app.post("/scan", status_code=201)
def create_scan(payload: dict = None):
    run_id = uuid4().hex[:12]
    repo_url = payload.get("repo_url") if isinstance(payload, dict) else None
    state_manager.create_run(run_id)
    if repo_url:
        directory = state_manager.run_dir(run_id)
        state = state_manager.read_state(run_id)
        state["repo_url"] = repo_url
        state_manager.write_state(directory, state)
    if "PYTEST_CURRENT_TEST" not in os.environ:
        thread = threading.Thread(target=pipeline.run, args=(run_id, repo_url), daemon=True)
        thread.start()
    return {"run_id": run_id, "status": "pending", "repo_url": repo_url}


@app.get("/runs/latest")
def get_latest_run():
    if not state_manager.RUNS_DIR.exists():
        raise HTTPException(status_code=404, detail="No runs found")
    candidates = [
        d for d in state_manager.RUNS_DIR.iterdir()
        if d.is_dir() and (d / "state.json").exists()
    ]
    if not candidates:
        raise HTTPException(status_code=404, detail="No runs found")
    latest_dir = max(candidates, key=lambda d: (d / "state.json").stat().st_mtime)
    return state_manager.read_state(latest_dir.name)


@app.get("/runs/{run_id}/replay/{finding_id}")
def replay(run_id: str, finding_id: str):
    if not (SAFE_ID.match(run_id) and SAFE_ID.match(finding_id)):
        raise HTTPException(status_code=400, detail="Invalid id")
    try:
        state = state_manager.read_state(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Run not found")

    if finding_id not in {str(f.get("id")) for f in state.get("findings", [])}:
        raise HTTPException(status_code=404, detail="Finding not found")

    patched = Path("runs") / run_id / "patched" / finding_id
    if not patched.exists():
        raise HTTPException(status_code=404, detail="No patched copy for this finding")

    out = {}
    for label, src in (("before", str(ORIGINAL_DIR)), ("after", str(patched))):
        base_url, _, stop = start_sandbox(src)
        try:
            out[label] = attack_idor(base_url)
        finally:
            stop()
    return out


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    try:
        return state_manager.read_state(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Run not found")


def _find_patched_app(run_id: str, finding_id: str) -> Path | None:
    candidate = Path("runs") / run_id / "patched" / finding_id / "app.py"
    if candidate.exists():
        return candidate
    candidate_alt = Path("runs") / run_id / "patched" / "finding-01" / "app.py"
    if candidate_alt.exists():
        return candidate_alt
    patched_root = Path("runs") / run_id / "patched"
    if patched_root.exists():
        for sub in patched_root.glob("*/app.py"):
            return sub
    return None


@app.get("/runs/{run_id}/fixed/{finding_id}/file")
def get_fixed_file(run_id: str, finding_id: str):
    if not (SAFE_ID.match(run_id) and SAFE_ID.match(finding_id)):
        raise HTTPException(status_code=400, detail="Invalid id")
    patched_file = _find_patched_app(run_id, finding_id)
    if not patched_file or not patched_file.exists():
        raise HTTPException(status_code=404, detail="Fixed file not found")
    return Response(
        patched_file.read_text(encoding="utf-8"),
        media_type="text/x-python",
        headers={"Content-Disposition": 'attachment; filename="app.py"'},
    )


@app.get("/runs/{run_id}/fixed/{finding_id}/code")
def get_fixed_code(run_id: str, finding_id: str):
    if not (SAFE_ID.match(run_id) and SAFE_ID.match(finding_id)):
        raise HTTPException(status_code=400, detail="Invalid id")
    patched_file = _find_patched_app(run_id, finding_id)
    if not patched_file or not patched_file.exists():
        raise HTTPException(status_code=404, detail="Fixed file not found")
    return {
        "filename": "app.py",
        "code": patched_file.read_text(encoding="utf-8"),
    }


@app.post("/runs/{run_id}/apply/{finding_id}")
def apply_fixed_code(run_id: str, finding_id: str):
    if not (SAFE_ID.match(run_id) and SAFE_ID.match(finding_id)):
        raise HTTPException(status_code=400, detail="Invalid id")
    patched_file = _find_patched_app(run_id, finding_id)
    if not patched_file or not patched_file.exists():
        raise HTTPException(status_code=404, detail="Fixed file not found")
    target_app = ORIGINAL_DIR / "app.py"
    target_app.write_text(patched_file.read_text(encoding="utf-8"), encoding="utf-8")
    return {"status": "applied", "message": "Fixed code has been applied directly to target/app.py"}


@app.get("/runs/{run_id}/patch")
def get_patch(run_id: str):
    try:
        patch = storage.combined_patch(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Patch not found")
    return Response(
        patch,
        media_type="text/x-diff",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.patch"'},
    )


@app.post("/runs/{run_id}/pr")
def create_pr(run_id: str):
    try:
        return storage.open_review_pr(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Run or patch not found")