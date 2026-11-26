"""SYN-990: load-synapse は、人として話すときの会話の頭で get_ingest_health を 1 回呼び、止まりだけを伝える。"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOAD = ROOT / "plugins" / "sc-skills" / "skills" / "load-synapse" / "SKILL.md"


class IngestHealthDocumentContract(unittest.TestCase):
    def setUp(self):
        self.text = LOAD.read_text(encoding="utf-8")

    def test_called_once_at_the_head_of_a_human_conversation(self):
        self.assertIn("get_ingest_health", self.text)
        self.assertIn("人として話しているときだけ、会話の頭に1回", self.text)

    def test_only_stops_are_told_and_hidden_scopes_are_not_touched(self):
        self.assertIn("`stopped` なら `stopped[].stops[].message` を最初に伝える", self.text)
        self.assertIn("止まりが無ければ何も言わない", self.text)
        self.assertIn("`visible: false` の範囲", self.text)
        self.assertIn("件数（失敗・結果不明・待ち）は聞かれたときに出す", self.text)

    def test_step_zero_comes_before_the_search_steps(self):
        self.assertLess(self.text.index("0. 取り込みの止まりを確かめる"), self.text.index("1. 手がかりを決める"))


if __name__ == "__main__":
    unittest.main()
