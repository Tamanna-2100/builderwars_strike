import json
from pathlib import Path

from bedrock_client import ask


SYSTEM = "You are a code inspection assistant. Analyze the provided source code and list API routes, parameter mappings, and input handling patterns. Return ONLY a JSON array of {id,vuln_type,file,route,line,reason}. Max 5."
TARGET_DIR = Path(__file__).resolve().parent / "target"
FIELDS = {"id", "vuln_type", "file", "route", "line", "reason"}


def scan(target_dir=None):
    base_dir = Path(target_dir).resolve() if target_dir else TARGET_DIR
    code = "\n\n".join(
        f"File: target/{path.name}\n{path.read_text(encoding='utf-8')}"
        for path in sorted(base_dir.glob("*.py"))
    )
    result = ask("scanner", SYSTEM, code)
    try:
        if not isinstance(result, list) or len(result) > 5:
            raise ValueError("Expected an array of at most five hypotheses")
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