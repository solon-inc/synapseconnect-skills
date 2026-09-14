"""Filter get_updates metadata by an explicit half-open time range."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


def filter_period(
    episodes: list[dict[str, Any]], since: datetime, until: datetime
) -> dict[str, Any]:
    if since.tzinfo is None or until.tzinfo is None:
        raise ValueError("since and until must include a timezone")
    if until <= since:
        raise ValueError("until must be later than since")

    selected: list[dict[str, Any]] = []
    missing = 0
    invalid = 0
    for episode in episodes:
        raw = episode.get("created_at")
        if not isinstance(raw, str) or not raw.strip():
            missing += 1
            continue
        try:
            created_at = parse_timestamp(raw)
        except ValueError:
            invalid += 1
            continue
        if since <= created_at < until:
            selected.append(episode)
    return {
        "episodes": selected,
        "skipped_missing_created_at": missing,
        "skipped_invalid_created_at": invalid,
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
    parser.add_argument("--since", required=True, help="inclusive ISO 8601 timestamp")
    parser.add_argument("--until", required=True, help="exclusive ISO 8601 timestamp")
    args = parser.parse_args()
    try:
        result = filter_period(
            _load(args.input), parse_timestamp(args.since), parse_timestamp(args.until)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
