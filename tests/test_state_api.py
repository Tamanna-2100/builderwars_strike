from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import api
import state_manager


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(state_manager, "RUNS_DIR", tmp_path / "runs")
    with TestClient(api.app) as test_client:
        yield test_client


def test_create_and_read_record(client):
    response = client.post("/scan", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    run_id = response.json()["run_id"]
    state = client.get(f"/runs/{run_id}").json()
    assert state["run_id"] == run_id
    assert state["status"] == "pending"
    assert len(state["steps"]) == 5
    assert all(step["status"] == "pending" for step in state["steps"])


def test_missing_and_invalid_ids(client):
    assert client.get("/runs/missing").status_code == 404
    assert client.get("/runs/invalid.id").status_code == 404


def test_concurrent_stage_updates(client):
    run_id = client.post("/scan").json()["run_id"]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(state_manager.update_stage, run_id, name, "done", "Reviewed") for name in state_manager.STAGES]
        for future in futures:
            future.result()
    state = client.get(f"/runs/{run_id}").json()
    assert all(step["status"] == "done" and step["detail"] == "Reviewed" for step in state["steps"])


@pytest.mark.parametrize("name,status,detail", [("", "done", "ok"), ("scan", "invalid", "ok"), ("scan", "done", "two\nlines")])
def test_invalid_updates(client, name, status, detail):
    run_id = client.post("/scan").json()["run_id"]
    with pytest.raises(ValueError):
        state_manager.update_stage(run_id, name, status, detail)
    assert client.get(f"/runs/{run_id}").json()["steps"][0]["status"] == "pending"


def test_untrusted_origin_does_not_get_cors_header(client):
    response = client.post("/scan", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in response.headers


def test_download_combined_patch(client):
    run_id = client.post("/scan").json()["run_id"]
    directory = state_manager.run_dir(run_id)
    state = state_manager.read_state(run_id)
    state["findings"] = [{"patch": {"diff": "--- a\n+++ b\n"}}, {"patch": {"diff": "--- c\n+++ d"}}]
    state_manager.write_state(directory, state)
    response = client.get(f"/runs/{run_id}/patch")
    assert response.status_code == 200
    assert response.text == "--- a\n+++ b\n--- c\n+++ d\n"
    assert response.headers["content-disposition"] == f'attachment; filename="{run_id}.patch"'


def test_download_missing_patch(client):
    run_id = client.post("/scan").json()["run_id"]
    assert client.get(f"/runs/{run_id}/patch").status_code == 404
    assert client.get("/runs/missing/patch").status_code == 404


def test_delete_run_endpoint(client, monkeypatch):
    run_id = client.post("/scan").json()["run_id"]
    directory = state_manager.run_dir(run_id)
    assert directory.exists()

    monkeypatch.setattr(api.storage, "delete_run", lambda r: ["runs/example/state.json"])
    res = client.delete(f"/runs/{run_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "deleted"
    assert not directory.exists()
