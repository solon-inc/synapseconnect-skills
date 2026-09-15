---
name: synapse-request
description: 依頼を出す — 上司や依頼者が、SynapseConnect の全社共有または開発チーム棚へ型付き依頼を1件記録するときに使う。通常の作業メモや依頼の承認フローには使わない。
---

# 依頼を出す

ユーザーが誰か・チーム・全員へ依頼を出すとき、あとから進捗と対応付けられる依頼記録を1件作る。

棚とタイムゾーンは下の「棚の決め方」で実行時に決める。グループの実名・ID はこのスキルに書かない。

## 棚の決め方

棚・タイムゾーン・上限は、キーごとに 設定メモ > `.synapse/shelves.json` > `list_groups` の自動解決 > 既定 の優先順位で決める。

1. プロジェクトのナレッジ／CLAUDE.md に `# SynapseConnect 設定メモ` 見出しのブロックがあれば、
   そこに書かれた項目（全社共有・開発チーム棚・タイムゾーン）を最優先で使う（0.8 以降、設定メモは任意で上書き用）。
2. 設定メモに無い項目は `list_groups` を1回呼び、その JSON をそのまま
   `../../scripts/resolve_shelves.py` に渡して解決する（設定メモがあれば `--memo-overrides` に
   JSON で渡す）。このスキルが使うのは `roles.company`、`roles.development`、`defaults.timezone`
   （既定は OS のタイムゾーン）。
3. 使う役割が `ask_user` なら、候補（group_id と description）を提示して1回だけ選んでもらい、
   `--save-choice <役割>=<group_id>` で `.synapse/shelves.json` に保存する。
4. `personal_self` が `stop` なら書かずに理由を伝える。`roles.development` が `absent` のときに
   「開発だけに」と言われたら、全社共有に置くか確認し、推測で選ばない。

## 固定形式

- `name`: `依頼: <30字以内の要点> — <yyyy-mm-dd>`
- `group_id`: 全社共有（`roles.company`）。ただし「開発だけに」と明示された場合だけ開発チーム棚（`roles.development`）
- `ingest_key`: `req-<yyyymmdd>-<小文字ASCIIのslug>`
- `source_ref`: 元記録の不透明な参照。無ければ `会話 <yyyy-mm-dd>`
- `reference_time`: 送信直前に信頼できる現在時計から取得した時刻（ISO 8601、タイムゾーン付き）

本文は次の行頭と全角コロンを変えない。

```text
種別：依頼
依頼ID：<ingest_keyと同じID>
依頼者：<表示名>
受け手：<表示名／チーム／全員>
内容：<何を・いつまでに・なぜ。1〜3文>
期限：<yyyy-mm-dd または 未定>
背景・元記録：<不透明な参照または 会話 yyyy-mm-dd>
判断要：あり／なし
```

## 手順

1. 依頼の受け手、内容、期限、背景、判断が必要かを会話から整理する。期限が無ければ `未定` とする。
2. 書き込み先を決める。既定は全社共有（`roles.company`）で、「開発だけに」と明示された依頼だけ開発チーム棚（`roles.development`）にする。個人棚には置かない。
3. 固定形式の内容を作り、送信直前に `../../scripts/current_reference_time.py` を実行するか、利用環境の同等な現在時計を1回読む。`defaults.timezone`（設定メモにあればその値）を `--timezone` に渡し、無ければ省略して OS のタイムゾーンに任せる。返り値を加工せず `reference_time` に使い、その日付から `req-<yyyymmdd>-<slug>`、`name`、本文の会話日付を作る。会話時刻、メッセージの表示時刻、モデルの推測で現在時刻を埋めない。時計を取得できない、または取得後に送信が中断した場合は送信せず、現在時計を取り直す。
4. API キー、token、password、cookie、口座、個人の連絡先、個人の評価表現が無いことを確認してから `add_memory` を1回だけ呼ぶ。`source_ref` と `reference_time` を付ける。
5. 返された依頼 ID、棚（と決まり方: 設定メモ／保存済み／自動解決）、記録 ID、実際に渡した `reference_time` を報告する。実体抽出が0件でも記録の着地とは分けて報告する。

## 止まる条件

- 受け手または公開範囲が分からず、全社共有と開発チーム棚で影響が変わる。
- 対象棚が `ask_user` のまま（候補が複数、または 0 件）、`stop`、または書き込み権限が無い。
- API キー、token、password、cookie、口座、個人の連絡先、個人の評価表現が含まれる。
- 信頼できる現在時計を取得できない。
- timeout、結果不明、`record_mismatch`。同じ内容を新しい ID で再投稿しない。

依頼の承認、期限通知、Chatwork 配信はこのスキルの範囲外。
