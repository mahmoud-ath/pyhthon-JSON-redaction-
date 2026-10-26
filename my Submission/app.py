"""Fictional LarchTrace evidence renderer with optional exact-key redaction."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import typing

REDACTED = "[REDACTED]"


def render_value(value: typing.Any) -> typing.Any:
    """Copy nested JSON, sorting object keys and preserving array order and types."""
    if isinstance(value, dict):
        return {key: render_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [render_value(item) for item in value]
    return value


def validate_policy(policy: typing.Any) -> list[str]:
    """Accept exactly {"keys": [distinct nonempty strings]}; values are never echoed."""
    if isinstance(policy, dict) is False or list(policy) != ["keys"]:
        raise ValueError("invalid redaction_policy")
    keys = policy["keys"]
    if isinstance(keys, list) is False:
        raise ValueError("invalid redaction_policy")
    if any(isinstance(key, str) is False or key == "" for key in keys):
        raise ValueError("invalid redaction_policy")
    if len(set(keys)) != len(keys):
        raise ValueError("invalid redaction_policy")
    return list(keys)


def escape_pointer_segment(segment: str) -> str:
    """Escape a JSON Pointer segment: ~ becomes ~0 first, then / becomes ~1."""
    return segment.replace("~", "~0").replace("/", "~1")


def redact_value(
    value: typing.Any,
    keys: list[str],
    current_path: str,
    collected_paths: list[str],
) -> typing.Any:
    """Copy JSON, replacing the whole value of each matching key; record its path."""
    if isinstance(value, dict):
        copied: dict[str, typing.Any] = {}
        for key in sorted(value):
            child_path = f"{current_path}/{escape_pointer_segment(key)}"
            if key in keys:
                copied[key] = REDACTED
                collected_paths.append(child_path)
            else:
                copied[key] = redact_value(value[key], keys, child_path, collected_paths)
        return copied
    if isinstance(value, list):
        return [
            redact_value(item, keys, f"{current_path}/{index}", collected_paths)
            for index, item in enumerate(value)
        ]
    return value


def validate_records(records: typing.Any) -> list[dict[str, typing.Any]]:
    """Validate identity and evidence presence without echoing supplied values."""
    if isinstance(records, list) is False:
        raise ValueError("records must be an array")
    seen: set[str] = set()
    for index, record in enumerate(records):
        if isinstance(record, dict) is False:
            raise ValueError(f"record {index}: expected object")
        identity = record.get("record_id")
        if isinstance(identity, str) is False or identity.strip() == "":
            raise ValueError(f"record {index}: expected nonblank record_id")
        if identity in seen:
            raise ValueError(f"record {index}: duplicate record_id")
        seen.add(identity)
        if "evidence" not in record:
            raise ValueError(f"record {index}: missing evidence")
    return records


def render_evidence(payload: dict[str, typing.Any], arguments: argparse.Namespace) -> dict[str, typing.Any]:
    """Render records; unknown envelope and record fields are ignored."""
    # RC2: a present policy is validated before any record validation.
    policy_keys = validate_policy(payload["redaction_policy"]) if "redaction_policy" in payload else None
    records = validate_records(payload.get("records"))
    ordered = sorted(records, key=lambda record: record["record_id"])
    items: list[dict[str, typing.Any]] = []
    paths: list[str] = []
    for index, record in enumerate(ordered):
        if policy_keys is None:
            evidence = render_value(record["evidence"])
        else:
            evidence = redact_value(record["evidence"], policy_keys, f"/records/{index}/evidence", paths)
        items.append({"record_id": record["record_id"], "evidence": evidence})
    result: dict[str, typing.Any] = {"records": items, "summary": {"records": len(items)}}
    if policy_keys is not None:
        result["redaction"] = {"count": len(paths), "paths": sorted(paths)}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a fictional structured scanner evidence batch.")
    parser.add_argument("--input", default="inputs/primary.json", help="UTF-8 fixture JSON")
    arguments = parser.parse_args()
    try:
        payload = json.loads(pathlib.Path(arguments.input).read_text(encoding="utf-8"))
        if isinstance(payload, dict) is False:
            raise ValueError("input must be a JSON object")
        result = render_evidence(payload, arguments)
        print(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=True))
    except NotImplementedError as error:
        print(str(error), file=sys.stderr)
        return 3
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
