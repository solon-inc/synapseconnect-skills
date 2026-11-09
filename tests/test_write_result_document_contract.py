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
                     "元の `ingest_key`", "`replayed: true`", "get_episode(uuid)"):
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_unknown_outcomes_are_not_reported_as_not_written(self) -> None:
        content = WRITE_RESULT.read_text(encoding="utf-8")
        for term in ("`unknown`", "`written` が `null`", "`retry: false`", "`write_outcome_unknown`",
                     "`llm_timeout`", "`worker_lease_expired`", "`job` が `null`",
                     "`ledger_unavailable`", "`coverage.complete: false`",
                     "`status` の名前だけで「書けなかった」と決めない",
                     "結果不明を「書けなかった」と言わない"):
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_resend_needs_original_key_and_never_uses_absence_as_proof(self) -> None:
        content = WRITE_RESULT.read_text(encoding="utf-8")
        for term in ("送る前に決め", "元の `ingest_key` と同じ本文・棚",
                     "見つからないことは「書かれていない」「送り直して安全」の証拠にならない",
                     "新しい鍵を作らずに止まる", "自動では送らない"):
            with self.subTest(term=term):
                self.assertIn(term, content)
        self.assertNotIn("棚に無いことを確かめたうえで出し直す", content)

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
