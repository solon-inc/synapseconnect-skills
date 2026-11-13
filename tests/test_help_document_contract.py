import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELP = ROOT / "plugins/sc-skills/skills/help-synapse/SKILL.md"


class HelpDocumentContractTest(unittest.TestCase):
    def test_help_reads_provider_distribution_shelves_first(self) -> None:
        content = HELP.read_text(encoding="utf-8")
        for term in ("「SynapseConnect初めての方」", "「SynapseConnect の使い方」",
                     "`shared: true`", "`synapseconnect-admin`", "`limit=1000`",
                     "search_memory_deep", "出どころを添える", "配る棚には書かない",
                     "棚に無いことを、棚にあるかのように言わない"):
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_help_covers_personal_plan_support(self) -> None:
        content = HELP.read_text(encoding="utf-8")
        for term in ("## 個人プランの方", "提供元の窓口へ", "「共有の招待」", "受け入れるまで",
                     "抜ける", "招待には期限がある", "読むだけ", "共有し直せない"):
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_help_contains_no_shelf_ids(self) -> None:
        content = HELP.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"g_[0-9a-f]{32}|sca-dist-[0-9a-f]+|sc_distribution", content))


if __name__ == "__main__":
    unittest.main()
