import json
import os
from uuid import uuid4

import boto3
from dotenv import load_dotenv

import state_manager


load_dotenv()


def artifact_files(run_id):
    directory = state_manager.run_dir(run_id)
    if not (directory / "state.json").is_file():
        raise FileNotFoundError("run not found")
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if any((directory.joinpath(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts) + 1)):
            continue
        if not path.is_file():
            continue
        if relative.as_posix() == "state.json" or relative.parts[0] in {"evidence", "diffs", "tests"} or path.suffix in {".patch", ".diff"}:
            yield path, relative


def upload_run(run_id):
    bucket = os.environ.get("S3_BUCKET", "").strip()
    if not bucket:
        raise ValueError("S3_BUCKET is required")
    files = list(artifact_files(run_id))
    client = boto3.client("s3")
    keys = []
    for path, relative in files:
        key = f"runs/{run_id}/{relative.as_posix()}"
        client.upload_file(str(path), bucket, key)
        keys.append(key)
    return keys


def combined_patch(run_id):
    state = state_manager.read_state(run_id)
    diffs = []
    for finding in state.get("findings", []):
        patch = finding.get("patch") or {}
        diff = patch.get("diff")
        if isinstance(diff, str) and diff.strip():
            diffs.append(diff.rstrip("\n") + "\n")
    if not diffs:
        raise FileNotFoundError("no patches found")
    return "".join(diffs)


def open_review_pr(run_id):
    state = state_manager.read_state(run_id)
    patch = combined_patch(run_id)
    files = list(artifact_files(run_id))
    fallback = f"/runs/{run_id}/patch"
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repository:
        return {"pr_url": None, "patch_url": fallback, "error": "GitHub is not configured"}
    try:
        from github import Auth, Github

        evidence = [{"id": finding.get("id"), "title": finding.get("title"), "evidence": finding.get("evidence")} for finding in state.get("findings", [])]
        markdown = "# Run evidence\n\n```json\n" + json.dumps(evidence, indent=2, ensure_ascii=False) + "\n```\n"
        with Github(auth=Auth.Token(token)) as client:
            repo = client.get_repo(repository)
            base = os.environ.get("GITHUB_BASE_BRANCH", "").strip() or repo.default_branch
            base_sha = repo.get_branch(base).commit.sha
            branch = f"verity-review/{run_id}-{uuid4().hex[:12]}"
            repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base_sha)
            prefix = f"verity-reviews/{run_id}"
            repo.create_file(f"{prefix}/changes.patch", f"Add patch for {run_id}", patch, branch=branch)
            repo.create_file(f"{prefix}/evidence.md", f"Add evidence for {run_id}", markdown, branch=branch)
            for path, relative in files:
                if relative.parts[0] == "tests" and path.suffix == ".py":
                    repo.create_file(f"{prefix}/{relative.as_posix()}", f"Add test for {run_id}", path.read_text(encoding="utf-8"), branch=branch)
            pull = repo.create_pull(title=f"Review run {run_id}", body="Review the proposed patch, tests, and evidence before applying changes.", head=branch, base=base, draft=True)
        return {"pr_url": pull.html_url, "patch_url": fallback, "error": None}
    except Exception as error:
        return {"pr_url": None, "patch_url": fallback, "error": f"GitHub publishing failed: {type(error).__name__}"}