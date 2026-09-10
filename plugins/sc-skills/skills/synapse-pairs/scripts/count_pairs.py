"""Count typed request/progress/share pairs from already-fetched episodes."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _fields(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in body.splitlines():
        if not raw_line or raw_line[0].isspace():
            continue
        line = raw_line.rstrip()
        separator = "：" if "：" in line else ":" if ":" in line else None
        if separator is None:
            continue
        key, value = line.split(separator, 1)
        key = key.rstrip()
        if key and key not in result:
            result[key] = value.strip()
    return result


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _event_timestamp(episode: dict[str, Any]) -> tuple[datetime | None, bool]:
    reference_time = _timestamp(episode.get("reference_time"))
    if reference_time is not None:
        return reference_time, False
    return _timestamp(episode.get("created_at")), True


def summarize_pairs(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    requests: dict[str, dict[str, Any]] = {}
    shares: dict[str, dict[str, Any]] = {}
    progress: list[tuple[dict[str, str], dict[str, Any]]] = []
    malformed = 0

    for episode in episodes:
        body = episode.get("body", episode.get("episode_body", ""))
        fields = _fields(body if isinstance(body, str) else "")
        kind = fields.get("種別")
        if kind == "依頼" and fields.get("依頼ID"):
            requests.setdefault(fields["依頼ID"], episode)
        elif kind == "配信" and fields.get("配信ID"):
            shares.setdefault(fields["配信ID"], episode)
        elif kind == "進捗" and fields.get("進捗ID"):
            targets = bool(fields.get("対象依頼")) + bool(fields.get("対象配信"))
            if targets == 1:
                progress.append((fields, episode))
            else:
                malformed += 1
        elif kind in {"依頼", "配信", "進捗"}:
            malformed += 1

    request_progress: dict[str, list[tuple[dict[str, str], dict[str, Any]]]] = {}
    share_progress: dict[str, list[tuple[dict[str, str], dict[str, Any]]]] = {}
    for fields, episode in progress:
        request_id = fields.get("対象依頼")
        share_id = fields.get("対象配信")
        if request_id in requests:
            request_progress.setdefault(request_id, []).append((fields, episode))
        elif share_id in shares:
            share_progress.setdefault(share_id, []).append((fields, episode))

    completed = {
        request_id
        for request_id, rows in request_progress.items()
        if any(fields.get("状態") == "完了" for fields, _ in rows)
    }

    first_progress_hours: list[float] = []
    excluded_intervals = 0
    created_at_fallback_intervals = 0
    for request_id, rows in request_progress.items():
        requested_at, request_fallback = _event_timestamp(requests[request_id])
        progress_times = [
            (value, fallback)
            for _, row in rows
            if (event := _event_timestamp(row))[0] is not None
            for value, fallback in [event]
        ]
        if requested_at is None or not progress_times:
            excluded_intervals += 1
            continue
        first_progress_at, progress_fallback = min(progress_times, key=lambda item: item[0])
        delta = first_progress_at - requested_at
        if delta.total_seconds() < 0:
            excluded_intervals += 1
            continue
        if request_fallback or progress_fallback:
            created_at_fallback_intervals += 1
        first_progress_hours.append(delta.total_seconds() / 3600)

    return {
        "requests": len(requests),
        "requests_with_progress": len(request_progress),
        "completed_requests": len(completed),
        "shares": len(shares),
        "shares_with_progress": len(share_progress),
        "median_first_progress_hours": (
            round(statistics.median(first_progress_hours), 3)
            if first_progress_hours
            else None
        ),
        "unanswered_request_ids": sorted(set(requests) - set(request_progress)),
        "malformed_typed_records": malformed,
        "excluded_time_intervals": excluded_intervals,
        "created_at_fallback_intervals": created_at_fallback_intervals,
    }


def _load(path: str) -> list[dict[str, Any]]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(text)
    episodes = value.get("episodes") if isinstance(value, dict) else value
    if not isinstance(episodes, list) or not all(isinstance(row, dict) for row in episodes):
        raise ValueError("input must be a JSON array of episodes or {'episodes': [...]} ")
    return episodes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="-", help="JSON file or - for stdin")
    args = parser.parse_args()
    try:
        result = summarize_pairs(_load(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
