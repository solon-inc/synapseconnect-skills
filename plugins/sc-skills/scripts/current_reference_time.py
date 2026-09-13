"""Emit one timezone-aware timestamp from the host clock for typed-record writers."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def current_reference_time(timezone_name: str, *, now: datetime | None = None) -> str:
    if not timezone_name or timezone_name.strip() != timezone_name:
        raise ValueError("timezone must be one configured IANA name")
    try:
        timezone = ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("configured timezone is unavailable") from exc
    instant = datetime.now(UTC) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware instant")
    return instant.astimezone(timezone).replace(microsecond=0).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timezone", required=True)
    args = parser.parse_args()
    try:
        value = current_reference_time(args.timezone)
    except ValueError as exc:
        parser.exit(2, f"current reference time unavailable: {exc}\n")
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
