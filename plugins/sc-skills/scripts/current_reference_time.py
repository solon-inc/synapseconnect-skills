"""Emit one timezone-aware timestamp from the host clock for typed-record writers.

``--timezone`` is optional since 0.8: when omitted, the OS local timezone
(``datetime.now().astimezone()``) is used.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def current_reference_time(
    timezone_name: str | None = None, *, now: datetime | None = None
) -> str:
    if timezone_name is None:
        timezone = None  # OS local timezone via datetime.astimezone()
    else:
        if not timezone_name or timezone_name.strip() != timezone_name:
            raise ValueError("timezone must be one configured IANA name")
        try:
            timezone = ZoneInfo(timezone_name)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("configured timezone is unavailable") from exc
    instant = datetime.now(UTC) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware instant")
    localized = instant.astimezone(timezone).replace(microsecond=0)
    if localized.utcoffset() is None:
        raise ValueError("OS local timezone is unavailable")
    return localized.isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timezone",
        default=None,
        help="IANA timezone name; omitted = OS local timezone",
    )
    args = parser.parse_args()
    try:
        value = current_reference_time(args.timezone)
    except ValueError as exc:
        parser.exit(2, f"current reference time unavailable: {exc}\n")
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
