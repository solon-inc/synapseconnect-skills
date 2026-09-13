"""Executable local contract for the declarative synapse-share skill.

This does not call SynapseConnect or Chatwork.  It exercises the operation
ordering and record/pair format that a skill runner must preserve.
"""

from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "share_cases.json"
SKILL_ROOT = Path(__file__).resolve().parents[1]
SHARE_ID = re.compile(r"^share-\d{8}-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*$")
SENSITIVE = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\b(?:authorization\s*:\s*bearer|api[_ -]?key|token|password|passwd|secret)\b\s*[:=]?\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:口座番号|暗証番号)\s*[:：]?\s*\S+", re.IGNORECASE),
)


def has_sensitive_content(request: dict) -> bool:
    values = [
        request.get("title") or "",
        request.get("note") or "",
        request.get("source_ref") or "",
        request.get("attachment") or "",
    ]
    values.extend(request.get("summary") or [])
    return any(pattern.search(value) for value in values for pattern in SENSITIVE)


def build_record(request: dict, recipient: dict) -> dict:
    share_id = request["share_id"]
    if not SHARE_ID.fullmatch(share_id):
        raise ValueError("invalid share id")
    date = request["reference_time"][:10]
    summary = " ".join(request["summary"])
    body = "\n".join(
        (
            "種別：配信",
            f"配信ID：{share_id}",
            f"配信者：{request['sender']}",
            f"宛先：{request['recipient']}",
            f"通知先：{recipient['notification_target']}",
            f"要点：{summary}",
            f"一言：{request.get('note') or 'なし'}",
            f"元記録：{request['source_ref']}",
            f"添付：{request.get('attachment') or 'なし'}",
            f"日時：{request['reference_time']}",
        )
    )
    return {
        "name": f"配信: {request['title']} — {date}",
        "group_id": recipient["group_id"],
        "ingest_key": share_id,
        "source_ref": request["source_ref"],
        "reference_time": request["reference_time"],
        "body": body,
    }


def build_chat_message(
    config: dict,
    request: dict,
    recipient: dict,
    episode_uuid: str,
    *,
    include_to: bool = True,
) -> str:
    prefix = (
        f"[To:{recipient['to_account_id']}]\n"
        if include_to and recipient["notification_target"] == "個人向け"
        else ""
    )
    note = request.get("note") or ""
    bullets = "\n".join(f"・{line}" for line in request["summary"])
    return (
        f"{prefix}[info][title]【共有】{request['title']}[/title]{note}\n"
        f"{bullets}\n"
        f"詳細: {config['console_url']}（記録ID: {episode_uuid}）\n"
        f"配信ID: {request['share_id']}（着手したら「進捗を残す」で「対象配信：」にこのIDを）[/info]"
    )


def redact_to_id(message: str) -> str:
    return re.sub(r"^\[To:[^]]+\]", "[To:<設定済み>]", message)


def run_case(config: dict, request: dict, case: dict) -> dict:
    trace: list[str] = []
    if has_sensitive_content(request):
        return {"status": "sensitive_content", "trace": trace}
    recipient = config["recipients"].get(request["recipient"])
    if recipient is None:
        return {"status": "recipient_not_allowed", "trace": trace}
    if not all((recipient.get("group_id"), recipient.get("room_id"), recipient.get("notification_target"))):
        return {"status": "recipient_not_allowed", "trace": trace}
    if recipient["notification_target"] == "個人向け" and not recipient.get("to_account_id"):
        return {"status": "recipient_not_allowed", "trace": trace}
    required_setting = {
        "個人向け": "company_group_id",
        "全社向け": "company_group_id",
        "チーム向け": "development_group_id",
    }.get(recipient["notification_target"])
    expected_group = config.get(required_setting) if required_setting else None
    if not expected_group or recipient["group_id"] != expected_group:
        return {"status": "shelf_configuration_mismatch", "trace": trace}

    record = build_record(request, recipient)
    preview_message = redact_to_id(
        build_chat_message(config, request, recipient, "<記録後に確定>")
    )
    if not case["confirmed"] and (case["first_use"] or config.get("dry_run", True)):
        return {
            "status": "preview",
            "trace": trace,
            "record": record,
            "preview_message": preview_message,
            "message": preview_message,
        }

    trace.append("add_memory")
    if case["record_outcome"] == "failure":
        return {"status": "record_failed", "trace": trace}
    if case["record_outcome"] == "unknown":
        return {"status": "record_unknown", "trace": trace}

    message = build_chat_message(config, request, recipient, "episode-test-001")
    trace.append(config["chatwork_tool"])
    if case["chat_outcome"] != "success":
        return {
            "status": "chat_failed",
            "trace": trace,
            "record": record,
            "room_id": recipient["room_id"],
            "manual_message": build_chat_message(
                config,
                request,
                recipient,
                "episode-test-001",
                include_to=False,
            ),
        }
    return {
        "status": "sent",
        "trace": trace,
        "record": record,
        "room_id": recipient["room_id"],
        "message": message,
    }


