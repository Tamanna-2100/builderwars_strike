from unittest.mock import Mock

import pytest

import scanner


@pytest.fixture
def hypothesis():
    return {
        "id": "1",
        "vuln_type": "input handling",
        "file": "target/app.py",
        "route": "/notes",
        "line": 12,
        "reason": "Reads an input parameter",
    }


def test_scan_reads_python_sources(monkeypatch, tmp_path, hypothesis):
    (tmp_path / "app.py").write_text("app source", encoding="utf-8")
    (tmp_path / "seed.py").write_text("seed source", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("not python", encoding="utf-8")
    ask = Mock(return_value=[hypothesis])
    monkeypatch.setattr(scanner, "TARGET_DIR", tmp_path)
    monkeypatch.setattr(scanner, "ask", ask)

    assert scanner.scan() == [hypothesis]
    ask.assert_called_once_with(
        "scanner", scanner.SYSTEM, "File: target/app.py\napp source\n\nFile: target/seed.py\nseed source"
    )


@pytest.mark.parametrize("result", [None, {}, [None], [{}], [1] * 6])
def test_scan_rejects_invalid_responses(monkeypatch, result):
    monkeypatch.setattr(scanner, "ask", Mock(return_value=result))
    with pytest.raises(ValueError, match="Invalid scanner response"):
        scanner.scan()


@pytest.mark.parametrize("field,value", [("id", True), ("id", 1.5), ("line", "12"), ("line", True)])
def test_scan_rejects_invalid_field_types(monkeypatch, hypothesis, field, value):
    hypothesis[field] = value
    monkeypatch.setattr(scanner, "ask", Mock(return_value=[hypothesis]))
    with pytest.raises(ValueError, match="Invalid scanner response"):
        scanner.scan()


def test_scan_accepts_empty_response(monkeypatch):
    monkeypatch.setattr(scanner, "ask", Mock(return_value=[]))
    assert scanner.scan() == []


def test_scan_normalizes_numeric_id(monkeypatch, hypothesis):
    hypothesis["id"] = 1
    monkeypatch.setattr(scanner, "ask", Mock(return_value=[hypothesis]))
    assert scanner.scan()[0]["id"] == "1"
    assert hypothesis["id"] == 1


def test_scan_accepts_many_hypotheses(monkeypatch, hypothesis):
    many = [dict(hypothesis, id=str(i)) for i in range(1, 16)]
    monkeypatch.setattr(scanner, "ask", Mock(return_value=many))
    res = scanner.scan()
    assert len(res) == 15
    assert res[14]["id"] == "15"
