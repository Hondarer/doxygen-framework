<!--
生成元: agree-before-implement スキル
文書種別: 簡易 ADR (lightadr)
最終更新日時: 2026-11-25 20:59:00 JST
最終更新エージェント: claude code (opus サブエージェント、主セッション session_01KJc53UFydnbt2gLXTJC1ZC)
稼働 OS: Linux (WSL)
上流文書: `261125-doxyfw-storage-loss-investigation-overview.md` (全体管理文書)、`261125-doxyfw-storage-loss-investigation-discussion.md` (検討用 Markdown)。いずれも削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。上流文書の全体管理文書が存在する場合は、その再開手順に従って進行位置を確認します。存在しない場合は、この文書を単体の決定事項の記録として扱います。この文書は正式な ADR ではありません。正式な ADR への転記はユーザーが必要時に行うため、エージェントは依頼なしに転記や正式な ADR の作成・更新を行わないでください。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。
-->

# doxyfw 起動直後の Chrome で保存領域の値が失われる理由の調査 簡易 ADR

ファイル名: `261125-doxyfw-storage-loss-investigation-lightadr.md`

この文書は、検討で得られた事実、ユーザーの選択とコメント、およびそれらに基づく決定事項を、決定 1 件ごとにまとめた簡易 ADR (Architecture Decision Record: 設計判断の記録) です。正式な ADR ではなく、対案の比較や決定の影響の評価は記載していません。  
各決定の「決定」は、方針が変わるたびに書き換え、常に最新の決定だけを示します。変更の推移は「経緯」に時系列で記録します。

## 決定事項一覧

