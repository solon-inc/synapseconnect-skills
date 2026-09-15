"""Resolve SynapseConnect shelves for sc-skills from a list_groups response.

Precedence per key: memo overrides > saved file > automatic resolution > defaults.
Reads the list_groups JSON from stdin and prints exactly one JSON object.
Pure Python 3.12, no third-party dependencies, no network.

``team[].name_source`` is one of ``description`` (the shelf's own description),
``group_id_suffix`` (no usable description; label is ``個人棚 …<last 6>``) or
``memo`` (taken from the 設定メモ ``members`` override).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = 1
DEFAULT_SAVED_PATH = ".synapse/shelves.json"
DEFAULT_CONSOLE_URL = "https://console.synapse-connect.ai/console"
DEFAULT_SHARE_DRY_RUN = True
DEFAULT_NEWS_LIMIT_PER_RUN = 5
FALLBACK_TIMEZONE = "Asia/Tokyo"

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "company": ("全社", "全社共有", "全体", "company-wide", "all-hands"),
    "development": ("開発", "開発チーム", "dev"),
    "news": ("ニュース", "news"),
}
# Personal-shelf descriptions that are only a generic default, not a person's name.
GENERIC_PERSONAL_DESCRIPTIONS = ("プライベート", "private", "personal")
GENERIC_PERSONAL_PREFIXES = ("private workspace",)
GROUP_ID_PREFIXES = ("g_", "p_")
ROLES = tuple(ROLE_KEYWORDS)
ABSENT_ALLOWED_ROLES = frozenset({"development"})
MEMO_ROLE_KEYS = frozenset(ROLES)
MEMO_DEFAULT_KEYS = frozenset(
    {"timezone", "console_url", "share_dry_run", "news_limit_per_run"}
)
MEMO_KEYS = MEMO_ROLE_KEYS | MEMO_DEFAULT_KEYS | {"members"}

MEMO_KEY_TABLE = """\
--memo-overrides keys (設定メモ; each key overrides only itself):
  company, development, news   shelf group_id, or the exact list_groups description
                               (a value not starting with g_/p_ is matched by name;
                               no exact match -> ask_user)
  timezone                     IANA name, e.g. Asia/Tokyo (default: OS local timezone)
  console_url                  Console top URL (default: %s)
  share_dry_run                true/false (default: true)
  news_limit_per_run           positive integer (default: %d)
  members                      [{"display_name": "...", "personal_group_id": "p_..."}]
                               replaces the automatic team list (name_source: memo)