def count_share_progress_pairs(records: list[str]) -> int:
    shares = {
        line.removeprefix("配信ID：")
        for body in records
        for line in body.splitlines()
        if line.startswith("配信ID：")
    }
    progress_targets = {
        line.removeprefix("対象配信：")
        for body in records
        for line in body.splitlines()
        if line.startswith("対象配信：")
    }
    return len(shares & progress_targets)


class ShareContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_operation_and_failure_contracts(self) -> None:
        for case in self.fixture["cases"]:
            with self.subTest(case=case["name"]):
                config = copy.deepcopy(self.fixture["config"])
                config.update(case.get("config_overrides", {}))
                request = copy.deepcopy(self.fixture["base_request"])
                request.update(case.get("request_overrides", {}))
                result = run_case(config, request, case)
                self.assertEqual(case["expected_status"], result["status"])
                self.assertEqual(case["expected_trace"], result["trace"])
                if case.get("expect_manual_message"):
                    self.assertIn("manual_message", result)
                    self.assertNotIn("[To:", result["manual_message"])
                if case.get("expect_manual_to_tag") is False:
                    self.assertNotIn("[To:", result["manual_message"])
                if case.get("expect_preview_placeholders"):
                    self.assertIn("<記録後に確定>", result["message"])
                    self.assertIn("[To:<設定済み>]", result["message"])
                    self.assertNotIn("account-200", result["message"])
                if "expected_group_id" in case:
                    self.assertEqual(case["expected_group_id"], result["record"]["group_id"])
                if "expected_room_id" in case:
                    self.assertEqual(case["expected_room_id"], result["room_id"])
                if case.get("expect_to_tag") is True:
                    self.assertIn("[To:", result["message"])
                if case.get("expect_to_tag") is False and "message" in result:
                    self.assertNotIn("[To:", result["message"])

    def test_notification_shelf_mismatch_or_missing_stops_all_tools(self) -> None:
        case = {"confirmed": True, "first_use": False,
                "record_outcome": "success", "chat_outcome": "success"}
        for kind, setting, expected in (
            ("個人向け", "company_group_id", "g_all"),
            ("全社向け", "company_group_id", "g_all"),
            ("チーム向け", "development_group_id", "g_development"),
        ):
            for variant in ("match", "other_shelf", "prefix", "missing_setting", "unknown_kind"):
                with self.subTest(kind=kind, variant=variant):
                    config = copy.deepcopy(self.fixture["config"])
                    row = config["recipients"]["担当A"]
                    row["notification_target"] = kind
                    row["group_id"] = expected
                    if variant == "other_shelf":
                        row["group_id"] = "g_development" if expected == "g_all" else "g_all"
                    elif variant == "prefix":
                        row["group_id"] = expected + "_other"
                    elif variant == "missing_setting":
                        del config[setting]
                    elif variant == "unknown_kind":
                        row["notification_target"] = "不明"
                    result = run_case(config, self.fixture["base_request"], case)
                    if variant == "match":
                        self.assertEqual(result["status"], "sent")
                        self.assertEqual(result["record"]["group_id"], expected)
                    else:
                        self.assertEqual(result["status"], "shelf_configuration_mismatch")
                        self.assertEqual(result["trace"], [])
                        self.assertNotIn("record", result)

    def test_skill_declares_exact_shelf_binding_before_recording(self) -> None:
        contract = (SKILL_ROOT / "references/share-contract.md").read_text(encoding="utf-8")
        self.assertIn('宛先行の `group_id` が完全一致することを確認する', contract)
        self.assertIn('記録・投稿をせず「設定要確認」で停止する', contract)

    def test_record_has_fixed_machine_readable_fields(self) -> None:
        recipient = self.fixture["config"]["recipients"]["担当A"]
        record = build_record(self.fixture["base_request"], recipient)
        lines = record["body"].splitlines()
        for prefix in ("種別：", "配信ID：", "配信者：", "宛先：", "通知先：", "要点：", "元記録：", "日時："):
            self.assertEqual(1, sum(line.startswith(prefix) for line in lines), prefix)
        self.assertEqual(record["ingest_key"], lines[1].removeprefix("配信ID："))
        self.assertRegex(record["name"], r"^配信: .+ — \d{4}-\d{2}-\d{2}$")

    def test_share_and_progress_form_exactly_one_pair(self) -> None:
        share_id = self.fixture["base_request"]["share_id"]
        records = [
            f"種別：配信\n配信ID：{share_id}",
            f"種別：進捗\n進捗ID：prog-{share_id}-01\n対象配信：{share_id}\n状態：着手",
            "種別：進捗\n進捗ID：prog-other-01\n対象配信：share-20260917-1100-other\n状態：途中",
        ]
        self.assertEqual(1, count_share_progress_pairs(records))

    def test_markdown_references_stay_inside_standalone_skill(self) -> None:
        link = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        for markdown in SKILL_ROOT.rglob("*.md"):
            for target in link.findall(markdown.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (markdown.parent / target).resolve()
                self.assertTrue(resolved.is_relative_to(SKILL_ROOT), target)
                self.assertTrue(resolved.is_file(), target)


if __name__ == "__main__":
    unittest.main()
