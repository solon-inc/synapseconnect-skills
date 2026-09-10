from __future__ import annotations

import importlib.util
import copy
import json
import re
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PAIRS = load_module(
    "count_pairs",
    ROOT / "plugins/sc-skills/skills/synapse-pairs/scripts/count_pairs.py",
)
PERIOD = load_module(
    "filter_period",
    ROOT / "plugins/sc-skills/skills/synapse-team-week/scripts/filter_period.py",
)


class TypedRecordContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = ROOT / "tests/fixtures/typed-record-contract-v2.json"
        cls.episodes = json.loads(fixture.read_text(encoding="utf-8"))["episodes"]

    def test_pair_summary_uses_explicit_ids(self) -> None:
        result = PAIRS.summarize_pairs(self.episodes)
        self.assertEqual(result["requests"], 3)
        self.assertEqual(result["requests_with_progress"], 2)
        self.assertEqual(result["completed_requests"], 1)
        self.assertEqual(result["shares"], 1)
        self.assertEqual(result["shares_with_progress"], 1)
        self.assertEqual(result["median_first_progress_hours"], 1.0)
        self.assertEqual(result["created_at_fallback_intervals"], 0)
        self.assertEqual(
            result["unanswered_request_ids"], ["req-20260917-unanswered"]
        )
        self.assertEqual(result["malformed_typed_records"], 0)

    def test_pair_summary_discloses_created_at_fallback(self) -> None:
        episodes = copy.deepcopy(self.episodes)
        for row in episodes:
            row.pop("reference_time", None)
        result = PAIRS.summarize_pairs(episodes)
        self.assertEqual(result["median_first_progress_hours"], 1.25)
        self.assertEqual(result["created_at_fallback_intervals"], 2)

    def test_parser_accepts_legacy_ascii_colon(self) -> None:
        fields = PAIRS._fields("種別: 進捗\n対象依頼: req-example\n状態: 完了")
        self.assertEqual(fields["対象依頼"], "req-example")
        self.assertEqual(fields["状態"], "完了")

    def test_parser_requires_fields_at_line_start(self) -> None:
        fields = PAIRS._fields(" 種別：依頼\n- 依頼ID：req-example")
        self.assertNotIn("種別", fields)
        self.assertNotIn("依頼ID", fields)

    def test_progress_names_include_status_and_date(self) -> None:
        progress_names = [
            row["name"]
            for row in self.episodes
            if PAIRS._fields(row["body"]).get("種別") == "進捗"
        ]
        pattern = re.compile(
            r"^進捗: .+ — (?:着手|途中|完了|詰まり) — \d{4}-\d{2}-\d{2}$"
        )
        self.assertTrue(progress_names)
        self.assertTrue(all(pattern.match(name) for name in progress_names))

    def test_period_is_inclusive_exclusive_and_timezone_aware(self) -> None:
        result = PERIOD.filter_period(
            self.episodes,
            datetime.fromisoformat("2026-09-17T11:00:00+09:00"),
            datetime.fromisoformat("2026-09-17T14:00:00+09:00"),
        )
        self.assertEqual(len(result["episodes"]), 3)
        self.assertEqual(result["skipped_missing_created_at"], 0)
        self.assertEqual(result["skipped_invalid_created_at"], 0)

    def test_period_rejects_naive_boundaries(self) -> None:
        with self.assertRaises(ValueError):
            PERIOD.filter_period(
                self.episodes,
                datetime.fromisoformat("2026-09-17T11:00:00"),
                datetime.fromisoformat("2026-09-17T14:00:00+09:00"),
            )


if __name__ == "__main__":
    unittest.main()
