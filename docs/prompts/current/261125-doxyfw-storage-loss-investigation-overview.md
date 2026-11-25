<!--
生成元: agree-before-implement スキル
文書種別: 全体管理文書 (overview)
最終更新日時: 2026-11-26 04:20:00 JST
最終更新エージェント: claude code (主セッション session_01KJc53UFydnbt2gLXTJC1ZC)
稼働 OS: Linux (WSL)
上流文書: `261116-doxyfw-page-variant-reload-flake-backlog.md` (対策元の残課題一覧。BL-001 が対象)
下流文書: `261125-doxyfw-storage-loss-investigation-discussion.md` (検討用 Markdown)、`261125-doxyfw-storage-loss-investigation-lightadr.md` (簡易 ADR)、`261125-doxyfw-storage-loss-investigation-design.md` (最終仕様)、`261125-doxyfw-storage-loss-investigation-backlog.md` (残課題一覧)。未作成の場合や、削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。この文書と、ユーザーが編集した最新の検討用 Markdown を読み直し、作業 WBS の `← **CURRENT**` の項目から再開します。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。`← **CURRENT**` の項目は処理が中止された項目である場合があり、どこまで進んでいたかは文書だけでは分かりません。対象成果物の内容を確認して実施済みの範囲を特定してから、作業を再開してください。`← **CURRENT**` がなく、作業 WBS がすべて完了 (✅) であれば、この案件の合意フローは完了しています。
-->

# doxyfw 起動直後の Chrome で保存領域の値が失われる理由の調査 全体管理

ファイル名: `261125-doxyfw-storage-loss-investigation-overview.md`

この文書は、案件の識別、作業 WBS、対象範囲、確認状況、経緯を管理します。質問と回答の本文は検討用 Markdown ([261125-doxyfw-storage-loss-investigation-discussion.md](261125-doxyfw-storage-loss-investigation-discussion.md)) に、決定事項は簡易 ADR (`261125-doxyfw-storage-loss-investigation-lightadr.md`) に記載し、この文書には重複して記載しません。

## 案件の識別

検討 ID: 261125-doxyfw-storage-loss-investigation

検討用 Markdown の版: 2

状態: 第 3 ゲート待ち (作業の実施を完了。Windows の確認は残課題)

## 作業 WBS と進捗管理

凡例: ⏸️ 未着手、🔄 実施中、🚫 ブロック中、⚠️ 要注意、✅ 完了。現在取り組んでいる項目の末尾に `← **CURRENT**` を付けます。

