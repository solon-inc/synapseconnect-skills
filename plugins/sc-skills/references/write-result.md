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
| timeout・通信断・`job_id` も応答も無い | 置けたか分からない（結果不明） | **再送しない**。下の「結果不明のとき」 |

`group_id` を省略すると本人の個人棚に置かれ `inbox_fallback` が付く。スキルは棚を必ず明示し、省略に頼らない。

## 送る前に鍵を決めて控える

- `ingest_key` は送る前に決め、送った本文・棚と一緒に控える。スキルが形式を決めていれば（依頼 `req-…`・進捗 `prog-…`・配信 `share-…`）それを使う。決めていなければ `save-<yyyymmdd>-<内容の短い英字>` のように作る。
- 省略するとサーバが採番し、通信が切れると手元に鍵が残らない。そのときは鍵を推測で作り直さない（下の「結果不明のとき」）。
- 同じ鍵の再送はグラフに 1 件しか作らない（`replayed: true` なら既存の記録を採る）仕組みだが、**結果不明を自動で送り直してよいという意味ではない。**

## 待ち方

- 記録の直後にその記録 ID を使う場面（配信の投稿文に記録 ID を入れる、直後に検索で使う）だけ、`wait_seconds=30` を付けて呼ぶ。30 秒で終わらなければ `queued` が返る（失敗ではない）。
- それ以外は待たずに呼び、`queued` なら `get_ingest_status(job_id)` で状態を見る。

## 受付済み（queued）のとき

`get_ingest_status(job_id)` の `job.status` と、あれば `job.written`・`job.retry`・`job.error_code` を読む。**`status` の名前だけで「書けなかった」と決めない。**

- `succeeded`（`written: true`）: `job.result.episode_uuid` が記録 ID。`job.result.extracted` が抽出の件数。
- `queued` / `running`: まだ途中。数回まで間をおいて見直す。終わらなければ「受付済み（job_id）・完了は未確認」と報告して終える。終わるまで「記録しました」と言わない。
- `awaiting_approval`: 上の表と同じ。
- `unknown`、または `written` が `null`（`retry: false` を含む）: **結果不明**。`failed` でも、`error_code` が `llm_timeout`・`worker_lease_expired`・`write_outcome_unknown` のように書けたかが分からない種類なら同じ。「書けなかった」と言わず、下の「結果不明のとき」に進む。
- `failed` で `written: false` かつ `retry: true` のときだけ「書けなかった」と報告し、`error_code` を添える。送り直すかは利用者が決める。送り直すなら**元の `ingest_key` と同じ本文・棚**で、自動では送らない。
- 応答の `job` が `null`、`ledger_unavailable`、`coverage.complete: false`: 状態が読めなかったのであって「無い」ではない。結果不明として扱う。

## 結果不明のとき

- **再送しない。**新しい `ingest_key` でも、元の鍵でも、自動では送らない。照合して人の判断を待つ。
- `job_id` があれば、間をおいて `get_ingest_status(job_id)` を見直す。`episode_uuid` が分かれば `get_episode(uuid)` で在るかを確かめる。
- `job_id` が無ければ、`list_episodes(group_id=..., since=<送った時刻の少し前>)` で同じ `name` の行を探してよい。見つかればその記録 ID で `get_episode` する。**見つからないことは「書かれていない」「送り直して安全」の証拠にならない**（処理中・まだ届いていない・権限や読み取り範囲の不足・続きのページがありうる）。
- 報告は「結果不明（job_id／送った時刻・name・ingest_key）。再送していない」。送り直すかは、照合の結果を見て利用者（運用では人）が決める。そのときも元の `ingest_key` と同じ本文・棚を使い、鍵が分からなければ新しい鍵を作らずに止まる。
- 配信（synapse-share）は、結果不明の間は Chatwork へ進まない。

## 置けたことと、探せること

- `accepted` は「置いた」であって「探せる」ではない。`extracted.entities` と `extracted.facts` を読む。
- どちらも 0（`nothing_extracted`）なら、本文は在るが検索には出にくい。「記録は在るが検索には出ない」と分けて報告する。固有名詞・識別子（人名・案件名・ID）を入れて書き直すと抽出されやすい。あとから確かめるときは `get_episode_output(episode_uuid)`。
- `extracted.counted: false` は「数えていない」であって 0 件ではない。
- 置けたかを確かめるのは `get_episode(uuid)` だけ。`search_episodes` などの検索で確かめない（当たっても証拠にならない）。

## 報告

- 置けたとき: 「記録しました: <name>（グループ名）」。記録 ID を求められたら `episode_uuid`。
- 受付だけのとき: 「受付済み: <name>（グループ名、job_id）。完了は未確認」。
- 承認待ち・書けなかった・結果不明は、それぞれその言葉で分けて報告する。結果不明を「書けなかった」と言わない。
