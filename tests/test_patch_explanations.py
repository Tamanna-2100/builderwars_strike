from copy import deepcopy
from unittest.mock import Mock

import pytest

import patcher


@pytest.fixture
def proposal():
    return {
        "file": "target/app.py",
        "content": "new\n",
        "summary": "Add a check.",
        "severity": "high",
        "explain": {
            "story": "Someone could read another person's note.",
            "why_it_matters": "Private notes could be shared without permission.",
            "mistake_pattern": "Missing ownership check",
            "prevention_rule": "Check ownership before returning a note.",
            "ai_prompt": "Check that each person may read a note before returning it.",
        },
    }


def test_patch_returns_explanation(monkeypatch, tmp_path, proposal):
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "app.py").write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(patcher, "ROOT", tmp_path)
    monkeypatch.setattr(patcher, "ask", Mock(return_value=proposal))
    result = patcher.patch({"id": "case", "file": "target/app.py"}, "old\n")
    assert result["explain"] == proposal["explain"]
    assert result["severity"] == "high"


@pytest.mark.parametrize("field,value", [
    ("severity", "critical"),
    ("explain", None),
    ("explain", {"story": "Missing fields"}),
])
def test_rejects_invalid_explanations(proposal, field, value):
    proposal[field] = value
    with pytest.raises(ValueError):
        patcher.validate_proposal(proposal, "target/app.py")


@pytest.mark.parametrize("field,value", [
    ("story", "One. Two. Three."),
    ("why_it_matters", "One. Two. Three."),
    ("ai_prompt", "First paragraph.\n\nSecond paragraph."),
    ("prevention_rule", ""),
])
def test_rejects_invalid_explanation_content(proposal, field, value):
    invalid = deepcopy(proposal)
    invalid["explain"][field] = value
    with pytest.raises(ValueError):
        patcher.validate_proposal(invalid, "target/app.py")