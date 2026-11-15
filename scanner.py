import json
from pathlib import Path

from bedrock_client import ask


SYSTEM = "You are a code inspection assistant. Analyze the provided source code and list API routes, parameter mappings, authorization checks, and input handling patterns across all files. Return ONLY a JSON array of {id,vuln_type,file,route,line,reason}."
TARGET_DIR = Path(__file__).resolve().parent / "target"
FIELDS = {"id", "vuln_type", "file", "route", "line", "reason"}


def scan(target_dir=None):
    base_dir = Path(target_dir).resolve() if target_dir else TARGET_DIR
    py_files = sorted(base_dir.glob("*.py"))
    if not py_files:
        py_files = sorted(
            p for p in base_dir.rglob("*.py")
            if not any(part.startswith(".") or part in {"venv", ".venv", "node_modules", "__pycache__"} for part in p.parts)
        )
    code = "\n\n".join(
        f"File: target/{path.name}\n{path.read_text(encoding='utf-8')}"
        if (base_dir == TARGET_DIR or base_dir.name == "target")
        else f"File: {path.relative_to(base_dir).as_posix()}\n{path.read_text(encoding='utf-8')}"
        for path in py_files
    )
    result = ask("scanner", SYSTEM, code)
    try:
        if not isinstance(result, list):
            raise ValueError("Expected an array of hypotheses")
        normalized = []
        for item in result:
            if not isinstance(item, dict) or set(item) != FIELDS:
                raise ValueError("Invalid hypothesis fields")
            item = item.copy()
            if type(item["id"]) is int:
                item["id"] = str(item["id"])
            if any(not isinstance(item[field], str) for field in FIELDS - {"line"}):
                raise ValueError("Hypothesis fields must be strings")
            if type(item["line"]) is not int:
                raise ValueError("Hypothesis line must be an integer")
            normalized.append(item)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid scanner response") from error
    return normalized


if __name__ == "__main__":
    print(json.dumps(scan(), indent=2))