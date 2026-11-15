from unittest.mock import Mock
import sys
from types import SimpleNamespace

import pytest

import state_manager
import storage


@pytest.fixture
def run(monkeypatch, tmp_path):
    monkeypatch.setattr(state_manager, "RUNS_DIR", tmp_path / "runs")
    state_manager.create_run("example")
    return state_manager.run_dir("example")


def test_upload_selected_artifacts(run, monkeypatch):
    (run / "evidence").mkdir()
    (run / "evidence" / "response.json").write_text("{}")
    (run / "tests").mkdir()
    (run / "tests" / "regression.py").write_text("pass")
    (run / "change.patch").write_text("diff")
    (run / "secret.txt").write_text("not an artifact")
    (run / "evidence" / "link.json").symlink_to(run / "secret.txt")
    client = Mock()
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage.boto3, "client", Mock(return_value=client))

    assert storage.upload_run("example") == ["runs/example/change.patch", "runs/example/evidence/response.json", "runs/example/state.json", "runs/example/tests/regression.py"]
    assert client.upload_file.call_count == 4
    assert all(call.args[1] == "test-bucket" for call in client.upload_file.call_args_list)


def test_upload_requires_bucket(run, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage.boto3, "client", Mock())
    with pytest.raises(ValueError, match="S3_BUCKET"):
        storage.upload_run("example")
    storage.boto3.client.assert_not_called()


def test_upload_missing_run(monkeypatch, tmp_path):
    monkeypatch.setattr(state_manager, "RUNS_DIR", tmp_path)
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage.boto3, "client", Mock())
    with pytest.raises(FileNotFoundError):
        storage.upload_run("missing")
    storage.boto3.client.assert_not_called()


def prepare_patch(run):
    state = state_manager.read_state("example")
    state["findings"] = [{"id": "one", "title": "Review", "evidence": {"response": "synthetic"}, "patch": {"diff": "--- old\n+++ new\n"}}]
    state_manager.write_state(run, state)


def test_unconfigured_pr_returns_fallback(run, monkeypatch):
    prepare_patch(run)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert storage.open_review_pr("example") == {"pr_url": None, "patch_url": "/runs/example/patch", "error": "GitHub is not configured"}


def test_pr_publishes_review_artifacts(run, monkeypatch):
    prepare_patch(run)
    (run / "tests").mkdir()
    (run / "tests" / "test_review.py").write_text("pass\n")
    repo = Mock(default_branch="main")
    repo.get_branch.return_value.commit.sha = "base-sha"
    repo.create_pull.return_value.html_url = "https://example.test/pr/1"
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.get_repo.return_value = repo
    github = SimpleNamespace(Auth=SimpleNamespace(Token=Mock(return_value="auth")), Github=Mock(return_value=client))
    monkeypatch.setitem(sys.modules, "github", github)
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.delenv("GITHUB_BASE_BRANCH", raising=False)

    result = storage.open_review_pr("example")
    assert result["pr_url"] == "https://example.test/pr/1"
    assert result["patch_url"] == "/runs/example/patch"
    assert [call.args[0] for call in repo.create_file.call_args_list] == ["verity-reviews/example/changes.patch", "verity-reviews/example/evidence.md", "verity-reviews/example/tests/test_review.py"]
    assert repo.create_pull.call_args.kwargs["draft"] is True


def test_pr_failure_returns_fallback(run, monkeypatch):
    prepare_patch(run)
    github = SimpleNamespace(Auth=SimpleNamespace(Token=Mock(side_effect=RuntimeError("private detail"))), Github=Mock())
    monkeypatch.setitem(sys.modules, "github", github)
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    result = storage.open_review_pr("example")
    assert result == {"pr_url": None, "patch_url": "/runs/example/patch", "error": "GitHub publishing failed: RuntimeError"}


def test_delete_run_s3(monkeypatch):
    client = Mock()
    client.list_objects_v2.return_value = {
        "Contents": [{"Key": "runs/example/state.json"}, {"Key": "runs/example/diff.patch"}]
    }
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage.boto3, "client", Mock(return_value=client))

    deleted = storage.delete_run("example")
    assert deleted == ["runs/example/state.json", "runs/example/diff.patch"]
    client.delete_objects.assert_called_once_with(
        Bucket="test-bucket",
        Delete={"Objects": [{"Key": "runs/example/state.json"}, {"Key": "runs/example/diff.patch"}]},
    )
