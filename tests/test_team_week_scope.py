from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/sc-skills/skills/synapse-team-week/scripts/plan_read_scope.py"
FIXTURE = ROOT / "tests/fixtures/team-week-visibility.json"


def load_module():
    spec = importlib.util.spec_from_file_location("plan_read_scope", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = load_module()


def load_resolver():
    path = ROOT / "plugins/sc-skills/scripts/resolve_shelves.py"
    spec = importlib.util.spec_from_file_location("resolve_shelves", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TeamWeekScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_existing_access_is_ready_without_cross_personal_read(self) -> None:
        result = PLANNER.plan_read_scope(self.fixture)
        self.assertTrue(result["local_existing_access_ready"])
        self.assertFalse(result["cross_personal_read_ready"])
        self.assertEqual(result["mode"], "partial_existing_access")
        self.assertEqual(
            result["readable_group_ids"], ["g_company", "g_development", "p_self"]
        )
        self.assertEqual(
            result["unavailable_personal_group_ids"],
            ["p_member_b", "p_member_c", "p_member_d"],
        )

    def test_missing_shared_configuration_keeps_partial_reads_not_ready(self) -> None:
        for removed in (("company_group_id",), ("development_group_id",),
                        ("company_group_id", "development_group_id")):
            with self.subTest(removed=removed):
                payload = copy.deepcopy(self.fixture)
                for key in removed:
                    del payload[key]
                result = PLANNER.plan_read_scope(payload)
                self.assertFalse(result["local_existing_access_ready"])
                self.assertEqual(set(result["missing_shared_settings"]), set(removed))
                self.assertIn("p_self", result["readable_group_ids"])

    def test_empty_partial_or_absent_shared_scope_is_not_ready(self) -> None:
        for shared in ([], ["g_company"], ["g_development"], None):
            with self.subTest(shared=shared):
                payload = copy.deepcopy(self.fixture)
                if shared is None:
                    del payload["shared_groups"]
                else:
                    payload["shared_groups"] = shared
                result = PLANNER.plan_read_scope(payload)
                self.assertFalse(result["local_existing_access_ready"])
                self.assertEqual(
                    set(result["omitted_required_shared_group_ids"]),
                    {"g_company", "g_development"} - set(shared or []),
                )
                self.assertEqual(set(result["readable_group_ids"]),
                                 {"p_self"} | set(shared or []))

    def test_required_shared_not_visible_is_unavailable_not_unconfigured(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["list_groups"] = [row for row in payload["list_groups"]
                                  if row["group_id"] != "g_development"]
        result = PLANNER.plan_read_scope(payload)
        self.assertFalse(result["local_existing_access_ready"])
        self.assertEqual(result["missing_shared_group_ids"], ["g_development"])
        self.assertEqual(result["missing_shared_settings"], [])
        self.assertEqual(result["omitted_required_shared_group_ids"], [])

    def test_extra_shared_id_is_not_read_even_when_visible(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["shared_groups"].append("g_extra")
        payload["list_groups"].append({"group_id": "g_extra", "classification": "organizational"})
        result = PLANNER.plan_read_scope(payload)
        self.assertFalse(result["local_existing_access_ready"])
        self.assertNotIn("g_extra", result["readable_group_ids"])
        self.assertEqual(result["unexpected_shared_group_ids"], ["g_extra"])

    def test_duplicate_required_shared_settings_are_not_ready_or_read(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["development_group_id"] = payload["company_group_id"]
        payload["shared_groups"] = ["g_company"]
        result = PLANNER.plan_read_scope(payload)
        self.assertFalse(result["local_existing_access_ready"])
        self.assertEqual(result["readable_group_ids"], ["p_self"])
        self.assertIn({"group_id": "g_company", "reason": "duplicate_shared_mapping"},
                      result["unresolved"])

    def test_declarative_freshness_contract_never_defaults_null_to_24h(self) -> None:
        # This pins the skill instructions, not a live LLM's compliance with them.
        skill = SCRIPT.parents[1].joinpath("SKILL.md").read_text(encoding="utf-8")
        self.assertIn('`stale=true` の場合だけ「同期が止まっている可能性」', skill)
        self.assertIn('`stale=null` は経過時間を表示して「鮮度方針未設定のため判定不能」', skill)
        self.assertIn('`stale=false` は設定された鮮度方針内', skill)
        self.assertIn('明示設定された `86400` 秒（24時間）の方針は維持する', skill)
        self.assertIn('未設定時の既定値にはしない', skill)
        self.assertNotIn('24時間超は「同期が止まっている可能性」', skill)

    def test_cross_personal_acceptance_becomes_full_only_after_all_are_visible(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["list_groups"].extend(
            {
                "group_id": member["personal_group_id"],
                "classification": "personal",
            }
            for member in payload["members"]
            if member["display_name"] != payload["viewer"]
        )
        result = PLANNER.plan_read_scope(payload)
        self.assertTrue(result["local_existing_access_ready"])
        self.assertTrue(result["cross_personal_read_ready"])
        self.assertEqual(result["mode"], "full_team")

    def test_classification_mismatch_is_not_selected_as_personal(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["list_groups"][0]["classification"] = "organization"
        result = PLANNER.plan_read_scope(payload)
        self.assertFalse(result["local_existing_access_ready"])
        self.assertEqual(
            result["unresolved"],
            [{"group_id": "p_self", "reason": "classification_mismatch"}],
        )

    def test_other_classification_mismatch_does_not_block_existing_access(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["list_groups"].append(
            {
                "group_id": "p_member_b",
                "classification": "organizational",
            }
        )
        result = PLANNER.plan_read_scope(payload)
        self.assertTrue(result["local_existing_access_ready"])
        self.assertFalse(result["cross_personal_read_ready"])

    def test_duplicate_personal_id_never_becomes_full_team(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["members"][1]["personal_group_id"] = "p_self"
        result = PLANNER.plan_read_scope(payload)
        self.assertFalse(result["local_existing_access_ready"])
        self.assertFalse(result["cross_personal_read_ready"])
        self.assertEqual(result["mode"], "partial_existing_access")
        self.assertEqual(
            result["unresolved"],
            [{"group_id": "p_self", "reason": "duplicate_member_mapping"}],
        )

    def test_viewer_is_not_added_to_configured_team(self) -> None:
        payload = {
            "viewer": "上田役C",
            "company_group_id": "g_company",
            "development_group_id": "g_development",
            "members": [
                {"display_name": "担当者A", "personal_group_id": "p_member_a"}
            ],
            "shared_groups": ["g_company"],
            "list_groups": [
                {"group_id": "p_member_a", "classification": "personal"},
                {"group_id": "p_viewer_c", "classification": "personal"},
                {"group_id": "g_company", "classification": "organizational"},
            ],
        }

        result = PLANNER.plan_read_scope(payload)

        self.assertEqual(result["configured_member_count"], 1)
        self.assertEqual(result["configured_member_display_names"], ["担当者A"])
        self.assertFalse(result["viewer_is_configured_member"])
        self.assertEqual(result["readable_group_ids"], ["g_company", "p_member_a"])
        self.assertNotIn("p_viewer_c", result["readable_group_ids"])

    def test_auto_members_are_adopted_from_list_groups_when_members_is_omitted(self) -> None:
        for removal in ("delete", "empty", "null"):
            with self.subTest(members=removal):
                payload = copy.deepcopy(self.fixture)
                if removal == "delete":
                    del payload["members"]
                elif removal == "empty":
                    payload["members"] = []
                else:
                    payload["members"] = None
                payload["list_groups"] = [
                    {"group_id": "p_self", "classification": "personal", "status": "published",
                     "description": None, "is_owner": True},
                    {"group_id": "p_member_b", "classification": "personal", "status": "published",
                     "description": "担当B", "is_owner": False},
                    {"group_id": "p_member_c", "classification": "personal", "status": "published",
                     "description": None, "is_owner": False},
                    {"group_id": "p_retired", "classification": "personal", "status": "retired",
                     "description": "退職", "is_owner": False},
                    {"group_id": "g_company", "classification": "organizational", "status": "published"},
                    {"group_id": "g_development", "classification": "organizational", "status": "published"},
                ]
                result = PLANNER.plan_read_scope(payload)
                self.assertEqual(result["members_source"], "auto")
                self.assertEqual(result["viewer_personal_group_id"], "p_self")
                self.assertEqual(result["configured_member_count"], 2)
                self.assertEqual(result["configured_member_display_names"],
                                 ["担当B", "個人棚 …mber_c"])
                self.assertEqual(result["readable_group_ids"],
                                 ["g_company", "g_development", "p_member_b", "p_member_c", "p_self"])
                self.assertNotIn("p_retired", result["readable_group_ids"])
                self.assertTrue(result["local_existing_access_ready"])
                self.assertTrue(result["cross_personal_read_ready"])
                self.assertEqual(result["mode"], "full_team")

    def test_auto_members_from_resolver_team_output(self) -> None:
        # Integration: the resolver's `team` rows are accepted as `members` unchanged.
        resolver = load_resolver()
        listed = [
            {"group_id": "p_self", "classification": "personal", "status": "published",
             "description": None, "is_owner": True},
            {"group_id": "p_member_b", "classification": "personal", "status": "published",
             "description": "担当B", "is_owner": False},
            {"group_id": "g_company", "classification": "organizational", "status": "published",
             "description": "全社共有"},
            {"group_id": "g_development", "classification": "organizational", "status": "published",
             "description": "開発チーム"},
        ]
        resolved = resolver.resolve(resolver.normalize_rows(listed), os_timezone="Asia/Tokyo")
        payload = {
            "viewer": "担当A",
            "company_group_id": resolved["roles"]["company"]["group_id"],
            "development_group_id": resolved["roles"]["development"]["group_id"],
            "members": [
                {"display_name": row["label"], "personal_group_id": row["group_id"]}
                for row in resolved["team"]
            ],
            "shared_groups": ["g_company", "g_development"],
            "list_groups": listed,
        }
        result = PLANNER.plan_read_scope(payload)
        self.assertEqual(result["members_source"], "configured")
        self.assertEqual(result["configured_member_display_names"], ["担当B"])
        self.assertTrue(result["cross_personal_read_ready"])
        # own shelf is not a configured member, so the viewer's shelf is read only in auto mode
        del payload["members"]
        auto = PLANNER.plan_read_scope(payload)
        self.assertEqual(auto["members_source"], "auto")
        self.assertIn("p_self", auto["readable_group_ids"])
        self.assertEqual(auto["mode"], "full_team")

    def test_auto_members_without_own_shelf_is_not_locally_ready(self) -> None:
        payload = copy.deepcopy(self.fixture)
        del payload["members"]
        payload["list_groups"] = [
            {"group_id": "p_member_b", "classification": "personal", "is_owner": False},
            {"group_id": "g_company", "classification": "organizational"},
            {"group_id": "g_development", "classification": "organizational"},
        ]
        result = PLANNER.plan_read_scope(payload)
        self.assertEqual(result["members_source"], "auto")
        self.assertIsNone(result["viewer_personal_group_id"])
        self.assertFalse(result["local_existing_access_ready"])
        self.assertEqual(result["mode"], "partial_existing_access")

    def test_non_array_members_is_still_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["members"] = "担当B"
        with self.assertRaises(ValueError):
            PLANNER.plan_read_scope(payload)


if __name__ == "__main__":
    unittest.main()
