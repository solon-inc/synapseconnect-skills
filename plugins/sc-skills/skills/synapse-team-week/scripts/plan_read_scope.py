"""Plan team-week reads from explicit configuration and list_groups output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def plan_read_scope(payload: dict[str, Any]) -> dict[str, Any]:
    viewer = payload.get("viewer")
    members = payload.get("members")
    shared = payload.get("shared_groups")
    listed = payload.get("list_groups")
    if not isinstance(viewer, str) or not viewer:
        raise ValueError("viewer must be a non-empty display name")
    if not isinstance(members, list) or not isinstance(shared, list):
        raise ValueError("members and shared_groups must be arrays")
    if not isinstance(listed, list):
        raise ValueError("list_groups must be an array")

    listed_by_id = {
        row.get("group_id"): row
        for row in listed
        if isinstance(row, dict) and isinstance(row.get("group_id"), str)
    }
    configured_personal_ids = [
        member.get("personal_group_id")
        for member in members
        if isinstance(member, dict) and isinstance(member.get("personal_group_id"), str)
    ]
    duplicate_personal_ids = {
        group_id
        for group_id in configured_personal_ids
        if configured_personal_ids.count(group_id) > 1
    }
    readable: list[str] = []
    unavailable_personal: list[str] = []
    unresolved: list[dict[str, str]] = []

    for member in members:
        if not isinstance(member, dict):
            raise ValueError("each member must be an object")
        display_name = member.get("display_name")
        group_id = member.get("personal_group_id")
        if not isinstance(display_name, str) or not isinstance(group_id, str):
            raise ValueError("member display_name and personal_group_id are required")
        if group_id in duplicate_personal_ids:
            if not any(row["group_id"] == group_id for row in unresolved):
                unresolved.append(
                    {"group_id": group_id, "reason": "duplicate_member_mapping"}
                )
            continue
        row = listed_by_id.get(group_id)
        if row is None:
            unavailable_personal.append(group_id)
            continue
        if row.get("classification") != "personal":
            unresolved.append({"group_id": group_id, "reason": "classification_mismatch"})
            continue
        readable.append(group_id)

    missing_shared: list[str] = []
    for group_id in shared:
        if not isinstance(group_id, str):
            raise ValueError("shared group IDs must be strings")
        if group_id in listed_by_id:
            readable.append(group_id)
        else:
            missing_shared.append(group_id)

    own_group_ids = {
        member["personal_group_id"]
        for member in members
        if member["display_name"] == viewer
    }
    other_group_ids = {
        member["personal_group_id"]
        for member in members
        if member["display_name"] != viewer
    }
    readable_set = set(readable)
    unresolved_group_ids = {row["group_id"] for row in unresolved}
    local_ready = (
        bool(own_group_ids)
        and own_group_ids <= readable_set
        and not missing_shared
        and not (own_group_ids & unresolved_group_ids)
    )
    cross_personal_ready = (
        bool(other_group_ids)
        and other_group_ids <= readable_set
        and not (other_group_ids & unresolved_group_ids)
    )
    return {
        "readable_group_ids": sorted(readable_set),
        "unavailable_personal_group_ids": sorted(unavailable_personal),
        "missing_shared_group_ids": sorted(missing_shared),
        "unresolved": unresolved,
        "local_existing_access_ready": local_ready,
        "cross_personal_read_ready": cross_personal_ready,
        "mode": "full_team" if local_ready and cross_personal_ready else "partial_existing_access",
    }


def _load(path: str) -> dict[str, Any]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="-", help="JSON file or - for stdin")
    args = parser.parse_args()
    try:
        result = plan_read_scope(_load(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