| 決定 ID | 題名 | 最終更新日 | 源泉 |
| --- | --- | --- | --- |
| [LADR-001](#ladr-001-調査の実施) | 調査の実施 | 2026-11-25 | [Q-001](261125-doxyfw-storage-loss-investigation-discussion.md#q-001-この案件で調査を行うか) |
| [LADR-002](#ladr-002-調査する-chrome-の版と取得方法) | 調査する Chrome の版と取得方法 | 2026-11-25 | [Q-002](261125-doxyfw-storage-loss-investigation-discussion.md#q-002-調査する-chrome-の版) |
| [LADR-003](#ladr-003-調査するページの種類) | 調査するページの種類 | 2026-11-25 | [Q-003](261125-doxyfw-storage-loss-investigation-discussion.md#q-003-調査するページの種類) |
| [LADR-004](#ladr-004-削除の時点の条件) | 削除の時点の条件 | 2026-11-25 | [Q-004](261125-doxyfw-storage-loss-investigation-discussion.md#q-004-調査する削除の時点) |
| [LADR-005](#ladr-005-sessionstorage-の調査) | sessionStorage の調査 | 2026-11-25 | [Q-005](261125-doxyfw-storage-loss-investigation-discussion.md#q-005-sessionstorage-を調査に含めるか)、[Q-011](261125-doxyfw-storage-loss-investigation-discussion.md#q-011-sessionstorage-の実験の起動方式) |
| [LADR-006](#ladr-006-調査報告の記録先) | 調査報告の記録先 | 2026-11-25 | [Q-006](261125-doxyfw-storage-loss-investigation-discussion.md#q-006-調査結果の記録先)、[Q-010](261125-doxyfw-storage-loss-investigation-discussion.md#q-010-再現実験のスクリプトの置き場所) |
| [LADR-007](#ladr-007-chromium-への不具合報告の扱い) | Chromium への不具合報告の扱い | 2026-11-25 | [Q-007](261125-doxyfw-storage-loss-investigation-discussion.md#q-007-chromium-への不具合報告の扱い) |
| [LADR-008](#ladr-008-再現の判定に使う試行回数) | 再現の判定に使う試行回数 | 2026-11-25 | [Q-008](261125-doxyfw-storage-loss-investigation-discussion.md#q-008-再現の判定に使う試行回数) |
| [LADR-009](#ladr-009-調査の範囲の上限) | 調査の範囲の上限 | 2026-11-25 | [Q-009](261125-doxyfw-storage-loss-investigation-discussion.md#q-009-調査にかける時間の上限) |

## LADR-001 調査の実施

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

対策元 `261116-doxyfw-page-variant-reload-flake-backlog.md` の BL-001 (起動直後の Chrome で、文書の開始時の `localStorage.removeItem` の後に保存した値が再読み込みで失われる理由が未確認) は、前案件でテストの修正だけで CI の失敗を解消したため、理由の追究を見送った項目です。この案件で調査を行うかを決める必要がありました。

### 得られた事実

- 現在の `framework/doxyfw/bin_test/page_link_probe.js` は、削除の指定を保存値が残っているページだけに限っており、調査をしなくても製品とテストの動作は変わりません (対策元 BL-001)。
- `framework` 配下の `bin_test` で `localStorage` の `removeItem` を使うのは `page_link_probe.js` だけです (対策元 BL-001)。

### 決定

この案件で BL-001 の調査を実施します。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-001](261125-doxyfw-storage-loss-investigation-discussion.md#q-001-この案件で調査を行うか) | A: 調査を実施する | なし | 新規に決定 |

## LADR-002 調査する Chrome の版と取得方法

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

確認済みの版は Chrome for Testing 153.0.8010.36 (headless) だけで、BL-001 はほかの版での発生有無を調べることを求めています。どの版で再現実験を行うかを決める必要がありました。

### 得られた事実

- ローカルの `/opt/chrome-for-testing/` には 153.0.8010.36 だけがあり、puppeteer 25.11.0 は `PUPPETEER_SKIP_DOWNLOAD=true` で導入されています (2026-11-25 の確認)。
- 2026-11-25 20:48 JST に、Chrome for Testing の公開一覧 `https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json` (更新時刻 2026-11-24T22:10:57Z) の Stable が 158.0.8127.88 であることを確認しました。
- `https://storage.googleapis.com/chrome-for-testing-public/158.0.8127.88/linux64/chrome-linux64.zip` (約 208 MB) をセッションの一時ディレクトリへ取得して展開し、`--version`、headless での起動、puppeteer 25.11.0 の `executablePath` 指定での起動を確認しました。不足する共有ライブラリはありませんでした。
- CI コンテナーの定義 (`oracle-linux-container/src/Dockerfile`) は、153.0.8010.36 を同じ配布元 (`https://storage.googleapis.com/chrome-for-testing-public/<版>/linux64/chrome-linux64.zip`) から取得しています。

### 決定

153.0.8010.36 (ローカルに導入済みの版) と、取得時点の Stable の最新版の 2 つで再現実験を行います。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-002](261125-doxyfw-storage-loss-investigation-discussion.md#q-002-調査する-chrome-の版) | A: 153.0.8010.36 と、取得時点の Stable の最新版の 2 つ | なし | 新規に決定 |

## LADR-003 調査するページの種類

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

BL-001 の確認は `file://` のページだけです。`http://` のページでも調べるかを決める必要がありました。

### 得られた事実

- BL-001 の「本来あるべき姿」に、発生条件の範囲として `http://` のページが挙げられています。

### 決定

`file://` と `http://` の両方のページで再現実験を行います。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-003](261125-doxyfw-storage-loss-investigation-discussion.md#q-003-調査するページの種類) | A: `file://` と `http://` の両方を調べる | なし | 新規に決定 |

## LADR-004 削除の時点の条件

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

既存の確認では、現象の原因が「削除を行うこと」か「削除を文書の開始時に行うこと」かが切り分けられていません。`removeItem` を実行する時点として何を調べるかを決める必要がありました。

### 得られた事実

- 対策元の再現試験 (負荷あり) で、文書の開始時に削除した場合は 60 回中 24 回、削除しない場合は 60 回中 0 回、値が失われました (対策元 BL-001)。

### 決定

文書の開始時 (`evaluateOnNewDocument`) に削除する条件と、読み込み完了の後に削除する条件を比較します。削除しない条件は対照として含めます。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-004](261125-doxyfw-storage-loss-investigation-discussion.md#q-004-調査する削除の時点) | A: 条件 1 (文書の開始時) と条件 2 (読み込み完了後) を比較する | なし | 新規に決定 |

## LADR-005 sessionStorage の調査

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

対策元の再現試験で、`sessionStorage` の値が再読み込み後に読めない回が 200 回中 4 回ありました。`sessionStorage` を調査に含めるかを決める必要がありました。

### 得られた事実

- 200 回中 4 回の観測は、「最小の再現用スクリプト (ブラウザーを使い回す)」の負荷ありの試験で得たものです。このスクリプトは `page_link_probe.js` と同じ順序 (削除スクリプトの登録、遷移、解除、保存、再読み込み) を行います。同じ試験の `localStorage` は 200 回とも値を維持しました (`261116-doxyfw-page-variant-reload-flake-discussion.md` の「WSL での再現と切り分け」)。

### 決定

`sessionStorage` を調査に含めます。`sessionStorage` の実験は、1 回ごとにブラウザーを起動する方式と、1 つのブラウザーを使い回して試行ごとに新しいページを開く方式の両方で、削除の時点の条件 (文書の開始時、読み込み完了後、削除なし) を調べます。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-005](261125-doxyfw-storage-loss-investigation-discussion.md#q-005-sessionstorage-を調査に含めるか) | A: 含める | なし | 新規に決定 |
| 2026-11-25 20:54 | [Q-011](261125-doxyfw-storage-loss-investigation-discussion.md#q-011-sessionstorage-の実験の起動方式) | A: 1 回ごとに起動する方式と、ブラウザーを使い回す方式の両方を調べる | なし | 決定を補足 (起動方式を追加) |

## LADR-006 調査報告の記録先

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

調査結果を、恒久的な知見として正本文書に置くか、経緯として検討文書に置くかを決める必要がありました。

### 得られた事実

- プロジェクトの方針として、正本文書には経緯を残さず最終仕様だけを書き、経緯は `prompt/` 配下の検討用 Markdown に記録します。
- AGENTS.md は、非自明な回避策の根拠 URL を `see: <URL>` 形式でソース内に残すよう定めています。

### 決定

調査報告は、対策元 BL-001 の「継続作業での経緯と対処」と、この案件の最終仕様と残課題一覧に記録します。該当する Chromium の不具合報告がある場合は、`framework/doxyfw/bin_test/page_link_probe.js` のコメントに `see: <URL>` を追加します。正本文書は変更しません。再現実験のスクリプト (最小の再現スクリプト、条件を切り替えて繰り返す実行スクリプト、`http://` 用の簡易サーバー) はセッションの一時ディレクトリにだけ置き、リポジトリには残しません。最小の再現コードは調査報告に載せます。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-006](261125-doxyfw-storage-loss-investigation-discussion.md#q-006-調査結果の記録先) | A: 対策元 BL-001 と、この案件の文書に記録する。該当する報告があれば `page_link_probe.js` のコメントに `see: <URL>` を追加する。正本文書は変更しない | なし | 新規に決定 |
| 2026-11-25 20:54 | [Q-010](261125-doxyfw-storage-loss-investigation-discussion.md#q-010-再現実験のスクリプトの置き場所) | A: 一時ディレクトリにだけ置き、リポジトリには残さない。最小の再現コードは調査報告に載せる | なし | 決定を補足 (スクリプトの置き場所を追加) |

## LADR-007 Chromium への不具合報告の扱い

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

既知の報告が見つからず、最小の再現手順が得られた場合に、Chromium の不具合トラッカーへの報告をどう扱うかを決める必要がありました。外部への送信はユーザーのアカウントで行う操作です。

### 得られた事実

- 2026-11-25 の既知報告の検索 (WebSearch 2 回) では、この現象と一致する報告は見つかりませんでした。

### 決定

外部への報告は送信しません。最小の再現手順が得られた場合は、報告用の下書き (再現コードと条件) を調査報告に含めます。送信するかは、ユーザーが別途判断します。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-007](261125-doxyfw-storage-loss-investigation-discussion.md#q-007-chromium-への不具合報告の扱い) | A: 報告は送信せず、下書きを調査報告に含める。送信の判断はユーザーが別途行う | なし | 新規に決定 |

## LADR-008 再現の判定に使う試行回数

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

各条件で「再現した」「再現しない」を判定するための試行回数を決める必要がありました。

### 得られた事実

- 発生率 2% の現象を n 回で 1 回も観測しない確率は、n=60 で約 30%、n=200 で約 1.8% です (計算)。
- 負荷なしの予備実行 (1 回ごとに起動、5 回) では、1 回あたり約 0.4 秒から 0.5 秒でした (2026-11-25、セッションの一時ディレクトリで計測)。

### 決定

`localStorage` で削除を伴う条件 (文書の開始時、読み込み完了後) は 60 回とし、60 回で 1 回も発生しなかった条件は 200 回まで追加します。`localStorage` で削除を伴わない条件と、`sessionStorage` のすべての条件 (両方の起動方式) は 200 回とします。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-008](261125-doxyfw-storage-loss-investigation-discussion.md#q-008-再現の判定に使う試行回数) | A: 発生率が高い条件 (`localStorage` の削除あり) は 60 回、発生率が低い条件 (`sessionStorage`、およびほかの版や `http://` で再現が見られない場合) は 200 回 | なし | 新規に決定 (選択肢の規則を各条件へ当てはめた) |

## LADR-009 調査の範囲の上限

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

原因が Chrome の内部実装にある場合、再現実験だけでは「なぜ」に到達できない可能性があります。調査の範囲の上限を決める必要がありました。

### 得られた事実

- BL-001 の「本来あるべき姿」は、値が失われる理由と、発生する条件の範囲、不具合報告の有無の把握です。

### 決定

再現実験 (条件の比較) までを範囲とし、Chromium のソース読解は行いません。内部の原因が未確認の場合は、この案件の残課題一覧に記録します。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:35 | [Q-009](261125-doxyfw-storage-loss-investigation-discussion.md#q-009-調査にかける時間の上限) | A: 再現実験までを範囲とし、Chromium のソース読解は行わない。内部の原因が未確認の場合は残課題として残す | なし | 新規に決定 |
