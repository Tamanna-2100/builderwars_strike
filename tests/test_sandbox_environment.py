from unittest.mock import Mock

import sandbox


def test_sandbox_does_not_inherit_host_environment(monkeypatch, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "seed.py").write_text("pass\n", encoding="utf-8")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "synthetic-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-token")
    monkeypatch.setenv("PYTHONPATH", "/untrusted/path")
    seed = Mock()
    process = Mock()
    process.poll.return_value = None
    launch = Mock(return_value=process)
    monkeypatch.setattr(sandbox.subprocess, "run", seed)
    monkeypatch.setattr(sandbox.subprocess, "Popen", launch)
    monkeypatch.setattr(sandbox.requests, "get", Mock(return_value=Mock(status_code=200)))
    monkeypatch.setattr(sandbox, "get_free_port", Mock(return_value=12345))

    _, temp_dir, stop = sandbox.start_sandbox(str(target))
    try:
        seed_env = seed.call_args.kwargs["env"]
        flask_env = launch.call_args.kwargs["env"]
        assert seed_env == flask_env
        assert set(seed_env) == {"DATABASE", "PORT", "FLASK_APP", "HOME", "TMPDIR", "PATH", "PYTHONNOUSERSITE"}
        assert seed_env["HOME"] == temp_dir
        assert seed_env["DATABASE"] == f"{temp_dir}/notes.db"
        assert "AWS_SECRET_ACCESS_KEY" not in seed_env
        assert "GITHUB_TOKEN" not in seed_env
        assert "PYTHONPATH" not in seed_env
    finally:
        stop()