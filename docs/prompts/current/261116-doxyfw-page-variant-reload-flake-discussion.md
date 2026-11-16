<!--
生成元: agree-before-implement スキル
文書種別: 検討用 Markdown (discussion)
最終更新日時: 2026-11-16 11:10:00 JST
最終更新エージェント: claude code / セッション ID: session_01KJc53UbHjwaWeuucBs5Q5U
稼働 OS: Windows
上流文書: `../../../../../app/porter/docs/prompts/current/261115-porter-multicast-src-contract-backlog.md` (対策元の残課題一覧。BL-003 が対象)
下流文書: `261116-doxyfw-page-variant-reload-flake-design.md` (最終仕様)、`261116-doxyfw-page-variant-reload-flake-backlog.md` (残課題一覧)。未作成の場合や、削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。ユーザーが編集した最新版を読み直し、作業 WBS の `← **CURRENT**` の項目から再開します。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。`← **CURRENT**` の項目は処理が中止された項目である場合があり、どこまで進んでいたかは文書だけでは分かりません。対象成果物の内容を確認して実施済みの範囲を特定してから、作業を再開してください。`← **CURRENT**` がなく、作業 WBS がすべて完了 (✅) であれば、この案件の合意フローは完了しています。
-->

# doxyfw 依存関係レポートのテストで再読み込み後にページ種別の保存値が失われる問題の検討

ファイル名: `261116-doxyfw-page-variant-reload-flake-discussion.md`

## 検討の識別

検討 ID: 261116-doxyfw-page-variant-reload-flake

版: 1

状態: 検討中

## 作業 WBS と進捗管理

