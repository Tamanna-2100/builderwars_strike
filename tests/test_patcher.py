from unittest.mock import Mock
from pathlib import Path

import pytest

import patcher


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "app.py").write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(patcher, "ROOT", tmp_path)
    return tmp_path


def test_creates_review_artifacts(workspace, monkeypatch):
    ask = Mock(return_value={"file": "target/app.py", "content": "new\n", "summary": "Change"})
    monkeypatch.setattr(patcher, "ask", ask)
    result = patcher.patch({"id": "case-1", "file": "target/app.py", "vuln_type": "access"}, "old\n")
    assert (workspace / "target" / "app.py").read_text() == "old\n"
    assert (workspace / "runs/case-1/patched/app.py").read_text() == "new\n"
    assert "-old\n+new\n" in result["diff"]
    assert "pytest.skip" in (workspace / "tests/test_security_case-1.py").read_text()
    assert "target/app.py (access)" in (workspace / "tests/test_security_case-1.py").read_text()
    assert ask.call_args.args[:2] == ("patcher", patcher.SYSTEM)


@pytest.mark.parametrize("identifier,filename", [("../escape", "target/app.py"), ("ok", "../outside.py")])
def test_rejects_invalid_paths(workspace, monkeypatch, identifier, filename):
    ask = Mock()
    monkeypatch.setattr(patcher, "ask", ask)
    with pytest.raises(ValueError):
        patcher.patch({"id": identifier, "file": filename}, "old\n")
    ask.assert_not_called()


def test_rejects_wrong_proposal_file(workspace, monkeypatch):
    monkeypatch.setattr(patcher, "ask", Mock(return_value={"file": "target/other.py", "content": "new", "summary": "Change"}))
    with pytest.raises(ValueError):
        patcher.patch({"id": "case", "file": "target/app.py"}, "old\n")
    assert not (workspace / "runs").exists()


def test_does_not_overwrite_existing_test(workspace, monkeypatch):
    (workspace / "tests").mkdir()
    existing = workspace / "tests/test_security_case.py"
    existing.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(patcher, "ask", Mock(return_value={"file": "target/app.py", "content": "new", "summary": "Change"}))
    with pytest.raises(FileExistsError):
        patcher.patch({"id": "case", "file": "target/app.py"}, "old\n")
    assert existing.read_text() == "existing"
    assert not (workspace / "runs").exists()


def test_rejects_output_directory_symlink(workspace, monkeypatch, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (workspace / "runs").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(patcher, "ask", Mock(return_value={"file": "target/app.py", "content": "new", "summary": "Change"}))
    with pytest.raises(ValueError):
        patcher.patch({"id": "case", "file": "target/app.py"}, "old\n")
    assert not list(outside.iterdir())


def test_failed_test_template_write_does_not_leave_patch(workspace, monkeypatch):
    monkeypatch.setattr(patcher, "ask", Mock(return_value={"file": "target/app.py", "content": "new\n", "summary": "Change"}))
    original_open = Path.open

    def failing_open(path, *args, **kwargs):
        if path.name == "test_security_case.py":
            raise OSError("write failed")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    with pytest.raises(OSError, match="write failed"):
        patcher.patch({"id": "case", "file": "target/app.py"}, "old\n")
    assert not (workspace / "runs/case/patched/app.py").exists()


def test_diff_separates_lines_without_trailing_newlines(workspace, monkeypatch):
    (workspace / "target/app.py").write_text("old", encoding="utf-8")
    monkeypatch.setattr(patcher, "ask", Mock(return_value={"file": "target/app.py", "content": "new", "summary": "Change"}))
    result = patcher.patch({"id": "case", "file": "target/app.py"}, "old")
    assert "-old\n" in result["diff"]
    assert "+new\n" in result["diff"]
    assert "\\ No newline at end of file" in result["diff"]