- ✅ 1. 検討用 Markdown のための情報収集と質問の実施
    - ✅ 1.1. 前提条件と要求事項の調査 (対策元 `261116-doxyfw-page-variant-reload-flake-backlog.md` の BL-001、`framework/doxyfw/bin_test/page_link_probe.js` の `newReportPage()`、ローカルの Chrome for Testing と puppeteer の版、Chromium の既知報告の検索) と、対策元 BL-001 の状態の「検討中」への更新
    - ✅ 1.2. 課題・論点の抽出と明確化のための確認項目 ([Q-001](261125-doxyfw-storage-loss-investigation-discussion.md#q-001-この案件で調査を行うか) から [Q-009](261125-doxyfw-storage-loss-investigation-discussion.md#q-009-調査にかける時間の上限)) の作成
    - ✅ 1.3. Q&A ターンごとのユーザー回答の受付と記録 (JST 日時、Git ユーザー名または発言者)。Q-001 から Q-009 の回答 (2026-11-25 20:35:57 JST 保存) を受領
    - ✅ 1.4. 回答に基づく前提・制約の検証、簡易 ADR (`261125-doxyfw-storage-loss-investigation-lightadr.md`) への決定事項の反映、WBS の見直し (合意方針や見送り決定を対策元 BL-001 へ随時反映)。Q-001 から Q-009 を解決済みにし、LADR-001 から LADR-009 を記録。Chrome for Testing の取得可否を一時ディレクトリで確認。追加 Q として Q-010 と Q-011 を作成
    - ✅ 1.5. 追加 Q の回答の受付と記録。Q-010 と Q-011 の回答 (2026-11-25 20:54:43 JST 保存) を受領
    - ✅ 1.6. 追加 Q の回答の検証と、簡易 ADR (LADR-005、LADR-006、LADR-008) と対策元 BL-001 への反映
- ✅ 2. 前提合意と残懸念の解消 (第 1 ゲート: 最終仕様作成への着手)
    - ✅ 2.1. 全論点に対する未解決事項および質問の解消確認 (Q-001 から Q-011 が解決済み、6 観点が確認済み)
    - ✅ 2.2. 方針・前提条件の合意確定 (簡易 ADR の決定事項と、根拠となった解決済み Q の回答との一致を確認し、懸念がないことをもってフェーズ 2 へ着手)
- ✅ 3. 最終決定事項 (最終仕様) の作成と承認の受付
    - ✅ 3.1. `261125-doxyfw-storage-loss-investigation-design.md` の作成 (調査の条件表、再現手順、結論の判定基準、記録先を含む。対策元 BL-001 へ確定方針・状態を反映)
    - ✅ 3.2. 最終仕様における受入条件と整合性の確認 (LADR-001 から LADR-009 と最終仕様の各章の一致を確認)
    - ✅ 3.3. 対話セッションにおける最終仕様 (design.md) の承認の受付 (第 2 ゲート: 作業着手の合意)。2026-11-25 21:48 頃のユーザーの自走指示で承認されたものとして扱う
- ✅ 4. 承認された最終仕様に従った作業の実施
    - ✅ 4.1. Chrome for Testing の取得時点の Stable の最新版のセッションの一時ディレクトリへの取得、最小の再現スクリプトの作成、条件別の再現実験の実施 (スクリプトはセッションの一時ディレクトリにだけ置く。実験は調査報告の根拠として結果を記録する)
    - ✅ 4.2. 調査報告の作成 (記録先は [Q-006](261125-doxyfw-storage-loss-investigation-discussion.md#q-006-調査結果の記録先) の回答に従う)。調査結果を最終仕様の「調査結果」の章へ記録 (36 条件、6,920 回)。Windows での発生有無は、最終仕様の範囲 (検証手順の Windows は不要) の外のため、残課題 BL-002 として記録
    - ✅ 4.3. 該当する Chromium の不具合報告がある場合の `framework/doxyfw/bin_test/page_link_probe.js` のコメントへの `see: <URL>` の追加。該当する報告なし (検索 4 回)。page_link_probe.js は変更しない
    - ✅ 4.4. 変更した Markdown の機械的検証 (`text_style_jp.py --dry-run` の後に `--in-place`) と、対策元 BL-001 の最終状態の記録。design.md と対策元 BL-001 を dry-run、in-place で確認 (残課題一覧と overview は 4.7 の後に再確認)
    - ✅ 4.5. 受入条件への適合確認 (全作業の完了確認)。受入条件 1 から 8 を確認 (36 条件の結果、Stable の版と取得元、5 観点の結論、検索結果、最小の再現コードと下書き、page_link_probe.js 無変更、リポジトリへのスクリプト追加なし、BL-001 更新)。9 は全文書の整形後に最終確認
    - ✅ 4.6. 簡易 ADR (`261125-doxyfw-storage-loss-investigation-lightadr.md`) の最終確認。LADR-001 から LADR-009 の決定は実施結果と矛盾せず、変更なし。実験で 158.0.8127.88 を使用 (LADR-002 のとおり)
    - ✅ 4.7. 残課題一覧 (`261125-doxyfw-storage-loss-investigation-backlog.md`) の再構築と整理 (未解明の範囲や次フェーズへ回す事項の転記を含む。対策元 BL-001 の最終状態・転記先の確定)。BL-001 から BL-004 に再構築 (内部の原因、Windows 未確認、以前の観測の不一致、不具合報告の未送信)
- 🔄 5. 成果物の承認の受付 (第 3 ゲート)
    - 🔄 5.1. 成果物・検証結果・残課題の提示 ← **CURRENT**
    - ⏸️ 5.2. 対話セッションにおける成果物の承認の受付 (「承認」または「完了」の受領によるスキル完了)

## 対象と参照資料

依頼の源泉: ユーザーの指示 (2026-11-25 対話)。「消化可能なバックログを消化していきたい、各 prompt/current で対応可能な backlog を agree-before-implement スキルで推進します。サブエージェントには Sonnet を使用してください。また、Windows 側に Claude Code が待機しているので、疎通を取って連携して進めてください。」

対象成果物: 調査報告 (記録先は [Q-006](261125-doxyfw-storage-loss-investigation-discussion.md#q-006-調査結果の記録先) で確認します)。該当がある場合は `framework/doxyfw/bin_test/page_link_probe.js` のコメントへの `see: <URL>` の追加。

今回の対象範囲: 対策元の BL-001 (起動直後の Chrome で、文書の開始時の `localStorage.removeItem` の後に保存した値が再読み込みで失われる理由が未確認) の調査。調査の範囲は [Q-001](261125-doxyfw-storage-loss-investigation-discussion.md#q-001-この案件で調査を行うか) から [Q-005](261125-doxyfw-storage-loss-investigation-discussion.md#q-005-sessionstorage-を調査に含めるか) で確認します。

書き込み可能な検討文書: この文書、検討用 Markdown (`261125-doxyfw-storage-loss-investigation-discussion.md`)、簡易 ADR (`261125-doxyfw-storage-loss-investigation-lightadr.md`)。対策元の残課題一覧の状態・経緯・メタ情報。

参照資料と版:

- 対策元: `261116-doxyfw-page-variant-reload-flake-backlog.md` の BL-001、同案件の `261116-doxyfw-page-variant-reload-flake-design.md` と `261116-doxyfw-page-variant-reload-flake-discussion.md`
- `framework/doxyfw/bin_test/page_link_probe.js` の `newReportPage()` (現在は `clearVariant` を指定したページだけで開始時の削除を行い、読み込み後に削除スクリプトを解除する)
- ローカルの実行環境 (2026-11-25 に確認): Oracle Linux Server 8.10、Chrome for Testing 153.0.8010.36 (`/usr/local/bin/chrome` から `/opt/chrome-for-testing/153.0.8010.36/chrome-linux64/chrome` へのシンボリック リンク。`/opt/chrome-for-testing/` に入っている版はこの 1 つだけ)、puppeteer と puppeteer-core 25.11.0 (`/usr/local/lib/node_modules/`)、Node.js v24.21.0、論理 CPU 72、環境変数 `PUPPETEER_EXECUTABLE_PATH=/usr/local/bin/chrome` と `PUPPETEER_SKIP_DOWNLOAD=true`。`~/.cache/puppeteer` は存在しません。
- Chrome for Testing の取得の可否 (2026-11-25 20:48 JST に確認): 公開一覧 `https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json` の Stable は 158.0.8127.88。`https://storage.googleapis.com/chrome-for-testing-public/158.0.8127.88/linux64/chrome-linux64.zip` をセッションの一時ディレクトリへ取得し、headless での起動と puppeteer 25.11.0 からの起動を確認しました。CI コンテナーの定義 (`oracle-linux-container/src/Dockerfile`) も同じ配布元を使います。
- 負荷なしの予備実行 (1 回ごとにブラウザーを起動、5 回): 1 回あたり約 0.4 秒から 0.5 秒。
- Chromium の不具合トラッカーの既知報告の検索 (WebSearch 2 回): 該当する報告は見つかりませんでした。詳細は [Q-007](261125-doxyfw-storage-loss-investigation-discussion.md#q-007-chromium-への不具合報告の扱い) の Context に記載します。

## 観点別の確認

| 観点 | 状態 | 根拠・関連 Q |
| --- | --- | --- |
| 目的・利用者 | 確認済み | [Q-001](261125-doxyfw-storage-loss-investigation-discussion.md#q-001-この案件で調査を行うか)、[Q-006](261125-doxyfw-storage-loss-investigation-discussion.md#q-006-調査結果の記録先) |
| 範囲・境界 | 確認済み | [Q-011](261125-doxyfw-storage-loss-investigation-discussion.md#q-011-sessionstorage-の実験の起動方式)、[Q-002](261125-doxyfw-storage-loss-investigation-discussion.md#q-002-調査する-chrome-の版)、[Q-003](261125-doxyfw-storage-loss-investigation-discussion.md#q-003-調査するページの種類)、[Q-004](261125-doxyfw-storage-loss-investigation-discussion.md#q-004-調査する削除の時点)、[Q-005](261125-doxyfw-storage-loss-investigation-discussion.md#q-005-sessionstorage-を調査に含めるか) |
| 入力・根拠 | 確認済み | ローカルの Chrome と puppeteer の版、Chrome for Testing の Stable の取得の可否を確認済み (「参照資料と版」)。Chromium の既知報告の検索では該当なし。[Q-005](261125-doxyfw-storage-loss-investigation-discussion.md#q-005-sessionstorage-を調査に含めるか) の Context と対策元資料の食い違いは [Q-011](261125-doxyfw-storage-loss-investigation-discussion.md#q-011-sessionstorage-の実験の起動方式) で扱う |
| 整合性・依存関係 | 確認済み | [Q-010](261125-doxyfw-storage-loss-investigation-discussion.md#q-010-再現実験のスクリプトの置き場所) (スクリプトは一時ディレクトリだけに置き、`bin_test/` の規範と整合)、[Q-007](261125-doxyfw-storage-loss-investigation-discussion.md#q-007-chromium-への不具合報告の扱い) (外部への報告と、リポジトリの規範の「根拠 URL を `see:` で残す」との関係) |
| 実現性・例外 | 確認済み | [Q-008](261125-doxyfw-storage-loss-investigation-discussion.md#q-008-再現の判定に使う試行回数)、[Q-009](261125-doxyfw-storage-loss-investigation-discussion.md#q-009-調査にかける時間の上限) |
| 受入条件・検証 | 確認済み | [Q-008](261125-doxyfw-storage-loss-investigation-discussion.md#q-008-再現の判定に使う試行回数)、[Q-006](261125-doxyfw-storage-loss-investigation-discussion.md#q-006-調査結果の記録先) |

## 質問一覧

各 Q の本文は検討用 Markdown にあります。

| Q-ID | 論点 | 状態 | 依存・関連 | 反映先の決定 |
| --- | --- | --- | --- | --- |
| [Q-001](261125-doxyfw-storage-loss-investigation-discussion.md#q-001-この案件で調査を行うか) | この案件で調査を行うか | 解決済み | なし | LADR-001 |
| [Q-002](261125-doxyfw-storage-loss-investigation-discussion.md#q-002-調査する-chrome-の版) | 調査する Chrome の版 | 解決済み | Q-001 | LADR-002 |
| [Q-003](261125-doxyfw-storage-loss-investigation-discussion.md#q-003-調査するページの種類) | 調査するページの種類 | 解決済み | Q-001 | LADR-003 |
| [Q-004](261125-doxyfw-storage-loss-investigation-discussion.md#q-004-調査する削除の時点) | 調査する削除の時点 | 解決済み | Q-001 | LADR-004 |
| [Q-005](261125-doxyfw-storage-loss-investigation-discussion.md#q-005-sessionstorage-を調査に含めるか) | sessionStorage を調査に含めるか | 解決済み | Q-001 | LADR-005 |
| [Q-006](261125-doxyfw-storage-loss-investigation-discussion.md#q-006-調査結果の記録先) | 調査結果の記録先 | 解決済み | Q-001 | LADR-006 |
| [Q-007](261125-doxyfw-storage-loss-investigation-discussion.md#q-007-chromium-への不具合報告の扱い) | Chromium への不具合報告の扱い | 解決済み | Q-006 | LADR-007 |
| [Q-008](261125-doxyfw-storage-loss-investigation-discussion.md#q-008-再現の判定に使う試行回数) | 再現の判定に使う試行回数 | 解決済み | Q-002 から Q-005 | LADR-008 |
| [Q-009](261125-doxyfw-storage-loss-investigation-discussion.md#q-009-調査にかける時間の上限) | 調査にかける時間の上限 | 解決済み | Q-001、Q-008 | LADR-009 |
| [Q-010](261125-doxyfw-storage-loss-investigation-discussion.md#q-010-再現実験のスクリプトの置き場所) | 再現実験のスクリプトの置き場所 | 解決済み | Q-006、Q-007 | LADR-006 |
| [Q-011](261125-doxyfw-storage-loss-investigation-discussion.md#q-011-sessionstorage-の実験の起動方式) | sessionStorage の実験の起動方式 | 解決済み | Q-004、Q-005、Q-008 | LADR-005、LADR-008 |

## 対象成果物と合意版

最終決定事項 (最終仕様) の設計書: `261125-doxyfw-storage-loss-investigation-design.md`

検討用 Markdown の合意版 (第 1 ゲート): 版 2 (2026-11-25 21:00 JST に残懸念なしを確認)

最終仕様 (design.md) の合意版 (第 2 ゲート): 2026-11-25 21:48 頃のユーザーの自走指示による承認 (2026-11-26 01:57 JST に作業着手)

更新予定の成果物: 調査報告 (記録先は Q-006 で確定)。該当がある場合は `framework/doxyfw/bin_test/page_link_probe.js` のコメント。

受入条件: 最終仕様 (`261125-doxyfw-storage-loss-investigation-design.md`) の「受入条件」の節に記載

## 経緯

| 日時 (JST) | 出来事 | 内容・参照先 |
| --- | --- | --- |
| 2026-11-25 20:35 | 案件の開始 | 全体管理文書と検討用 Markdown (版 1) を作成。対策元 BL-001 の状態を「検討中」へ更新 |
| 2026-11-25 20:56 | 回答の検証と追加 Q の提示 (版 2) | Q-001 から Q-009 の回答 (Tetsuo Honda、2026-11-25 20:35:57 JST) を検証し、解決済みにした。簡易 ADR (LADR-001 から LADR-009) と、この案件の残課題一覧を作成。追加 Q として Q-010 と Q-011 を検討用 Markdown へ追記。担当を Opus のサブエージェントへ変更 (ユーザーの指示) |
| 2026-11-25 21:00 | 第 1 ゲートの通過 | Q-010 と Q-011 の回答 (Tetsuo Honda、2026-11-25 20:54:43 JST) を検証して解決済みにし、LADR-005、LADR-006、LADR-008 を更新。全 Q が解決済みで 6 観点が確認済みのため、合意版を版 2 として最終仕様の作成に着手 |
| 2026-11-25 20:57 | 最終仕様の作成 | `261125-doxyfw-storage-loss-investigation-design.md` を作成。対策元 BL-001 の状態を「対応中」へ更新。第 2 ゲートで停止 |
| 2026-11-26 01:57 | 第 2 ゲートの通過 | ユーザーの指示 (2026-11-25 21:48 頃の対話)「全体の進め方を先に指示する。…ユーザーの確認なく継続的に自走すること。…決定した最終仕様が実現できない場合は、ユーザーに問い合わせることなく backlog に送る。各サブモジュール (案件) 完了時に main にプッシュし CI を起動させ、エラーや警告があれば都度対処する。…」および「6. は他の案件同様 main へのコミットを事前許可する。」を最終仕様の承認として扱い、WBS 4 に着手。担当は sonnet サブエージェント |
| 2026-11-26 03:56 | 再現実験の完了 | 36 条件、6,920 回。文書の開始時の削除かつ `file://` の条件だけで値が失われた (版による違いなし) |
| 2026-11-26 04:25 | 作業の完了 | 調査結果の記録、対策元 BL-001 の完了、残課題一覧の再構築。第 3 ゲートで停止 |

## 反映と検証の記録

- 対応箇所: `261125-doxyfw-storage-loss-investigation-design.md` に「調査結果」の章を追加 (実験環境、36 条件の結果、結論、既知の報告の検索、最小の再現コード、報告用の下書き)。対策元 `261116-doxyfw-page-variant-reload-flake-backlog.md` の BL-001 を「完了」にし、経緯を記載。`261125-doxyfw-storage-loss-investigation-backlog.md` を BL-001 から BL-004 に再構築。`page_link_probe.js` は、該当する既知の報告がなかったため変更なし。
- 実験: 2026-11-26 01:57 JST から 03:56 JST。153.0.8010.36 と 158.0.8127.88、36 条件、有効な試行 6,920 回、例外 0 件。値が失われたのは、文書の開始時の削除かつ `file://` の 6 条件だけ。スクリプトと生データ (`results.jsonl`) はセッションの一時ディレクトリ `261125-doxyfw-storage-loss-investigation/` だけにあり、リポジトリには追加していない。
- 検証: 変更した Markdown (design、対策元 backlog、この案件の backlog、overview) に `text_style_jp.py --dry-run` と `--in-place` を実施。
- 未完了項目: Windows での発生有無 (BL-002)。第 3 ゲート (成果物の承認) は未受領。
