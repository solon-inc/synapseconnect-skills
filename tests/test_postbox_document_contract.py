import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/sc-skills/skills"


class PostboxDocumentContractTest(unittest.TestCase):
    def test_save_routes_provider_feedback_to_postable_shelf(self) -> None:
        content = (SKILLS / "save-synapse/SKILL.md").read_text(encoding="utf-8")
        for term in ("list_ingest_destinations", "postable", "post_to_shelf",
                     "この会社からはまだ送れません", "add_memory"):
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_help_recommends_post_only_after_ok_and_not_for_user_errors(self) -> None:
        content = (SKILLS / "help-synapse/SKILL.md").read_text(encoding="utf-8")
        for term in ("送るのは OK の後", "権限不足・入力の誤り・回数の上限では勧めない",
                     "SynapseConnect へのご意見", "棚が見えなければ勧めない", "withdraw_post"):
            with self.subTest(term=term):
                self.assertIn(term, content)


if __name__ == "__main__":
    unittest.main()
