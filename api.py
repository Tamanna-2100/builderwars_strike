from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

import state_manager
import storage


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.post("/scan", status_code=201)
def create_scan():
    run_id = uuid4().hex
    state_manager.create_run(run_id)
    return {"run_id": run_id, "status": "pending"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    try:
        return state_manager.read_state(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Run not found")


@app.get("/runs/{run_id}/patch")
def get_patch(run_id: str):
    try:
        patch = storage.combined_patch(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Patch not found")
    return Response(patch, media_type="text/x-diff", headers={"Content-Disposition": f'attachment; filename="{run_id}.patch"'})