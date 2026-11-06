# 記録の結果の読み方（add_memory の応答）

`add_memory` を呼ぶすべてのスキル（記憶の記録・依頼・進捗・配信・会議・ニュース）が従う共通の手順です。

## 応答の種類

`add_memory` は**既定では待たずに返る**。返った `status` で次の動作を決める。

| 応答 | 意味 | 次の動作 |
|---|---|---|
| `accepted: true`（`episode_uuid` あり） | 台帳とグラフに置けた | 記録 ID（`episode_uuid`）を控えて報告する |
| `queued`（`job_id` あり） | 受付済み。まだ置けたかは分からない。**失敗ではない** | `get_ingest_status(job_id)` で状態を見る（下の「受付済みのとき」） |
| `awaiting_approval` | 書き込みポリシーで、管理者の承認を待っている。承認までは検索に出ない | 再送しない。「承認待ち」と `job_id` を報告して終える |
| 未登録の棚・権限エラーで拒否 | 書けなかった。別の棚に黙って置かれることはない | 再送しない。書けなかった棚を報告する |
| timeout・通信断・結果不明 | 置けたか分からない | **再送しない**。下の「結果不明のとき」 |

`group_id` を省略すると本人の個人棚に置かれ `inbox_fallback` が付く。スキルは棚を必ず明示し、省略に頼らない。

## 待ち方

- 記録の直後にその記録 ID を使う場面（配信の投稿文に記録 ID を入れる、直後に検索で使う）だけ、`wait_seconds=30` を付けて呼ぶ。30 秒で終わらなければ `queued` が返る（失敗ではない）。
- それ以外は待たずに呼び、`queued` なら `get_ingest_status(job_id)` で状態を見る。

## 受付済み（queued）のとき

`get_ingest_status(job_id)` の `job.status` を読む。

- `succeeded`: `job.result.episode_uuid` が記録 ID。`job.result.extracted` が抽出の件数。
- `queued` / `running`: まだ途中。数回まで間をおいて見直す。終わらなければ「受付済み（job_id）・完了は未確認」と報告して終える。終わるまで「記録しました」と言わない。
- `awaiting_approval`: 上の表と同じ。
- `failed` など: `error_code` を添えて「書けなかった」と報告する。同じ `ingest_key` で再送するかは利用者に確かめる。

## 結果不明のとき

- 新しい `ingest_key` で出し直さない（重複の記録ができる）。
- `job_id` があれば `get_ingest_status` で照会する。無ければ `list_episodes(group_id=..., since=<送った時刻の少し前>)` で、同じ `name` の行が棚にあるかを見る。
- 棚に無いことを確かめたうえで出し直すときは、**同じ `ingest_key`** を使う（同じキーの再送はグラフに 1 件しか作らない。`replayed: true` なら既存の記録を採る）。

## 置けたことと、探せること

- `accepted` は「置いた」であって「探せる」ではない。`extracted.entities` と `extracted.facts` を読む。
- どちらも 0（`nothing_extracted`）なら、本文は在るが検索には出にくい。「記録は在るが検索には出ない」と分けて報告する。固有名詞・識別子（人名・案件名・ID）を入れて書き直すと抽出されやすい。あとから確かめるときは `get_episode_output(episode_uuid)`。
- `extracted.counted: false` は「数えていない」であって 0 件ではない。
- 置けたかを確かめるのは `get_episode(uuid)` だけ。`search_episodes` などの検索で確かめない（当たっても証拠にならない）。

## 報告

- 置けたとき: 「記録しました: <name>（グループ名）」。記録 ID を求められたら `episode_uuid`。
- 受付だけのとき: 「受付済み: <name>（グループ名、job_id）。完了は未確認」。
- 承認待ち・書けなかった・結果不明は、それぞれその言葉で分けて報告する。