""" % (DEFAULT_CONSOLE_URL, DEFAULT_NEWS_LIMIT_PER_RUN)


class ResolveError(ValueError):
    """Raised when the input, overrides or saved file cannot be trusted."""


# --------------------------------------------------------------------------- input


def normalize_rows(payload: Any) -> list[dict[str, Any]]:
    """Accept a bare list or an object carrying the rows under ``groups``."""
    rows = payload
    if isinstance(payload, dict):
        rows = payload.get("groups", payload.get("items"))
    if not isinstance(rows, list):
        raise ResolveError("list_groups input must be a JSON array (or an object with 'groups')")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ResolveError(f"list_groups row {index} must be an object")
        group_id = row.get("group_id")
        if not isinstance(group_id, str) or not group_id.strip():
            raise ResolveError(f"list_groups row {index} must have a non-empty string group_id")
        if group_id in seen:
            raise ResolveError(f"list_groups contains duplicate group_id {group_id!r}")
        seen.add(group_id)
        classification = row.get("classification")
        if not isinstance(classification, str):
            raise ResolveError(f"list_groups row {group_id!r} must have a string classification")
        status = row.get("status", "published")
        if not isinstance(status, str):
            raise ResolveError(f"list_groups row {group_id!r} status must be a string")
        description = row.get("description")
        if description is not None and not isinstance(description, str):
            raise ResolveError(f"list_groups row {group_id!r} description must be a string or null")
        is_owner = row.get("is_owner", False)
        if is_owner is None:
            is_owner = False
        if not isinstance(is_owner, bool):
            raise ResolveError(f"list_groups row {group_id!r} is_owner must be a boolean")
        normalized.append(
            {
                "group_id": group_id,
                "classification": classification,
                "status": status,
                "description": description,
                "is_owner": is_owner,
            }
        )
    return normalized


def _published(row: dict[str, Any]) -> bool:
    return row["status"] == "published"


def _suffix_label(group_id: str) -> str:
    return f"個人棚 …{group_id[-6:]}"


def _candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {"group_id": row["group_id"], "description": row["description"]}


# ------------------------------------------------------------------ automatic rules


def resolve_personal_self(rows: list[dict[str, Any]]) -> dict[str, Any]:
    owned = [r for r in rows if r["classification"] == "personal" and r["is_owner"] is True]
    if len(owned) == 1:
        return {"group_id": owned[0]["group_id"], "status": "resolved"}
    reason = "personal_self_missing" if not owned else "personal_self_ambiguous"
    return {"status": "stop", "reason": reason, "candidates": [_candidate(r) for r in owned]}


def is_generic_personal_description(description: str | None) -> bool:
    text = _normalize_text(description).strip()
    if not text:
        return True
    if text in GENERIC_PERSONAL_DESCRIPTIONS:
        return True
    return any(text.startswith(prefix) for prefix in GENERIC_PERSONAL_PREFIXES)


def resolve_team(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    team: list[dict[str, Any]] = []
    for row in rows:
        if row["classification"] != "personal" or row["is_owner"] or not _published(row):
            continue
        description = (row["description"] or "").strip()
        if description and not is_generic_personal_description(description):
            team.append({"group_id": row["group_id"], "label": description,
                         "name_source": "description"})
        else:
            team.append({"group_id": row["group_id"], "label": _suffix_label(row["group_id"]),
                         "name_source": "group_id_suffix"})
    return team


def _normalize_text(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").casefold()


def _keyword_matches(keyword: str, text: str) -> bool:
    """ASCII keywords match on word boundaries; Japanese keywords match as substrings."""
    needle = _normalize_text(keyword)
    if needle.isascii():
        return re.search(rf"(?<![0-9a-z]){re.escape(needle)}(?![0-9a-z])", text) is not None
    return needle in text


def matched_roles(description: str | None) -> set[str]:
    text = _normalize_text(description)
    if not text:
        return set()
    return {
        role
        for role, keywords in ROLE_KEYWORDS.items()
        if any(_keyword_matches(keyword, text) for keyword in keywords)
    }


def resolve_roles_auto(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    organizational = [
        r for r in rows if r["classification"] == "organizational" and _published(r)
    ]
    matches = {role: [] for role in ROLES}
    ambiguous_rows: set[str] = set()
    for row in organizational:
        roles = matched_roles(row["description"])
        if len(roles) > 1:
            ambiguous_rows.add(row["group_id"])
        for role in roles:
            matches[role].append(row)
    result: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        candidates = matches[role]
        unambiguous = [r for r in candidates if r["group_id"] not in ambiguous_rows]
        if len(candidates) == 1 and len(unambiguous) == 1:
            result[role] = {"group_id": candidates[0]["group_id"], "status": "resolved",
                            "source": "auto"}
        elif not candidates and role in ABSENT_ALLOWED_ROLES:
            result[role] = {"status": "absent"}
        else:
            result[role] = {"status": "ask_user",
                            "candidates": [_candidate(r) for r in candidates]}
    return result


# ------------------------------------------------------------------------ overrides


def load_saved(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolveError(f"saved file {path} is unreadable: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("roles"), dict):
        raise ResolveError(f"saved file {path} must be an object with a 'roles' object")
    roles: dict[str, str] = {}
    for role, group_id in payload["roles"].items():
        if role not in ROLES:
            raise ResolveError(f"saved file {path} has unknown role {role!r}")
        if not isinstance(group_id, str) or not group_id.strip():
            raise ResolveError(f"saved file {path} role {role!r} must be a non-empty string")
        roles[role] = group_id
    return roles


def parse_memo_overrides(text: str | None) -> dict[str, Any]:
    if text is None or not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResolveError(f"--memo-overrides is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResolveError("--memo-overrides must be a JSON object")
    unknown = sorted(set(payload) - MEMO_KEYS)
    if unknown:
        raise ResolveError(f"--memo-overrides has unknown keys: {', '.join(unknown)}")
    memo: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if key in MEMO_ROLE_KEYS or key in {"timezone", "console_url"}:
            if not isinstance(value, str) or not value.strip():
                raise ResolveError(f"--memo-overrides {key} must be a non-empty string")
            memo[key] = value.strip()
        elif key == "share_dry_run":
            if not isinstance(value, bool):
                raise ResolveError("--memo-overrides share_dry_run must be a boolean")
            memo[key] = value
        elif key == "news_limit_per_run":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ResolveError("--memo-overrides news_limit_per_run must be a positive integer")
            memo[key] = value
        elif key == "members":
            if not isinstance(value, list):
                raise ResolveError("--memo-overrides members must be an array")
            members: list[dict[str, str]] = []
            for index, member in enumerate(value):
                if not isinstance(member, dict):
                    raise ResolveError(f"--memo-overrides members[{index}] must be an object")
                name = member.get("display_name")
                group_id = member.get("personal_group_id")
                if not isinstance(name, str) or not name.strip():
                    raise ResolveError(f"--memo-overrides members[{index}].display_name is required")
                if not isinstance(group_id, str) or not group_id.strip():
                    raise ResolveError(
                        f"--memo-overrides members[{index}].personal_group_id is required"
                    )
                members.append({"display_name": name.strip(), "personal_group_id": group_id.strip()})
            memo[key] = members
    return memo


def parse_save_choice(text: str | None) -> tuple[str, str] | None:
    if text is None:
        return None
    role, sep, group_id = text.partition("=")
    role, group_id = role.strip(), group_id.strip()
    if not sep or role not in ROLES or not group_id:
        raise ResolveError("--save-choice must be <company|development|news>=<group_id>")
    return role, group_id


def write_saved(path: Path, roles: dict[str, str], *, now: datetime | None = None) -> None:
    resolved_at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    payload = {"version": VERSION, "roles": dict(sorted(roles.items())), "resolved_at": resolved_at}
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# --------------------------------------------------------------------------- defaults


def detect_os_timezone(*, env: dict[str, str] | None = None) -> str:
    """Return the IANA name of the OS local timezone, falling back to Asia/Tokyo."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    environ = os.environ if env is None else env
    candidates: list[str] = []
    tz_env = environ.get("TZ", "").strip().lstrip(":")
    if tz_env:
        candidates.append(tz_env)
    try:
        link = Path("/etc/localtime").resolve()
        parts = link.parts
        if "zoneinfo" in parts:
            candidates.append("/".join(parts[parts.index("zoneinfo") + 1:]))
    except OSError:
        pass
    try:
        candidates.append(Path("/etc/timezone").read_text(encoding="utf-8").strip())
    except OSError:
        pass
    for name in candidates:
        if not name or "/" not in name and name.upper() != "UTC":
            continue
        try:
            ZoneInfo(name)
        except (ValueError, ZoneInfoNotFoundError, OSError):
            continue
        return name
    return FALLBACK_TIMEZONE


