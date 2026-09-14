from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/sc-skills/scripts/plan_episode_evidence.py"
FIXTURE = ROOT / "tests/fixtures/uat-reader-evidence.json"


def load_module():
    spec = importlib.util.spec_from_file_location("plan_episode_evidence", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = load_module()


class EpisodeEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_bounded_prefix_requires_exact_get_episode_and_cannot_support_claims(self) -> None:
        result = PLANNER.plan_search(self.fixture["search"])
        self.assertFalse(result["candidate_set_complete"])
        self.assertFalse(result["claims_from_bounded_prefix_allowed"])
        self.assertEqual(
            result["required_get_episode_calls"],
            [self.fixture["search"]["episodes"][0]["full_content_lookup"]],
        )
        self.assertEqual(
            result["full_content_candidate_ids"],
            ["def3d6b8-3574-42d7-a840-0ad05c60910c"],
        )

    def test_tampered_or_missing_full_lookup_stays_unresolved(self) -> None:
        payload = copy.deepcopy(self.fixture["search"])
        payload["episodes"][0]["full_content_lookup"]["arguments"]["group_ids"] = ["g_other"]
        result = PLANNER.plan_search(payload)
        self.assertEqual(result["required_get_episode_calls"], [])
        self.assertEqual(
            result["unresolved"],
            [{"uuid": "11111111-1111-4111-8111-111111111111", "reason": "exact_full_content_lookup_missing"}],
        )

    def test_confirmed_typed_record_does_not_invent_a_console_link(self) -> None:
        result = PLANNER.plan_source(self.fixture["confirmed_episode"])
        self.assertIsNone(result["clickable_url"])
        self.assertEqual(result["reason"], "per_record_console_link_not_returned")
        self.assertEqual(result["record_id"], "def3d6b8-3574-42d7-a840-0ad05c60910c")

    def test_https_source_ref_is_still_an_opaque_reference(self) -> None:
        payload = copy.deepcopy(self.fixture["confirmed_episode"])
        payload["episode"]["source_ref"] = "https://example.test/not-a-returned-source-url"
        result = PLANNER.plan_source(payload)
        self.assertIsNone(result["clickable_url"])
        self.assertEqual(result["reason"], "per_record_console_link_not_returned")

    def test_returned_https_link_is_preserved_and_never_marked_permanent(self) -> None:
        payload = copy.deepcopy(self.fixture["confirmed_episode"])
        payload["episode"]["console_source_url"] = "https://console.example.test/source/exact"
        result = PLANNER.plan_source(payload)
        self.assertEqual(result["clickable_url"], "https://console.example.test/source/exact")
        self.assertFalse(result["constructed"])
        self.assertFalse(result["persist_as_permanent"])

    def test_source_tool_top_level_url_is_preserved_exactly(self) -> None:
        payload = {
            "source_url": "https://signed.example.test/object?token=exact",
        }
        result = PLANNER.plan_source(payload)
        self.assertEqual(
            result["clickable_url"],
            "https://signed.example.test/object?token=exact",
        )
        self.assertFalse(result["constructed"])
        self.assertFalse(result["persist_as_permanent"])

    def test_document_metadata_requests_existing_source_tool(self) -> None:
        payload = copy.deepcopy(self.fixture["confirmed_episode"])
        payload["episode"].update({"doc_sha": "a" * 64, "doc_page": 3})
        result = PLANNER.plan_source(payload)
        self.assertEqual(
            result["required_source_lookup"],
            {"tool": "get_source_url", "arguments": {"group_id": "g_company", "doc_sha": "a" * 64, "page": 3}},
        )


if __name__ == "__main__":
    unittest.main()
