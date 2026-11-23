<!--
生成元: agree-before-implement スキル
文書種別: 最終仕様 (design)
最終更新日時: 2026-11-16 12:41:10 JST
最終更新エージェント: claude code / セッション ID: session_01KJc53SqgNC8iDAi6rvzgwh
稼働 OS: Linux (WSL)
上流文書: `261116-doxyfw-page-variant-reload-flake-discussion.md` (検討用 Markdown)。削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。上流文書が存在する場合は、上流文書の再開手順に従って進行位置を確認し、判断の経緯を上流文書の Q&A で確認します。存在しない場合は、この文書を単体の最終仕様として扱います。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。
-->

# doxyfw 依存関係レポートのテストで再読み込み後にページ種別の保存値が失われる問題 最終仕様

ファイル名: `261116-doxyfw-page-variant-reload-flake-design.md`

## 目的

`framework/doxyfw/bin_test/test_generate_dependency_report.py` の `OverviewInteractionTest.test_page_link_and_variant_settings` が、CI の ol8 ジョブで不定期に失敗する問題をなくします。

## 問題の条件

テストの補助スクリプト `framework/doxyfw/bin_test/page_link_probe.js` は、次の条件をすべて満たすと、保存したページ種別 (`localStorage` のキー `doxyfw-dependency-page-variant`) を再読み込みで失います。

1. `puppeteer.launch()` で起動した直後のブラウザーで、最初のページを開く。
2. そのページの文書の開始時に、`page.evaluateOnNewDocument()` で登録したスクリプトが `localStorage.removeItem()` を実行する。
3. その後、同じキーへ値を保存し、`page.reload()` で再読み込みする。
4. CPU の負荷が高い。

失われた値は、同じブラウザーで開き直したページでも読めません。

> [!NOTE]
> 条件は、Oracle Linux 8.10 の Chrome for Testing 153.0.8010.36 (headless) と puppeteer 25.11.0 での再現試験で特定しました。CPU を 2 コアに絞り、空ループ 4 本で負荷をかけた状態で、対象のテストは 40 回中 10 回失敗しました。負荷なしの 40 回はすべて成功しました。削除スクリプトを登録しない場合は、同じ負荷の下で 60 回とも値を維持しました。削除スクリプトは、再読み込みでは再実行されていません。Chrome の内部で値が失われる理由は、確認していません。

## 変更の対象

| ファイル | 変更 |
| --- | --- |
| `framework/doxyfw/bin_test/page_link_probe.js` | 最初のページの削除指定を外す。診断出力を削除する。 |
| `framework/doxyfw/bin_test/test_generate_dependency_report.py` | 変更しない。 |
| `framework/doxyfw/templates/generate-dependency-report.py` (レポート本体) | 変更しない。文書の開始時に保存値を削除しないため、問題の条件を満たさない。 |

## page_link_probe.js の変更

### 最初のページの削除指定を外す

`run()` が最初に開くページ (確認内容 1 から 3 と 5 に使うページ) は、`clearVariant` を指定せずに開きます。  
テストは 1 回ごとにブラウザーを起動し、保存領域は起動ごとの一時プロファイルにあります。最初のページを開く時点で保存値はないため、削除しなくても「保存値がない状態から始める」という前提を満たします。

```javascript
    // 1-3, 5: page 対応レポート (ja 環境、localStorage 未保存の状態から開始)
    // 起動直後のブラウザーには保存値がないため、clearVariant を指定しない。
    const page = await newReportPage(browser, withPageUrl, errors, { language: 'ja-JP' });
```

英語環境のページ (確認内容 4) と動的発行のページ (確認内容 7) は、保存値 `ja-details` が残っている状態で開くため、`clearVariant: true` を指定したままにします。これらのページは、開いた後に保存と再読み込みを行わないため、問題の条件を満たしません。  
`newReportPage()` の削除スクリプトの登録と、初回の遷移の後の解除は、現状のままにします。

### 診断出力を削除する

次の診断出力を、すべて削除します。

