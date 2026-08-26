# synapseconnect-skills

SynapseConnect（組織の記憶の棚）を Claude から使うための公式スキル集です。
Claude Code の plugin marketplace 形式で配布しています。Claude.ai / Claude Desktop でも同じ SKILL.md をスキルとして利用できます。

## 収録プラグイン

| プラグイン | 対象 | 中身 |
|---|---|---|
| `sc-skills` | 利用者 | 基本2スキル: `load-synapse`（記憶の検索 — `/load-synapse` で明示的な読み込みにも）・`save-synapse`（記憶の記録 — `/save-synapse` で明示的な保存にも）／応用2スキル: `news-synapse`（ニュース収集）・`meeting-synapse`（会議メモ記録）／`help-synapse`（ヘルプ窓口 — 使い方案内と、解決しないときの管理者への橋渡し） |
| `sc-ops` | 導入・管理担当 | `setting-synapse` — 環境確認から記録・読み込み頻度のヒアリングまで対話で行い、SynapseConnect を最適に使うシステムプロンプトを作成・設定案内する |

## 前提

1. SynapseConnect の MCP コネクタに接続済みであること（接続手順は提供元の接続ガイド参照）。
2. 基本ルール（システムプロンプト）を設定済みであること。基本ルールが「いつ動くか」を決め、
   本リポジトリのスキルが「どうやるか」を決める2層構成です。基本ルール全文は
   `plugins/sc-ops/skills/setting-synapse/references/base-rules.md` にあります。
3. 棚の実名・ID などの固有値はスキルに含まれません。`docs/config-template.md` を写して
   「設定メモ」を1枚作り、プロジェクトのナレッジ（Claude Code なら CLAUDE.md の1節）に置いてください。

## 導入

- **Claude Code**:
  ```
  /plugin marketplace add solon-inc/synapseconnect-skills
  /plugin install sc-skills@synapseconnect-skills
  ```
  （導入・管理担当は `sc-ops@synapseconnect-skills` も）
- **Claude.ai（チャット）/ Claude Desktop**: `plugins/sc-skills/skills/` 配下の各スキルフォルダを
  zip にして「設定 → Skills」からアップロード。Team/Enterprise は組織一括配布（Organization-provisioned skills）が使えます。
- スキルのアップロードが使えない環境では、SKILL.md 本文をプロジェクトの指示欄・ナレッジに貼っても同じ効果があります。

## 更新

- 各プラグインの `plugin.json` の `version` で版を管理します。
- Claude Code は `/plugin marketplace update synapseconnect-skills` で更新（自動更新も既定で有効）。
- zip 導入の場合は、新しい zip を再アップロードしてください。

## ライセンス

© Solon Inc. All rights reserved.
本スキル集は SynapseConnect 利用者向けに提供しています。再配布・改変配布はご相談ください。
