from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/sc-skills/scripts/resolve_shelves.py"
FIXTURE = ROOT / "tests/fixtures/list-groups-resolution.json"


def load_module():
    spec = importlib.util.spec_from_file_location("resolve_shelves", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RESOLVER = load_module()


def run_cli(argv: list[str], stdin_text: str) -> tuple[int, dict, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = RESOLVER.main(argv, stdin=io.StringIO(stdin_text), stdout=stdout, stderr=stderr)
    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    payload = json.loads("\n".join(lines))
    return code, payload, stderr.getvalue()


class ResolveShelvesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.rows = copy.deepcopy(self.fixture["list_groups"])
        self.extra = copy.deepcopy(self.fixture["extra_rows"])
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = Path(self.tmp.name) / ".synapse" / "shelves.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def resolve(self, rows=None, **kwargs):
        normalized = RESOLVER.normalize_rows(self.rows if rows is None else rows)
        return RESOLVER.resolve(normalized, os_timezone="Asia/Tokyo", **kwargs)

    # ---- personal_self / team

    def test_own_shelf_is_the_single_owned_personal_row(self) -> None:
        result = self.resolve()
        self.assertEqual(result["personal_self"],
                         {"group_id": "p_1111111111aaaaaa", "status": "resolved"})

    def test_missing_or_ambiguous_own_shelf_stops(self) -> None:
        rows = [row for row in self.rows if not row.get("is_owner")]
        self.assertEqual(self.resolve(rows)["personal_self"],
                         {"status": "stop", "reason": "personal_self_missing", "candidates": []})
        rows = self.rows + [self.extra["second_owner"]]
        result = self.resolve(rows)["personal_self"]
        self.assertEqual(result["status"], "stop")
        self.assertEqual(result["reason"], "personal_self_ambiguous")
        self.assertEqual([c["group_id"] for c in result["candidates"]],
                         ["p_1111111111aaaaaa", "p_owner2"])

    def test_team_is_published_not_owned_personal_rows_with_labels(self) -> None:
        self.assertEqual(self.resolve()["team"], [
            {"group_id": "p_2222222222bbbbbb", "label": "担当B の個人棚",
             "name_source": "description"},
            {"group_id": "p_3333333333cccccc", "label": "個人棚 …cccccc",
             "name_source": "group_id_suffix"},
        ])

    # ---- roles

    def test_keyword_rules_resolve_company_development_news(self) -> None:
        roles = self.resolve()["roles"]
        self.assertEqual(roles["company"],
                         {"group_id": "g_5555555555", "status": "resolved", "source": "auto"})
        self.assertEqual(roles["development"],
                         {"group_id": "g_6666666666", "status": "resolved", "source": "auto"})
        # half-width katakana is NFKC-normalized before matching
        self.assertEqual(roles["news"],
                         {"group_id": "g_7777777777", "status": "resolved", "source": "auto"})

    def test_keyword_match_is_case_insensitive_and_ignores_non_organizational(self) -> None:
        rows = [row for row in self.rows if row["group_id"] != "g_5555555555"]
        rows.append(self.extra["second_company"])
        roles = self.resolve(rows)["roles"]
        self.assertEqual(roles["company"]["group_id"], "g_5555555555b")
        # the library row "資料 全社" and the retired "旧 全社共有" never become candidates
        self.assertEqual(roles["company"]["source"], "auto")

    def test_zero_candidates_ask_user_for_company_and_news_but_allow_absent_development(self) -> None:
        rows = [row for row in self.rows
                if row["group_id"] not in {"g_5555555555", "g_6666666666", "g_7777777777"}]
        roles = self.resolve(rows)["roles"]
        self.assertEqual(roles["company"], {"status": "ask_user", "candidates": []})
        self.assertEqual(roles["news"], {"status": "ask_user", "candidates": []})
        self.assertEqual(roles["development"], {"status": "absent"})

    def test_multiple_candidates_ask_user_with_candidate_list(self) -> None:
        rows = self.rows + [self.extra["second_company"]]
        company = self.resolve(rows)["roles"]["company"]
        self.assertEqual(company["status"], "ask_user")
        self.assertEqual(company["candidates"], [
            {"group_id": "g_5555555555", "description": "全社共有"},
            {"group_id": "g_5555555555b", "description": "Company-Wide notices"},
        ])

    def test_row_matching_two_keyword_groups_is_ambiguous_for_both(self) -> None:
        rows = self.rows + [self.extra["company_and_news"]]
        roles = self.resolve(rows)["roles"]
        for role in ("company", "news"):
            with self.subTest(role=role):
                self.assertEqual(roles[role]["status"], "ask_user")
                self.assertIn("g_ambiguous", [c["group_id"] for c in roles[role]["candidates"]])
        self.assertEqual(roles["development"]["status"], "resolved")

    def test_production_company_description_resolves_via_zentai(self) -> None:
        rows = [row for row in self.rows if row["group_id"] != "g_5555555555"]
        rows.append(self.extra["production_company"])
        company = self.resolve(rows)["roles"]["company"]
        self.assertEqual(company, {"group_id": "g_prod_company", "status": "resolved",
                                   "source": "auto"})
        self.assertEqual(RESOLVER.matched_roles("テナント全体で日常業務から再利用する共有ナレッジ"),
                         {"company"})

    def test_ascii_keywords_match_on_word_boundaries_only(self) -> None:
        rows = self.rows + [self.extra["device_ledger"], self.extra["newsletter_draft"]]
        roles = self.resolve(rows)["roles"]
        self.assertEqual(roles["development"]["group_id"], "g_6666666666")
        self.assertEqual(roles["news"]["group_id"], "g_7777777777")
        self.assertEqual(RESOLVER.matched_roles("Device 管理台帳"), set())
        self.assertEqual(RESOLVER.matched_roles("Newsletter 下書き"), set())
        self.assertEqual(RESOLVER.matched_roles("dev shelf"), {"development"})
        self.assertEqual(RESOLVER.matched_roles("Team news (weekly)"), {"news"})
        self.assertEqual(RESOLVER.matched_roles("company-wide notices"), {"company"})
        self.assertEqual(RESOLVER.matched_roles("all-hands"), {"company"})
        # Japanese keywords keep substring matching
        self.assertEqual(RESOLVER.matched_roles("社内開発メモ"), {"development"})

    def test_generic_personal_descriptions_fall_back_to_suffix_label(self) -> None:
        rows = self.rows + [self.extra["generic_private"], self.extra["generic_workspace"]]
        team = {row["group_id"]: row for row in self.resolve(rows)["team"]}
        self.assertEqual(team["p_generic_private"],
                         {"group_id": "p_generic_private", "label": "個人棚 …rivate",
                          "name_source": "group_id_suffix"})
        self.assertEqual(team["p_generic_wspace"]["name_source"], "group_id_suffix")
        self.assertEqual(team["p_2222222222bbbbbb"]["name_source"], "description")
        for text in ("プライベート", " Private ", "PERSONAL", "private workspace 01", "", None):
            self.assertTrue(RESOLVER.is_generic_personal_description(text), text)
        self.assertFalse(RESOLVER.is_generic_personal_description("担当B の個人棚"))

    def test_is_owner_null_is_treated_as_false(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[1]["is_owner"] = None
        result = self.resolve(rows)
        self.assertEqual(result["personal_self"]["group_id"], "p_1111111111aaaaaa")
        self.assertIn("p_2222222222bbbbbb", [row["group_id"] for row in result["team"]])

    # ---- precedence: memo > saved > auto > default

    def test_memo_override_wins_over_auto_and_default(self) -> None:
        memo = RESOLVER.parse_memo_overrides(json.dumps(self.fixture["memo_overrides"]))
        result = self.resolve(memo=memo)
        self.assertEqual(result["roles"]["company"]["group_id"], "g_memo_company")
        self.assertEqual(result["roles"]["company"]["source"], "memo")
        self.assertFalse(result["roles"]["company"]["visible_in_list_groups"])
        self.assertEqual(result["roles"]["news"]["source"], "memo")
        self.assertEqual(result["roles"]["development"]["source"], "auto")
        self.assertEqual(result["team"], [
            {"group_id": "p_2222222222bbbbbb", "label": "担当B", "name_source": "memo"}
        ])
        self.assertEqual(result["defaults"], {
            "console_url": "https://console.example.test/console",
            "share_dry_run": False,
            "news_limit_per_run": 3,
            "timezone": "Asia/Tokyo",
        })

    def test_defaults_without_memo(self) -> None:
        self.assertEqual(self.resolve()["defaults"], {
            "console_url": "https://console.synapse-connect.ai/console",
            "share_dry_run": True,
            "news_limit_per_run": 5,
            "timezone": "Asia/Tokyo",
        })

    def test_saved_choice_is_reused_and_wins_over_auto(self) -> None:
        rows = self.rows + [self.extra["second_company"]]
        self.assertEqual(self.resolve(rows)["roles"]["company"]["status"], "ask_user")
        RESOLVER.write_saved(self.saved, {"company": "g_5555555555b"})
        saved = RESOLVER.load_saved(self.saved)
        company = self.resolve(rows, saved=saved)["roles"]["company"]
        self.assertEqual(company, {"group_id": "g_5555555555b", "status": "resolved",
                                   "source": "saved"})

    def test_saved_id_missing_from_list_groups_asks_again(self) -> None:
        RESOLVER.write_saved(self.saved, {"company": "g_gone"})
        company = self.resolve(saved=RESOLVER.load_saved(self.saved))["roles"]["company"]
        self.assertEqual(company["status"], "ask_user")
        self.assertEqual(company["reason"], "saved_group_missing")
        self.assertEqual(company["saved_group_id"], "g_gone")
        self.assertEqual([c["group_id"] for c in company["candidates"]], ["g_5555555555"])

    def test_saved_id_that_is_not_a_published_organizational_shelf_asks_again(self) -> None:
        for saved_id in ("p_2222222222bbbbbb", "g_9999999999", "l_0000000000"):
            with self.subTest(saved_id=saved_id):
                RESOLVER.write_saved(self.saved, {"company": saved_id})
                company = self.resolve(saved=RESOLVER.load_saved(self.saved))["roles"]["company"]
                self.assertEqual(company["status"], "ask_user")
                self.assertEqual(company["reason"], "saved_group_invalid")
                self.assertEqual(company["saved_group_id"], saved_id)
                self.assertEqual([c["group_id"] for c in company["candidates"]], ["g_5555555555"])

    def test_memo_shelf_given_by_name_is_resolved_by_exact_description(self) -> None:
        memo = RESOLVER.parse_memo_overrides('{"company": "全社共有", "news": "ニュース"}')
        roles = self.resolve(memo=memo)["roles"]
        self.assertEqual(roles["company"], {"group_id": "g_5555555555", "status": "resolved",
                                            "source": "memo", "memo_name": "全社共有",
                                            "visible_in_list_groups": True})
        # "ニュース" is not the exact description "ﾆｭｰｽ収集": no exact match -> ask_user
        self.assertEqual(roles["news"]["status"], "ask_user")
        self.assertEqual(roles["news"]["reason"], "memo_name_unresolved")
        self.assertEqual([c["group_id"] for c in roles["news"]["candidates"]], ["g_7777777777"])
        # duplicate descriptions are not an exact single match either
        rows = self.rows + [dict(self.extra["second_company"], description="全社共有")]
        self.assertEqual(self.resolve(rows, memo=memo)["roles"]["company"]["status"], "ask_user")

    def test_memo_beats_saved_beats_auto(self) -> None:
        RESOLVER.write_saved(self.saved, {"company": "g_8888888888"})
        memo = RESOLVER.parse_memo_overrides('{"company": "g_memo_company"}')
        company = self.resolve(memo=memo, saved=RESOLVER.load_saved(self.saved))["roles"]["company"]
        self.assertEqual((company["group_id"], company["source"]), ("g_memo_company", "memo"))

    # ---- CLI

    def test_cli_save_choice_writes_private_file_and_resolves_from_it(self) -> None:
        stdin = json.dumps(self.rows + [self.extra["second_company"]])
        code, payload, stderr = run_cli(
            ["--saved", str(self.saved), "--save-choice", "company=g_5555555555b"], stdin)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(payload["roles"]["company"]["source"], "saved")
        stored = json.loads(self.saved.read_text(encoding="utf-8"))
        self.assertEqual(stored["version"], 1)
        self.assertEqual(stored["roles"], {"company": "g_5555555555b"})
        self.assertIn("resolved_at", stored)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.saved.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.saved.parent.stat().st_mode), 0o700)
        code, payload, _ = run_cli(["--saved", str(self.saved)], stdin)
        self.assertEqual(code, 0)
        self.assertEqual(payload["roles"]["company"]["group_id"], "g_5555555555b")

    def test_cli_save_choice_refuses_unknown_or_non_organizational_group(self) -> None:
        for choice in ("company=g_not_listed", "company=p_2222222222bbbbbb", "company", "x=g_5555555555"):
            with self.subTest(choice=choice):
                code, payload, stderr = run_cli(
                    ["--saved", str(self.saved), "--save-choice", choice], json.dumps(self.rows))
                self.assertNotEqual(code, 0)
                self.assertIn("error", payload)
                self.assertTrue(stderr.strip())
                self.assertFalse(self.saved.exists())

    def test_cli_accepts_object_with_groups_and_memo_overrides(self) -> None:
        stdin = json.dumps({"groups": self.rows})
        code, payload, _ = run_cli(
            ["--saved", str(self.saved), "--memo-overrides", '{"news_limit_per_run": 2}'], stdin)
        self.assertEqual(code, 0)
        self.assertEqual(payload["defaults"]["news_limit_per_run"], 2)
        self.assertEqual(payload["personal_self"]["status"], "resolved")

    def test_invalid_input_exits_non_zero_with_reason(self) -> None:
        cases = {
            "not json": "{",
            "not a list": '{"bad": 1}',
            "row without group_id": '[{"classification": "personal"}]',
            "duplicate group_id": json.dumps([self.rows[0], self.rows[0]]),
            "is_owner not boolean": json.dumps(
                [{"group_id": "p_x", "classification": "personal", "is_owner": "yes"}]),
        }
        for name, stdin in cases.items():
            with self.subTest(case=name):
                code, payload, stderr = run_cli(["--saved", str(self.saved)], stdin)
                self.assertNotEqual(code, 0)
                self.assertIn("error", payload)
                self.assertTrue(stderr.strip())
        for memo in ('{"share_dry_run": "no"}', '{"unknown": 1}', '[1]', '{"news_limit_per_run": 0}'):
            with self.subTest(memo=memo):
                code, payload, _ = run_cli(
                    ["--saved", str(self.saved), "--memo-overrides", memo], json.dumps(self.rows))
                self.assertNotEqual(code, 0)
                self.assertIn("error", payload)

    def test_argparse_errors_still_emit_single_error_json(self) -> None:
        for argv in (["--bogus"], ["--save-choice"], ["extra-positional"]):
            with self.subTest(argv=argv):
                code, payload, stderr = run_cli(["--saved", str(self.saved), *argv],
                                                json.dumps(self.rows))
                self.assertEqual(code, 2)
                self.assertEqual(set(payload), {"version", "error"})
                self.assertIn("invalid arguments", payload["error"])
                self.assertTrue(stderr.strip())

    def test_help_documents_memo_keys_and_name_sources(self) -> None:
        for key in ("company", "development", "news", "timezone", "console_url",
                    "share_dry_run", "news_limit_per_run", "members", "display_name",
                    "personal_group_id"):
            self.assertIn(key, RESOLVER.MEMO_KEY_TABLE, key)
        for source in ("description", "group_id_suffix", "memo"):
            self.assertIn(f"``{source}``", RESOLVER.__doc__)

    def test_unreadable_saved_file_is_an_error_not_silently_ignored(self) -> None:
        self.saved.parent.mkdir(parents=True)
        self.saved.write_text('{"roles": {"company": 1}}', encoding="utf-8")
        code, payload, _ = run_cli(["--saved", str(self.saved)], json.dumps(self.rows))
        self.assertNotEqual(code, 0)
        self.assertIn("error", payload)

    def test_os_timezone_detection_falls_back_to_a_valid_iana_name(self) -> None:
        from zoneinfo import ZoneInfo

        self.assertEqual(RESOLVER.detect_os_timezone(env={"TZ": "Europe/London"}), "Europe/London")
        detected = RESOLVER.detect_os_timezone(env={"TZ": "Not/A-Zone"})
        ZoneInfo(detected)  # must not raise


if __name__ == "__main__":
    unittest.main()
