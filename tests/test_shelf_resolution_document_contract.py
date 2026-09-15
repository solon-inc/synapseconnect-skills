from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/sc-skills/skills"
PRECEDENCE = "設定メモ > `.synapse/shelves.json` > `list_groups` の自動解決 > 既定"
RESOLVER_SKILLS = (
    "news-synapse",
    "meeting-synapse",
    "synapse-request",
    "synapse-progress",
    "synapse-pairs",
    "synapse-team-week",
    "synapse-share",
)


class ShelfResolutionDocumentContractTest(unittest.TestCase):
    def test_each_resolver_skill_documents_how_shelves_are_decided(self) -> None:
        for name in RESOLVER_SKILLS:
            path = SKILLS / name / "SKILL.md"
            with self.subTest(skill=name):
                content = path.read_text(encoding="utf-8")
                self.assertIn("## 棚の決め方", content)
                self.assertIn(PRECEDENCE, content)
                self.assertIn("# SynapseConnect 設定メモ", content)
                self.assertIn("resolve_shelves.py", content)
                self.assertIn("`ask_user`", content)
                self.assertIn("--save-choice", content)
                self.assertIn("`stop`", content)

    def test_contract_documents_state_precedence_and_console_default(self) -> None:
        paths = (
            ROOT / "plugins/sc-skills/references/typed-record-contract-v2.md",
            SKILLS / "synapse-share/references/share-contract.md",
        )
        for path in paths:
            with self.subTest(path=path.name):
                content = path.read_text(encoding="utf-8")
                self.assertIn(PRECEDENCE, content)
                self.assertIn("https://console.synapse-connect.ai/console", content)
                self.assertNotIn("設定メモだけから読む", content)

    def test_share_skill_never_posts_without_allowlist(self) -> None:
        content = (SKILLS / "synapse-share/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("投稿はせず", content)
        self.assertIn("`chatwork`", content)
        self.assertIn("プレビューのみ", content)
        self.assertIn("room ID、To account ID は報告へ出さない", content)

    def test_team_week_uses_auto_members_and_own_stream_name(self) -> None:
        content = (SKILLS / "synapse-team-week/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`team` 全件", content)
        self.assertIn("team-week-<", content)
        self.assertIn("末尾8桁", content)

    def test_news_default_limit_and_meeting_default_shelf(self) -> None:
        news = (SKILLS / "news-synapse/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("5件", news)
        meeting = (SKILLS / "meeting-synapse/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`roles.company`", meeting)

    def test_help_skill_explains_how_to_reset_resolution(self) -> None:
        content = (SKILLS / "help-synapse/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`.synapse/shelves.json` を消して再実行", content)

    def test_plugin_version_and_description_match_release(self) -> None:
        plugin = json.loads(
            (ROOT / "plugins/sc-skills/.claude-plugin/plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(plugin["version"], "0.8.0")
        self.assertIn("list_groups", plugin["description"])
        self.assertNotIn("設定メモ」に分離", plugin["description"])

    def test_skill_documents_do_not_contain_real_looking_ids(self) -> None:
        for name in RESOLVER_SKILLS + ("help-synapse",):
            content = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=name):
                for token in content.split():
                    self.assertFalse(
                        token.startswith(("p_", "g_")) and len(token) > 8 and token[2:].isalnum(),
                        f"{name} contains an ID-looking token: {token}",
                    )


if __name__ == "__main__":
    unittest.main()
