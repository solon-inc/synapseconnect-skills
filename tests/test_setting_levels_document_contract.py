import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTING = ROOT / "plugins/sc-ops/skills/setting-synapse"


class SettingLevelsDocumentContractTest(unittest.TestCase):
    def test_lv5_is_recommended_for_both_record_and_read(self) -> None:
        levels = (SETTING / "references/levels.md").read_text(encoding="utf-8")
        self.assertEqual(levels.count("迷ったら **Lv5** がおすすめです。"), 2)
        self.assertEqual(levels.count("**Lv5（おすすめ）**"), 2)
        self.assertNotIn("Lv4（おすすめ）", levels)
        self.assertIn("作業や話題の区切りごとに経緯と結論を1件にまとめて記録する", levels)
        self.assertIn("一般知識だけで答えられる問いでは検索しない", levels)
        skill = (SETTING / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(skill.count("推奨は Lv5"), 2)
        self.assertNotIn("推奨は Lv4", skill)

    def test_base_rules_default_is_lv5_and_does_not_wait(self) -> None:
        rules = (SETTING / "references/base-rules.md").read_text(encoding="utf-8")
        for term in ("Lv5/Lv5 相当の既定形", "記録したら取込を待たない",
                     "記録を受け付けました: <name>", "話題に合うタグで絞って検索する"):
            with self.subTest(term=term):
                self.assertIn(term, rules)

    def test_setup_mentions_shelf_tags(self) -> None:
        skill = (SETTING / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("設定 › 棚 › タグ", skill)


if __name__ == "__main__":
    unittest.main()
