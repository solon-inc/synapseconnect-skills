from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/sc-skills/skills/book-synapse/SKILL.md"


class BookReadingDocumentContractTest(unittest.TestCase):
    """SYN-960: 本の読み方(汎用)の 4 段と、残し方・絞り方の約束。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_the_four_steps_are_in_order(self) -> None:
        heads = ["## 1. 必要な情報を決める", "## 2. 本をリストアップする（タグで）",
                 "## 3. 章・節を特定する", "## 4. 原本を読む"]
        positions = [self.text.index(h) for h in heads]
        self.assertEqual(positions, sorted(positions))

    def test_more_than_ten_books_are_narrowed_with_reasons(self) -> None:
        self.assertIn("10 冊を超えたら、優先順位を付けて 10 冊以内に絞る", self.text)
        self.assertIn("外した本と外した理由", self.text)

    def test_the_record_lets_someone_reopen_the_same_pages(self) -> None:
        for needed in ("読んだ本:", "頁", "原本: 確認済み／未確認", "外した本:"):
            with self.subTest(needed=needed):
                self.assertIn(needed, self.text)

    def test_it_uses_only_tools_that_exist(self) -> None:
        tools = set(re.findall(r"`([a-z_]+)\(", self.text))
        known = {"list_tags", "list_groups", "search_memory_deep", "search_episodes",
                 "list_library_documents", "get_library_document", "get_source_url",
                 "get_episode"}  # get_episode(uuid, group_ids): server.py の道具(#12 r1)
        self.assertTrue(tools, "the skill names its tools")
        self.assertLessEqual(tools, known)

    def test_each_company_knows_where_its_defaults_go(self) -> None:
        """各社の既定値を足す場所: 4 段と残し方を段の名前で指し、変えられないことも書く(SYN-960)。"""
        section = self.text.split("## 各社の既定値を足す場所", 1)[1].split("\n## ", 1)[0]
        for name in ("必要な情報を決める", "本をリストアップする", "章・節を特定する", "原本を読む", "残し方"):
            self.assertIn(name, section)
        for item in ("言い換えの語", "本の優先順位", "絞る冊数", "原本を確かめる範囲", "欄の追加"):
            self.assertIn(item, section)
        self.assertIn("差し替えても変わらないこと", section)

    def test_a_parent_tag_also_collects_its_descendants(self) -> None:
        """#12 r1 P2: 親タグから本を挙げるときは path で子孫の label も集め、打ち切りを「無い」としない。"""
        step = self.text.split("## 2.", 1)[1].split("\n## ", 1)[0]
        self.assertIn("子孫のタグも集める", step)
        self.assertIn("`path` に", step)
        self.assertIn("`label`", step)
        self.assertIn("「本が無い」と言わない", step)

    def test_the_library_tools_are_paged_by_cursor_not_by_page(self) -> None:
        """#12 r1 P2: 図書館の 2 つの口は cursor 方式(既定 50・最大 200)。並びは頁の順ではない。"""
        step = self.text.split("## 3.", 1)[1].split("\n## ", 1)[0]
        self.assertIn("next_cursor", step)
        self.assertIn("既定 50 件", step)
        self.assertIn("最大 200", step)
        self.assertIn("並びは頁の順ではない", step)
        self.assertIn("`doc_page`", step)
        self.assertIn("「未確認」", step)

    def test_a_row_without_a_lookup_is_not_given_an_invented_one(self) -> None:
        """#12 r1 P2: full_content_lookup が無い行は content_representation で分け、推測で作らない。"""
        step = self.text.split("## 3.", 1)[1].split("\n## ", 1)[0]
        self.assertIn("`content_representation`", step)
        self.assertIn("`full`", step)
        self.assertIn("推測で作らない", step)

    def test_it_is_generic(self) -> None:
        """会社固有の言い回し・棚の ID を持たない(FCD 固有のものは各社のスキルへ)。"""
        for word in ("FocusClide", "FCD", "lib-[0-9a-f]", "g_[0-9a-f]", "佐藤"):
            with self.subTest(word=word):
                self.assertIsNone(re.search(word, self.text))
        self.assertNotIn("sca-dist-", self.text)


if __name__ == "__main__":
    unittest.main()