def build_defaults(memo: dict[str, Any], *, os_timezone: str | None = None) -> dict[str, Any]:
    return {
        "console_url": memo.get("console_url", DEFAULT_CONSOLE_URL),
        "share_dry_run": memo.get("share_dry_run", DEFAULT_SHARE_DRY_RUN),
        "news_limit_per_run": memo.get("news_limit_per_run", DEFAULT_NEWS_LIMIT_PER_RUN),
        "timezone": memo.get("timezone") or os_timezone or detect_os_timezone(),
    }


# ---------------------------------------------------------------------------- resolve


def resolve(
    rows: list[dict[str, Any]],
    *,
    memo: dict[str, Any] | None = None,
    saved: dict[str, str] | None = None,
    os_timezone: str | None = None,
) -> dict[str, Any]:
    memo = memo or {}
    saved = saved or {}
    listed = {row["group_id"]: row for row in rows}

    personal_self = resolve_personal_self(rows)
    if "members" in memo:
        team = [
            {"group_id": m["personal_group_id"], "label": m["display_name"], "name_source": "memo"}
            for m in memo["members"]
        ]
    else:
        team = resolve_team(rows)

    auto_roles = resolve_roles_auto(rows)

    def auto_candidates(role: str) -> list[dict[str, Any]]:
        auto = auto_roles[role]
        if auto["status"] == "resolved":
            return [_candidate(listed[auto["group_id"]])]
        return list(auto.get("candidates", []))

    roles: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        if role in memo:
            value = memo[role]
            if value.startswith(GROUP_ID_PREFIXES):
                roles[role] = {"group_id": value, "status": "resolved", "source": "memo",
                               "visible_in_list_groups": value in listed}
                continue
            # A shelf given by name: exact match against list_groups description.
            by_name = [r for r in rows if (r["description"] or "").strip() == value]
            if len(by_name) == 1:
                roles[role] = {"group_id": by_name[0]["group_id"], "status": "resolved",
                               "source": "memo", "memo_name": value,
                               "visible_in_list_groups": True}
            else:
                roles[role] = {"status": "ask_user", "candidates": auto_candidates(role),
                               "reason": "memo_name_unresolved", "memo_name": value}
            continue
        saved_id = saved.get(role)
        if saved_id is not None:
            row = listed.get(saved_id)
            if row is None:
                reason = "saved_group_missing"
            elif not _published(row) or row["classification"] != "organizational":
                reason = "saved_group_invalid"
            else:
                roles[role] = {"group_id": saved_id, "status": "resolved", "source": "saved"}
                continue
            roles[role] = {"status": "ask_user", "candidates": auto_candidates(role),
                           "reason": reason, "saved_group_id": saved_id}
            continue
        roles[role] = auto_roles[role]

    return {
        "version": VERSION,
        "personal_self": personal_self,
        "team": team,
        "roles": roles,
        "defaults": build_defaults(memo, os_timezone=os_timezone),
    }


