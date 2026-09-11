from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RoutingDocumentContractTest(unittest.TestCase):
    def test_specialized_routes_do_not_gain_a_private_duplicate(self) -> None:
        paths = [
            ROOT
            / "plugins/sc-ops/skills/setting-synapse/references/base-rules.md",
            ROOT / "plugins/sc-ops/skills/setting-synapse/SKILL.md",
            ROOT / "plugins/sc-skills/skills/save-synapse/SKILL.md",
        ]
        for path in paths:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn("専門スキル", content)
                self.assertIn("1件だけ", content)
                self.assertIn("プライベート", content)

    def test_generic_save_still_defaults_to_private(self) -> None:
        content = (
            ROOT / "plugins/sc-skills/skills/save-synapse/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("専門スキルによる指定がなければ", content)
        self.assertIn("必ずユーザーのプライベートグループ", content)


if __name__ == "__main__":
    unittest.main()
