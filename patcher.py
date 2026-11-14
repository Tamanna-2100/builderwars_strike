import difflib
import json
import re
from pathlib import Path

from bedrock_client import ask


ROOT = Path(__file__).resolve().parent
SYSTEM = "Propose a minimal defensive code change. Return only a JSON object with file, content, and summary."


def patch(finding, source):
    if not isinstance(finding, dict) or not isinstance(source, str):
        raise ValueError("finding must be an object and source must be a string")
    identifier = finding.get("id")
    filename = finding.get("file")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
        raise ValueError("invalid finding id")
    if not isinstance(filename, str):
        raise ValueError("invalid finding file")
    target = ROOT / "target"
    original = (ROOT / filename).resolve()
    if not target.resolve().is_relative_to(ROOT.resolve()) or not original.is_relative_to(target.resolve()) or original.suffix != ".py" or not original.is_file():
        raise ValueError("finding file must be a Python file under target")
    if original.read_text(encoding="utf-8") != source:
        raise ValueError("source does not match the target file")

    proposal = ask("patcher", SYSTEM, json.dumps({"finding": finding, "source": source}))
    if not isinstance(proposal, dict) or set(proposal) != {"file", "content", "summary"}:
        raise ValueError("invalid patch proposal")
    if proposal["file"] != filename or any(not isinstance(proposal[field], str) for field in ("content", "summary")):
        raise ValueError("invalid patch proposal values")

    relative = original.relative_to(target.resolve())
    patched_root = (ROOT / "runs" / identifier / "patched").resolve()
    if not (ROOT / "runs").resolve().is_relative_to(ROOT.resolve()) or not patched_root.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("invalid patch destination")
    destination = (patched_root / relative).resolve()
    test_path = (ROOT / "tests" / f"test_security_{identifier}.py").resolve()
    if not (ROOT / "tests").resolve().is_relative_to(ROOT.resolve()) or not destination.is_relative_to(patched_root) or not test_path.is_relative_to((ROOT / "tests").resolve()):
        raise ValueError("invalid output path")
    if destination.exists() or test_path.exists():
        raise FileExistsError("patch proposal or regression template already exists")

    diff = "".join(difflib.unified_diff(
        source.splitlines(keepends=True), proposal["content"].splitlines(keepends=True),
        fromfile=filename, tofile=f"runs/{identifier}/patched/{relative.as_posix()}",
    ))
    template = (
        "import pytest\n\n\n"
        "def test_security_regression():\n"
        f"    pytest.skip({('Manual regression test required for finding ' + identifier + ' in ' + filename + ' (' + str(finding.get('vuln_type', 'unspecified')) + ')')!r})\n"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as output:
        output.write(proposal["content"])
    test_path.parent.mkdir(parents=True, exist_ok=True)
    with test_path.open("x", encoding="utf-8") as output:
        output.write(template)
    return {**proposal, "diff": diff, "patched_file": str(destination), "test_file": str(test_path)}