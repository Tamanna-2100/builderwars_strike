import shutil
from pathlib import Path
from fastapi.testclient import TestClient

import api
import pipeline
import state_manager


def test_end_to_end_pipeline_and_replay():
    run_id = "e2e_verify_run"
    run_path = state_manager.run_dir(run_id)
    test_file = Path(f"tests/test_security_{run_id}.py")
    if run_path.exists():
        shutil.rmtree(run_path)
    if test_file.exists():
        test_file.unlink()

    try:
        pipeline.run(run_id)
        client = TestClient(api.app)

        # 1. Verify state endpoint
        res = client.get(f"/runs/{run_id}")
        assert res.status_code == 200
        state = res.json()
        assert state["status"] == "done"
        assert state["stats"]["verified"] >= 1
        assert state["stats"]["fixed"] >= 1
        assert len(state["findings"]) >= 1

        # Confirmed finding has explain, severity, and sibling detection
        confirmed = state["findings"][0]
        assert confirmed["verdict"] == "confirmed"
        assert confirmed.get("explain")
        assert confirmed.get("severity") in {"high", "medium", "low"}
        assert "/documents/<int:doc_id>" in confirmed.get("siblings", [])

        # 2. Verify .patch download endpoint
        patch_res = client.get(f"/runs/{run_id}/patch")
        assert patch_res.status_code == 200
        assert "--- a/target/app.py" in patch_res.text

        # 3. Verify live before/after replay endpoint
        replay_res = client.get(f"/runs/{run_id}/replay/{confirmed['id']}")
        assert replay_res.status_code == 200
        replay_data = replay_res.json()
        assert replay_data["before"]["confirmed"] is True
        assert replay_data["after"]["confirmed"] is False
    finally:
        if run_path.exists():
            shutil.rmtree(run_path)
        if test_file.exists():
            test_file.unlink()