この検討用 Markdown が管理する作業 WBS です。  
対策元の残課題一覧 (`app/porter/docs/prompts/current/261115-porter-multicast-src-contract-backlog.md`) の BL-003 を対象とし、進行の各段階で対策元の状態と経緯も更新します。  
項目 4 の内容は、[Q-001](#q-001-この案件で行う対処の範囲)、[Q-002](#q-002-保存値を初回だけ削除する方法)、[Q-003](#q-003-修正後の検証の担当と方法) の回答で見直します。

凡例: ⏸️ 未着手、🔄 実施中、🚫 ブロック中、⚠️ 要注意、✅ 完了。現在取り組んでいる項目の末尾に `← **CURRENT**` を付けます。

- 🚫 1. 検討用 Markdown のための情報収集と質問の実施
    - ✅ 1.1. 稼働中のセッション (c-modernization-kit-c1、96、0d) への着手の宣言と、支障がない旨の返信の受領
    - ✅ 1.2. 前提条件と要求事項の調査 (対策元 backlog の BL-003、`page_link_probe.js`、レポート側の保存処理、puppeteer 25.11.0 の該当実装の読解)
    - ✅ 1.3. リポジトリ外の一時スクリプトによる再現の試行 (Windows、Edge 157、30 回)
    - ✅ 1.4. 確認項目 ([Q-001](#q-001-この案件で行う対処の範囲)、[Q-002](#q-002-保存値を初回だけ削除する方法)、[Q-003](#q-003-修正後の検証の担当と方法)) の作成
    - ✅ 1.5. 対策元 backlog の BL-003 を「検討中」へ更新 (メタ情報は c-modernization-kit-96 に連絡してから「下流文書」だけを追記)
    - 🚫 1.6. [Q-001](#q-001-この案件で行う対処の範囲)、[Q-002](#q-002-保存値を初回だけ削除する方法)、[Q-003](#q-003-修正後の検証の担当と方法) の回答の受付と記録 (停止理由: ユーザーの回答待ち) ← **CURRENT**
    - ⏸️ 1.7. 回答に基づく前提・制約の検証と WBS の見直し (合意した方針を対策元 backlog の BL-003 へ反映)
- ⏸️ 2. 前提合意と残懸念の解消 (第 1 ゲート: 最終仕様作成への着手)
    - ⏸️ 2.1. 全論点に対する未解決事項および質問の解消確認
    - ⏸️ 2.2. 方針・前提条件の合意確定 (懸念がないことをもってフェーズ 2 へ着手)
- ⏸️ 3. 最終決定事項 (最終仕様) の作成と承認の受付
    - ⏸️ 3.1. `261116-doxyfw-page-variant-reload-flake-design.md` の作成 (対策元 backlog の BL-003 へパスと方針を反映)
    - ⏸️ 3.2. 最終仕様における受入条件と整合性の確認
    - ⏸️ 3.3. 対話セッションにおける最終仕様 (design.md) の承認の受付 (第 2 ゲート: 作業着手の合意)
- ⏸️ 4. 承認された最終仕様に従った作業の実施
    - ⏸️ 4.1. `framework/doxyfw/bin_test/page_link_probe.js` の変更 (内容は [Q-001](#q-001-この案件で行う対処の範囲) と [Q-002](#q-002-保存値を初回だけ削除する方法) で決定)
    - ⏸️ 4.2. `framework/doxyfw/bin_test/test_generate_dependency_report.py` の変更 (診断出力の項目を検証に使う場合だけ)
    - ⏸️ 4.3. コード コメントへの永続的知見の反映 (解除に頼らない理由と根拠 URL)
    - ⏸️ 4.4. 局所テスト (担当と方法は [Q-003](#q-003-修正後の検証の担当と方法) で決定) と、変更した Markdown の機械的検証 (対策元 backlog の BL-003 を更新)
    - ⏸️ 4.5. 受入条件への適合確認 (全完確認)
    - ⏸️ 4.6. 残課題一覧 (`261116-doxyfw-page-variant-reload-flake-backlog.md`) の再構築と整理 (対策元 backlog の最終状態の確定)
- ⏸️ 5. 成果物の承認の受付 (第 3 ゲート)
    - ⏸️ 5.1. 成果物・検証結果・残課題の提示
    - ⏸️ 5.2. 対話セッションにおける成果物の承認の受付 (「承認」または「完了」の受領によるスキル完了)

## 対象と参照資料

対象成果物: `framework/doxyfw/bin_test/page_link_probe.js` (テストの補助スクリプト)。必要な場合は `framework/doxyfw/bin_test/test_generate_dependency_report.py`。

今回の対象範囲: 対策元 backlog の BL-003 への対処 (ユーザーの依頼: 「BL-003 への対処を行う」)。対処の範囲は [Q-001](#q-001-この案件で行う対処の範囲) で決定します。レポート本体 (`framework/doxyfw/templates/generate-dependency-report.py`) は対象外と考えています (根拠は「事前調査で確認した事実と見立て」)。

書き込み可能な検討用 Markdown: この文書 (`framework/doxyfw/docs/prompts/current/261116-doxyfw-page-variant-reload-flake-discussion.md`)

参照資料と版:

- 対策元の残課題一覧: `app/porter/docs/prompts/current/261115-porter-multicast-src-contract-backlog.md` の BL-003
- 過去の記録: `app/general/docs/prompts/past/261111-ci-time-backlog-followup-backlog.md` の BL-006 (run 42978073210 の同じテストの失敗。原因不明として閉じた)
- doxyfw: `2c887ff` (現在の作業ツリー。変更なし)
    - `framework/doxyfw/bin_test/page_link_probe.js`
    - `framework/doxyfw/bin_test/test_generate_dependency_report.py` の `OverviewInteractionTest.test_page_link_and_variant_settings` (2923 行目から)
    - `framework/doxyfw/templates/generate-dependency-report.py` の `loadPageVariant()` と `setPageVariant()` (6322 行目から)
- puppeteer 25.11.0 (ローカルの導入先 `puppeteer-core/lib/puppeteer/cdp/`): `FrameManager.js`、`CdpPreloadScript.js`
- CI: run 43767517941 attempt 1 の ol8 ジョブ (headless の Chrome 153)。ログは対策元 backlog の記載 (c-modernization-kit-96 の調査結果) を参照し、このセッションでは取得していません。

## 事前調査で確認した事実と見立て

ソースを読んで確認した事実と、実行で裏付けていない見立てを分けて記載します。

### ソースで確認した事実

- `page_link_probe.js` の `newReportPage()` は、`clearVariant` が指定されると、保存値を削除するスクリプトを `page.evaluateOnNewDocument()` で登録します (72 行目)。このスクリプトは、ページの文書が作られるたびに、ページ本体のスクリプトより先に実行されます。初回の遷移の後、`page.removeScriptToEvaluateOnNewDocument()` で登録を解除します (82 行目)。
- 解除が効いていなければ、169 行目の `page.reload()` で削除スクリプトが再び実行され、保存値 `ja-details` が消えます。この場合、再読み込み後のページも、その後に開き直したページ (削除スクリプトを登録しない) も、保存値を読めません。CI の診断出力 (再読み込み後の最初の読み取りで `None`、開き直した後も `None`、読み取りの例外なし) と一致します。
- puppeteer 25.11.0 の `removeScriptToEvaluateOnNewDocument()` (`FrameManager.js` 337 行目から) は、フレームごとに `preloadScript.getIdForFrame(frame)` で識別子を探し、見つからないフレームには解除の要求を送りません。エラーも出しません。識別子は、登録時のメインフレームのオブジェクトをキーにした `WeakMap` に入っています (`CdpPreloadScript.js`)。
- 同じ `FrameManager.js` の `#onFrameNavigated()` (437 行目から) は、遷移の通知に含まれるフレーム ID が既知でない場合、メインフレームのオブジェクトを新しく作ります。この場合、登録時のオブジェクトと一致しなくなり、解除の要求は送られません。
- レポート本体の `setPageVariant()` は `localStorage.setItem()` を同期的に呼ぶだけで、テストは保存後に 200 ミリ秒待ち、さらに保存値を読み取って確認してから再読み込みしています。
- `removeScriptToEvaluateOnNewDocument` と `localStorage` の `removeItem` を使うテストは、`framework` 配下の `bin_test` では `page_link_probe.js` だけです。
- テストは `puppeteer.launch()` でブラウザーを毎回起動します。保存領域は起動ごとの一時プロファイルにあるため、最初のページ (127 行目) を開く時点では、保存値はもともとありません。削除が必要なのは、`ja-details` を保存した後に開く英語環境のページ (189 行目) と動的発行のページ (207 行目) です。

### 見立て (実行での裏付けなし)

- 原因は、初回の遷移 (`about:blank` から `file://`) でメインフレームの ID が変わる場合があり、そのとき解除が行われず、再読み込みで削除スクリプトが再実行されたこと、と考えています。ID が変わる条件は特定していません。
- もう 1 つの候補 (保存がブラウザー側へ確定する前の再読み込み) は、可能性が低いと考えています。保存の確定が遅れただけであれば、値は後から届くはずですが、開き直したページでも値がないためです。ただし、現在の診断出力では否定できません。

### 再現の試行

リポジトリ外の一時ディレクトリに、`page_link_probe.js` と同じ順序 (削除スクリプトの登録、遷移、解除、保存、再読み込み) を行うスクリプトを作り、Windows の Edge 157 (headless) で 30 回実行しました。30 回とも、メインフレームのオブジェクトは遷移の前後で同じで、削除スクリプトは 1 回だけ実行され、保存値は維持されました。この環境では再現していません。CI と同じ ol8 の Chrome 153 では試していません。

## 現行の合意内容

- 対策元 backlog の BL-003 に対処します (ユーザーの依頼、2026-11-16)。
- 稼働中のほかのセッションへ宣言し、返信を受けてから作業を始めます (ユーザーの依頼、2026-11-16)。c1、96、0d の 3 セッションから「支障なし」の返信を受けました。
- 対策元 backlog は、BL-003 の行と節だけを置換します。メタ情報は、更新の前に c-modernization-kit-96 へ連絡します (96 と 0d からの依頼)。

上記以外は未確定です。

## 観点別の確認

| 観点 | 状態 | 根拠・関連 Q |
| --- | --- | --- |
| 目的・利用者 | 確認済み | CI の不定期な失敗をなくす (対策元 backlog の BL-003「本来あるべき姿」) |
| 範囲・境界 | 未解決 | [Q-001](#q-001-この案件で行う対処の範囲) |
| 入力・根拠 | 確認済み | 「対象と参照資料」。原因は見立てであり、確定していません |
| 整合性・依存関係 | 未解決 | [Q-002](#q-002-保存値を初回だけ削除する方法) (テストの確認内容 3 と 4 を維持する方法) |
| 実現性・例外 | 未解決 | [Q-002](#q-002-保存値を初回だけ削除する方法) |
| 受入条件・検証 | 未解決 | [Q-003](#q-003-修正後の検証の担当と方法) |

## 質問一覧

| Q-ID | 論点 | 状態 | 依存・関連 |
| --- | --- | --- | --- |
| [Q-001](#q-001-この案件で行う対処の範囲) | この案件で行う対処の範囲 | 未回答 | なし |
| [Q-002](#q-002-保存値を初回だけ削除する方法) | 保存値を初回だけ削除する方法 | 未回答 | [Q-001](#q-001-この案件で行う対処の範囲) |
| [Q-003](#q-003-修正後の検証の担当と方法) | 修正後の検証の担当と方法 | 未回答 | [Q-001](#q-001-この案件で行う対処の範囲) |

## 明確化のための確認項目

### Q-001 この案件で行う対処の範囲

**Status**

未回答

**Question**

この案件で、原因を区別する診断出力の追加と、解除に頼らない形への修正の、どこまでを行いますか。

**Context**

- **経緯と背景**: 原因の候補は 2 つあります。候補 1 は、初回だけ実行するはずの削除スクリプトが再読み込みでも実行されたことです。候補 2 は、保存がブラウザー側へ確定する前に再読み込みしたことです。現在の診断出力では区別できず、ローカルでも再現していません。対策元 backlog の恒久対応案は、「まず診断出力を加えて区別し、原因に応じて修正する」という 2 段階です。
- **判断が必要な理由**: 診断だけを先に入れると、次に CI で失敗するまで修正できません。失敗は不定期で、ol8 ジョブの再実行は 1 回あたり約 2 時間 40 分かかります。一方、候補 1 への修正 (解除に頼らない削除) は、候補 1 が原因でなくても害がなく、解除の成否に左右される箇所をなくせます。候補 2 が原因だった場合は、修正後も再発します。そのときに原因を確定できるよう、診断出力も残す案が A です。
- **各案の違い**: A は、修正と診断を 1 回の変更で入れます。再発しなければ解決、再発すれば診断出力から候補 2 かどうかを判断できます。B は、原因を確定してから修正しますが、次の失敗を待ちます。C は、修正だけを入れ、再発したときの手掛かりは今と同じです。

**Answer**

選択方式: 単一選択

- [ ] A: (推奨) 解除に頼らない形への修正と、削除スクリプトの実行回数と削除時点の値の診断出力を、同時に入れる。
- [ ] B: 診断出力だけを先に入れる。修正は、次の失敗で原因を確定してから別に行う。
- [ ] C: 解除に頼らない形への修正だけを入れる。診断出力は追加しない。
- [ ] D: その他
- [ ] X: 意図不明 (詳細な質問内容に再生成すること)

その他の回答 / 補足:

**Recommendation**

推奨: A  
理由: 開き直したページでも値がない点から、候補 1 が有力です。修正は補助スクリプト 1 つに収まり、候補 1 が原因でなくても副作用がありません。診断出力を残すので、再発した場合も次の 1 回で原因を判断できます。制約として、ローカルで再現していないため、修正の効果は CI を重ねて確認することになります。

### Q-002 保存値を初回だけ削除する方法

**Status**

未回答

**Question**

修正を行う場合、保存値を初回のページ表示の前にだけ削除する処理を、どの方法で実現しますか。

**Context**

- **経緯と背景**: テストは、「保存値がない状態から始める」ことと「再読み込みと開き直しで保存値が維持される」ことの両方を確認します。そのため、削除は初回の文書でだけ行い、再読み込みでは行わない必要があります。現在は、削除スクリプトの登録と解除でこれを実現しており、解除が効かないと保存値が消えます。[Q-001](#q-001-この案件で行う対処の範囲) で B を選んだ場合、この質問の回答は次の案件へ持ち越します。
- **現状のコード** (`page_link_probe.js` 69 行目から):

```javascript
  // 保存値の削除は初回だけ行い、再読み込み時には実行しない。
  let clearScript;
  if (options && options.clearVariant) {
    clearScript = await page.evaluateOnNewDocument(() => {
      try {
        window.localStorage.removeItem('doxyfw-dependency-page-variant');
      } catch (err) {
        window.__pageVariantClearError = String(err);
      }
    });
  }
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
  if (clearScript) await page.removeScriptToEvaluateOnNewDocument(clearScript.identifier);
```

- **案 A (タブごとの目印で初回だけ削除する)**: 削除スクリプトは登録したままにし、スクリプト自身が `sessionStorage` (タブごとの保存領域。再読み込みでは残り、別のタブには引き継がれない) の目印を見て、初回だけ削除します。解除の呼び出しはなくします。実行回数と削除時点の値も同じ場所に記録できるので、[Q-001](#q-001-この案件で行う対処の範囲) の診断出力と一体で実現できます。変更は `newReportPage()` の中だけです。

```javascript
    await page.evaluateOnNewDocument(() => {
      try {
        const runs = Number(window.sessionStorage.getItem('doxyfw-test-clear-runs') || '0') + 1;
        window.sessionStorage.setItem('doxyfw-test-clear-runs', String(runs));
        if (runs > 1) return;  // 再読み込みでは削除しない。
        const key = 'doxyfw-dependency-page-variant';
        window.sessionStorage.setItem('doxyfw-test-clear-saw', String(window.localStorage.getItem(key)));
        window.localStorage.removeItem(key);
      } catch (err) {
        window.__pageVariantClearError = String(err);
      }
    });
```

- **案 B (保存領域を分けて、削除をなくす)**: 削除スクリプトをなくします。最初のページは、ブラウザーの起動直後で保存値がもともとありません。英語環境のページと動的発行のページは、`browser.createBrowserContext()` で作る別の保存領域 (シークレット ウィンドウに相当) で開きます。削除処理がなくなるので、再実行の問題は起こりません。変更は `newReportPage()` と `run()` の両方に及びます。`file://` のページを別の保存領域で開く動作は、このテストでは未確認です。

```javascript
    // 4. localStorage 未保存の en 環境では既定が en (通常)
    const contextEn = await browser.createBrowserContext();
    const pageEn = await newReportPage(contextEn, withPageUrl, errors, { language: 'en-US' });
```

- **案 C (初回のページで削除してから読み込み直す)**: ページを 1 回開き、`page.evaluate()` で保存値を削除してから再読み込みし、そのページを「初回」として扱います。削除スクリプトの登録がなくなります。ページの読み込みが、削除するページごとに 1 回増えます。

```javascript
  await page.goto(url, { waitUntil: 'load' });
  if (options && options.clearVariant) {
    await page.evaluate(() => window.localStorage.removeItem('doxyfw-dependency-page-variant'));
    await page.reload({ waitUntil: 'load' });
  }
```

**Answer**

選択方式: 単一選択

- [ ] A: (推奨) タブごとの目印 (`sessionStorage`) で、初回だけ削除する。
- [ ] B: 保存領域を分けて、削除スクリプトをなくす。
- [ ] C: 初回のページで削除してから読み込み直す。
- [ ] D: その他
- [ ] X: 意図不明 (詳細な質問内容に再生成すること)

その他の回答 / 補足:

**Recommendation**

推奨: A  
理由: 変更が `newReportPage()` の中に収まり、テストの手順 (ページを開く回数と順序) が変わりません。削除スクリプトの実行回数と削除時点の値を同じ仕組みで記録でき、再発時に候補 1 と候補 2 を区別できます。リポジトリ外の一時スクリプトで、`sessionStorage` の値が再読み込み後も残ることは確認済みです (Windows、Edge 157)。制約として、削除スクリプトは再読み込みのたびに実行されるため、目印の読み取りに失敗した場合の動作を決める必要があります (失敗時は削除せず、エラーを診断出力に記録する想定)。

**Related**

[Q-001](#q-001-この案件で行う対処の範囲)

### Q-003 修正後の検証の担当と方法

**Status**

未回答

**Question**

変更後の局所テストは、誰が、どの方法で行いますか。

**Context**

- **経緯と背景**: ルートの `AGENTS.md` は、振る舞いを変更した場合に影響範囲の局所テストを求めています。一方、これまでの運用では、`make` と `make test` の実行確認はユーザーが担当しています。今回の対象は Python の `unittest` 1 件 (`OverviewInteractionTest.test_page_link_and_variant_settings`) で、`make` を使わずに単独で実行できます。Windows では `PYTHONUTF8=1` と `PUPPETEER_EXECUTABLE_PATH` の設定が必要です。
- **判断が必要な理由**: 不定期な失敗は、ローカルでは再現していません。ローカルで確認できるのは、「変更後もテストが成功すること」と「診断出力が期待どおりに出ること」までです。失敗がなくなったことは、プッシュ後の CI を重ねて確認することになります。CI の確認にはコミットとプッシュが必要で、どちらもユーザーの個別の指示を受けてから行います。

**Answer**

選択方式: 単一選択

- [ ] A: (推奨) エージェントが、対象のテスト 1 件を Windows で 10 回繰り返して実行する。CI での確認は、ユーザーの指示でコミットとプッシュをした後に行う。
- [ ] B: エージェントが、`framework/doxyfw/bin_test` のテスト全体を Windows で 1 回実行する。CI での確認は A と同じ。
- [ ] C: ユーザーが実行する。エージェントは実行しない。
- [ ] D: その他
- [ ] X: 意図不明 (詳細な質問内容に再生成すること)

その他の回答 / 補足:

**Recommendation**

推奨: A  
理由: 変更は `page_link_probe.js` だけで、このスクリプトを使うテストは対象の 1 件だけです。繰り返して実行すれば、変更が新しい不安定さを持ち込んでいないことを確認できます。10 回は、所要時間を数分に収めるための目安であり、不定期な失敗がなくなったことの証明にはなりません。

**Related**

[Q-001](#q-001-この案件で行う対処の範囲)

## 対象成果物と合意版

最終決定事項 (最終仕様) の設計書: `261116-doxyfw-page-variant-reload-flake-design.md`

検討用 Markdown の合意版 (第 1 ゲート): 未確定 (残懸念なし確認時に確定)

最終仕様 (design.md) の合意版 (第 2 ゲート): 未承認

更新予定の成果物: 未確定

受入条件: 未確定

## 反映と検証の記録

未着手。作業後の対応箇所、検証結果、未完了項目を記録します。
