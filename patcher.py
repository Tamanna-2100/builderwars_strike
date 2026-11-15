import difflib
import json
import re
from pathlib import Path

from bedrock_client import ask


ROOT = Path(__file__).resolve().parent
SYSTEM = (
    "Propose a minimal defensive code change. Return only a JSON object with file, content, "
    "summary, severity (high, medium, or low), and explain containing story, why_it_matters, "
    "mistake_pattern, prevention_rule, and ai_prompt. Write story and why_it_matters at a "
    "9th-grade reading level, without jargon, in at most two sentences each. Write ai_prompt "
    "as one paragraph of instructions for avoiding this mistake in future code."
)


def validate_proposal(proposal, filename):
    if not isinstance(proposal, dict) or set(proposal) != {"file", "content", "summary", "explain", "severity"}:
        raise ValueError("invalid patch proposal")
    if proposal["file"] != filename or any(not isinstance(proposal[field], str) for field in ("content", "summary")):
        raise ValueError("invalid patch proposal values")
    if proposal["severity"] not in ("high", "medium", "low"):
        raise ValueError("invalid severity")
    explain = proposal["explain"]
    fields = {"story", "why_it_matters", "mistake_pattern", "prevention_rule", "ai_prompt"}
    if not isinstance(explain, dict) or set(explain) != fields or any(not isinstance(explain[field], str) or not explain[field].strip() for field in fields):
        raise ValueError("invalid explanation")
    if any(len([sentence for sentence in re.split(r"(?<=[.!?])\s+", explain[field].strip()) if sentence]) > 2 for field in ("story", "why_it_matters")):
        raise ValueError("explanations must have at most two sentences")
    if "\n" in explain["ai_prompt"] or "\r" in explain["ai_prompt"]:
        raise ValueError("ai_prompt must be one paragraph")


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
    validate_proposal(proposal, filename)

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

    diff_lines = difflib.unified_diff(
        source.splitlines(keepends=True), proposal["content"].splitlines(keepends=True),
        fromfile=filename, tofile=f"runs/{identifier}/patched/{relative.as_posix()}",
    )
    diff = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in diff_lines)
    template = (
        "import pytest\n\n\n"
        "def test_security_regression():\n"
        f"    pytest.skip({('Manual regression test required for finding ' + identifier + ' in ' + filename + ' (' + str(finding.get('vuln_type', 'unspecified')) + ')')!r})\n"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with destination.open("x", encoding="utf-8") as output:
            created.append(destination)
            output.write(proposal["content"])
        test_path.parent.mkdir(parents=True, exist_ok=True)
        with test_path.open("x", encoding="utf-8") as output:
            created.append(test_path)
            output.write(template)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return {**proposal, "diff": diff, "patched_file": str(destination), "test_file": str(test_path)}