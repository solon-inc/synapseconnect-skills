import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/sc-skills/skills"
WRITE_RESULT = ROOT / "plugins/sc-skills/references/write-result.md"


class WriteResultDocumentContractTest(unittest.TestCase):
    def test_reference_covers_async_add_memory_outcomes(self) -> None:
        content = WRITE_RESULT.read_text(encoding="utf-8")
        for term in ("`queued`", "`job_id`", "get_ingest_status", "`awaiting_approval`",
                     "wait_seconds=30", "`episode_uuid`", "`nothing_extracted`",
                     "同じ `ingest_key`", "get_episode(uuid)"):
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_every_writer_skill_treats_queued_as_not_failed(self) -> None:
        for name in ("save-synapse", "synapse-request", "synapse-progress",
                     "synapse-share", "meeting-synapse", "news-synapse"):
            with self.subTest(skill=name):
                content = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("`queued`", content)
                self.assertIn("失敗ではない", content)

    def test_share_waits_for_episode_uuid_before_chat(self) -> None:
        content = (SKILLS / "synapse-share/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("wait_seconds=30", content)
        self.assertIn("get_ingest_status(job_id)", content)
        self.assertIn("Chatwork へ進まない", content)

    def test_load_routes_to_current_search_tools(self) -> None:
        content = (SKILLS / "load-synapse/SKILL.md").read_text(encoding="utf-8")
        for tool in ("search_memory_deep", "explore_from", "list_episodes",
                     "search_nodes", "`as_of`"):
            with self.subTest(tool=tool):
                self.assertIn(tool, content)


if __name__ == "__main__":
    unittest.main()
