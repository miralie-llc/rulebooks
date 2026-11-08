"""Validate product queue records; no publication or semantic-truth claim."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def validate_records(records, root=ROOT):
    schema = json.loads((root / "schema/work-item.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    items = {}
    for path, item in records:
        validator.validate(item)
        identifier = item["id"]
        if identifier in items:
            raise ValueError(f"Duplicate work ID: {identifier}")
        if path.stem != identifier or path.parent.name != item["queue"]:
            raise ValueError(f"Filename/queue mismatch: {path}")
        if not identifier.startswith(item["queue"] + "-"):
            raise ValueError(f"ID/queue mismatch: {identifier}")
        for evidence in item.get("evidence", []):
            target = (root / evidence["path"]).resolve()
            if Path(evidence["path"]).is_absolute() or not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError(f"Evidence must name an existing repository file: {identifier}")
        items[identifier] = item

    visited, pending = set(), set()

    def visit(identifier):
        if identifier not in items:
            raise ValueError(f"Missing work dependency: {identifier}")
        if identifier in pending:
            raise ValueError(f"Cyclic work dependency: {identifier}")
        if identifier in visited:
            return
        pending.add(identifier)
        for dependency in items[identifier].get("dependsOn", []):
            visit(dependency)
        pending.remove(identifier)
        visited.add(identifier)

    for identifier in items:
        visit(identifier)
    return len(items)


if __name__ == "__main__":
    paths = sorted((ROOT / "work").rglob("*.json"))
    if not paths:
        raise SystemExit("No work records found.")
    count = validate_records([(path, json.loads(path.read_text())) for path in paths])
    print(f"Validated {count} product work records.")