| 削除する対象 | 場所 |
| --- | --- |
| `window.__pageVariantReads` と `window.__storageAccessErrors` の初期化 | `newReportPage()` の文書の開始時のスクリプト |
| `window.localStorage` の取得を包み、例外を記録する処理 | 同上 |
| `Storage.prototype.getItem` を置き換え、読み取りの履歴を記録する処理 | 同上 |
| 削除スクリプトの例外を `window.__pageVariantClearError` へ記録する処理 | `newReportPage()` の削除スクリプト |
| 関数 `pageVariantDiagnostics()` | ファイルの直下 |
| `beforeReload`、`afterReload`、`afterReopen` の取得 | `run()` |
| 結果の JSON の `pageVariantDiagnostics` (`browserVersion` を含む) | `run()` の戻り値 |

削除スクリプトの `catch` 節は、例外を記録せず、理由のコメントだけを置きます。

```javascript
    clearScript = await page.evaluateOnNewDocument(() => {
      try {
        window.localStorage.removeItem('doxyfw-dependency-page-variant');
      } catch (err) {
        // localStorage が使えない環境では何もしない
      }
    });
```

文書の開始時のスクリプトに残すのは、テスト用の目印 (`window.__DEP_REPORT_TEST__`)、コピーした文字列の受け皿 (`window.__copiedText`)、`navigator.clipboard` の差し替え、`navigator.language` の差し替えです。

### 残す検証

次の検証は、変更しません。結果の JSON の `hrefAfterReload` と `hrefAfterReopen` も残します。

- 確認内容 3a: 同じページを再読み込みしても `ja-details` が維持される。
- 確認内容 3b: ページを閉じた後、別ページで開いても `ja-details` が維持される。
- テスト側の `subTest` による `operation="reload"` と `operation="reopen"` の分離。

## 知見の反映計画

永続的に必要な知見は、`page_link_probe.js` のコード コメントへ反映します。正本ドキュメントへの反映はありません。

| 反映先 | 内容 |
| --- | --- |
| `newReportPage()` の削除スクリプトの登録の直前 | `clearVariant` は、保存値が残っている状態で開くページにだけ指定すること。起動直後のブラウザーで文書の開始時に `removeItem` を実行すると、その後に保存した値が再読み込みで失われる場合があること (Chrome 153 で、CPU の負荷が高いときに確認)。 |
| `run()` の最初のページを開く行の直前 | 起動直後のブラウザーには保存値がないため、`clearVariant` を指定しないこと。 |

> [!IMPORTANT]
> この知見には、根拠として示せる公開の URL がありません。Chrome の内部の原因を確認していないためです。コード コメントには `see:` を付けず、確認した条件 (ブラウザーの版と負荷) を記載します。原因の追究は、残課題一覧 (`261116-doxyfw-page-variant-reload-flake-backlog.md`) の BL-001 に記録します。

## 検証

検証は、WSL 上の Oracle Linux 8 と Chrome for Testing 153 で行います。`make` は使いません。  
繰り返しの実行は `grok --yolo` の effort high へ委譲し、結果の確認は主エージェントが行います。

対象のテストの実行方法:

```bash
cd framework/doxyfw/bin_test
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
    test_generate_dependency_report.OverviewInteractionTest.test_page_link_and_variant_settings
```

負荷ありの条件: `taskset -c 0,1` で CPU を 2 コアに絞り、同じ 2 コアで空ループを 4 本動かした状態で、テストも `taskset -c 0,1` を付けて実行します。

CI での確認は、ユーザーの指示でコミットとプッシュをした後に行います。

## 受入条件

1. 対象のテスト 1 件が、負荷ありの 40 回と、負荷なしの 10 回で、すべて成功する。
2. `page_link_probe.js` に、`__pageVariantReads`、`__storageAccessErrors`、`__pageVariantClearError`、`pageVariantDiagnostics` の文字列が残っていない。
3. `page_link_probe.js` の最初のページを開く呼び出しに `clearVariant` がなく、英語環境のページと動的発行のページの呼び出しには `clearVariant: true` がある。
4. `test_generate_dependency_report.py` と `generate-dependency-report.py` に差分がない。
5. 変更した Markdown が、`text_style_jp.py --dry-run` で指摘なしになる。
6. 残課題一覧に Chrome の内部の原因の追究が記録され、対策元の残課題一覧 (`app/porter/docs/prompts/past/261115-porter-multicast-src-contract-backlog.md`) の BL-003 に、対処の内容と確認結果が記録されている。