# -------------------------------------------------------------------------------- CLI


class _Parser(argparse.ArgumentParser):
    """argparse errors become ResolveError so stdout still carries one JSON."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise ResolveError(f"invalid arguments: {message}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = _Parser(
        description=__doc__,
        epilog=MEMO_KEY_TABLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--memo-overrides", default=None,
                        help="JSON object from the user's 設定メモ; wins per key")
    parser.add_argument("--saved", default=DEFAULT_SAVED_PATH,
                        help=f"saved choices file (default {DEFAULT_SAVED_PATH})")
    parser.add_argument("--save-choice", default=None, metavar="ROLE=GROUP_ID",
                        help="record one user choice into --saved before resolving")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, stdin=None, stdout=None, stderr=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = _parse_args(argv)
        try:
            payload = json.loads(stdin.read())
        except json.JSONDecodeError as exc:
            raise ResolveError(f"stdin is not valid JSON: {exc}") from exc
        rows = normalize_rows(payload)
        memo = parse_memo_overrides(args.memo_overrides)
        saved_path = Path(args.saved)
        saved = load_saved(saved_path)
        choice = parse_save_choice(args.save_choice)
        if choice is not None:
            role, group_id = choice
            row = next((r for r in rows if r["group_id"] == group_id), None)
            if row is None or not _published(row):
                raise ResolveError(
                    f"--save-choice {role}={group_id}: group is not in this list_groups output"
                )
            if row["classification"] != "organizational":
                raise ResolveError(f"--save-choice {role}={group_id}: group is not organizational")
            saved = {**saved, role: group_id}
            write_saved(saved_path, saved)
        result = resolve(rows, memo=memo, saved=saved)
    except ResolveError as exc:
        print(json.dumps({"version": VERSION, "error": str(exc)}, ensure_ascii=False), file=stdout)
        print(f"resolve_shelves: {exc}", file=stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), file=stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
