"""Plan exact full-text and source lookups from already fetched MCP responses."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
DOC_SHA_RE = re.compile(r"[0-9a-f]{64}")


def _https_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return None
    return value


def _lookup(row: dict[str, Any]) -> dict[str, Any] | None:
    lookup = row.get("full_content_lookup")
    if not isinstance(lookup, dict) or lookup.get("tool") != "get_episode":
        return None
    arguments = lookup.get("arguments")
    expected = {"uuid": row.get("uuid"), "group_ids": [row.get("group_id")]}
    return lookup if arguments == expected else None


def plan_search(result: dict[str, Any]) -> dict[str, Any]:
    coverage = result.get("coverage") if isinstance(result.get("coverage"), dict) else {}
    meta = coverage.get("meta") if isinstance(coverage.get("meta"), dict) else {}
    rows = result.get("episodes")
    if not isinstance(rows, list):
        raise ValueError("search response episodes must be an array")
    if meta.get("result_semantics") != "candidates" or meta.get("match_is_evidence") is not False:
        raise ValueError("candidate semantics are not explicit")
    reasons = coverage.get("reasons") if isinstance(coverage.get("reasons"), list) else []
    candidate_set_complete = (
        coverage.get("complete") is True
        and coverage.get("truncated") is not True
        and "limit_reached" not in reasons
    )
    required: list[dict[str, Any]] = []
    full_preview_ids: list[str] = []
    unresolved: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("candidate row must be an object")
        uuid = row.get("uuid")
        group_id = row.get("group_id")
        if not isinstance(uuid, str) or not UUID_RE.fullmatch(uuid) or not isinstance(group_id, str):
            raise ValueError("candidate identity is invalid")
        truncated = row.get("content_truncated") is True or row.get("content_representation") == "bounded_prefix"
        if truncated:
            lookup = _lookup(row)
            if lookup is None:
                unresolved.append({"uuid": uuid, "reason": "exact_full_content_lookup_missing"})
            else:
                required.append(lookup)
        elif row.get("content_truncated") is False and row.get("content_representation") == "full":
            full_preview_ids.append(uuid)
        else:
            unresolved.append({"uuid": uuid, "reason": "content_completeness_unknown"})
    return {
        "candidate_set_complete": candidate_set_complete,
        "candidate_count": len(rows),
        "required_get_episode_calls": required,
        "full_content_candidate_ids": full_preview_ids,
        "unresolved": unresolved,
        "claims_from_bounded_prefix_allowed": False,
    }


def plan_source(result: dict[str, Any]) -> dict[str, Any]:
    for key, kind in (
        ("console_source_url", "returned_console_url"),
        ("source_url", "returned_source_url"),
    ):
        url = _https_url(result.get(key))
        if url is not None:
            return {
                "clickable_url": url,
                "kind": kind,
                "persist_as_permanent": False,
                "constructed": False,
            }
    coverage = result.get("coverage") if isinstance(result.get("coverage"), dict) else {}
    episode = result.get("episode") if isinstance(result.get("episode"), dict) else None
    if coverage.get("complete") is not True:
        return {"clickable_url": None, "reason": "source_not_confirmed"}
    if episode is None:
        return {"clickable_url": None, "reason": "episode_not_confirmed"}
    for key, kind in (
        ("console_source_url", "returned_console_url"),
        ("source_url", "returned_source_url"),
    ):
        url = _https_url(episode.get(key))
        if url is not None:
            return {
                "clickable_url": url,
                "kind": kind,
                "persist_as_permanent": False,
                "constructed": False,
            }
    doc_sha = episode.get("doc_sha")
    group_id = episode.get("group_id")
    page = episode.get("doc_page")
    if isinstance(doc_sha, str) and DOC_SHA_RE.fullmatch(doc_sha) and isinstance(group_id, str):
        arguments: dict[str, Any] = {"group_id": group_id, "doc_sha": doc_sha}
        if isinstance(page, int) and page > 0:
            arguments["page"] = page
        return {
            "clickable_url": None,
            "required_source_lookup": {"tool": "get_source_url", "arguments": arguments},
            "reason": "source_lookup_required",
        }
    return {
        "clickable_url": None,
        "reason": "per_record_console_link_not_returned",
        "record_id": episode.get("uuid"),
    }


def _load(path: str) -> dict[str, Any]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("search", "source"))
    parser.add_argument("--input", default="-")
    args = parser.parse_args()
    try:
        result = plan_search(_load(args.input)) if args.mode == "search" else plan_source(_load(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
