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
                "classification": "organization",
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


if __name__ == "__main__":
    unittest.main()
