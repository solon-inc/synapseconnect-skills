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
                 "list_library_documents", "get_library_document", "get_source_url"}
        self.assertTrue(tools, "the skill names its tools")
        self.assertLessEqual(tools, known)

    def test_it_is_generic(self) -> None:
        """会社固有の言い回し・棚の ID を持たない(FCD 固有のものは各社のスキルへ)。"""
        for word in ("FocusClide", "FCD", "lib-[0-9a-f]", "g_[0-9a-f]", "佐藤"):
            with self.subTest(word=word):
                self.assertIsNone(re.search(word, self.text))
        self.assertNotIn("sca-dist-", self.text)


if __name__ == "__main__":
    unittest.main()
