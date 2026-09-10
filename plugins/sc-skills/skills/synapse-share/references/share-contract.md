# 配信設定・投稿の契約

配信記録の name、ID、本文、棚、`source_ref`、`reference_time`、失敗時の冪等処理は
07c管理の[型付き記録の共通契約 v2](../../../references/grateful-memory-contract-v2.md)を正本とする。
この文書は宛先設定とChatwork通知に固有の契約だけを追加する。

## 設定メモから必要な値

共通の `docs/config-template.md` に次の値を持つ。実値は利用者側の設定メモだけに置く。

- SynapseConnect Console のトップ URL
- `share.dry_run`: 未設定時は `true`
- Chatwork 投稿ツールの正確なツール名
- 宛先表の各行:
  - 宛先（完全一致キー）
  - 棚の名前または ID
  - Chatwork room ID
  - To account ID（個人向けだけ必須）
  - 通知先: `個人向け`、`全社向け`、`チーム向け` のいずれか

宛先表に無い値を会話、検索結果、Chatwork のルーム一覧から補わない。room ID と
To account ID は記録本文や通常の実行報告へ出さない。

## Chatwork 投稿文

```text
[To:<account_id>]
[info][title]【共有】<要点タイトル>[/title]<一言。無ければ省略>
・<要点1>
・<要点2>
詳細: <Console トップ URL>（記録ID: <episode_uuid>）
配信ID: share-20260917-1030-kintone-spec（着手したら「進捗を残す」で「対象配信：」にこのIDを）[/info]
```

- `[To:]` は個人向けだけに付ける。全社向け・チーム向けには付けない。
- 要点が1文または3文なら箇条書き数も合わせる。
- Console に記録詳細の安定URLが返る場合は、その URL を `詳細:` にそのまま使う。
  返らない場合はトップ URL と記録 ID を併記し、URL形式を推測しない。
- 署名 URL、入力本文、schema、秘密、個人の連絡先は投稿しない。
- 添付 URL がある場合も形を解釈・書き換えず、配信記録の `添付:` に置く。
  Chatwork では `詳細:` の配信記録から辿らせ、ファイルを直接添付しない。

## 結果別の停止条件

| 結果 | 次の動作 |
|---|---|
| プレビューのみ | 外部ツールを呼ばず、確認を待つ |
| `add_memory` 成功 | 返った記録 ID を投稿文へ入れ、Chatwork を1回呼ぶ |
| `add_memory` 失敗・不明 | Chatwork を呼ばず停止。再実行前に同じ `ingest_key` を照合 |
| Chatwork 成功 | 配信 ID、棚、記録 ID、投稿先の表示名を報告 |
| Chatwork 失敗・不明 | 自動再送せず、記録 IDと手動投稿用の完成文を返す |
