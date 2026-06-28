# 依存関係レポート

このドキュメントでは、Doxygen XML から関数間の呼び出し関係を解析し、依存度の低い関数から確認できるようにするレポート機能について説明します。

## 目的

依存関係レポートは、リファクタリングやレビューで確認する関数の順序を決めるための補助データを生成します。

対象範囲は、1 回の Doxygen 実行で生成された XML に含まれる関数です。  
対象範囲内の他関数を呼び出さない関数を依存度の低い関数として扱い、その関数を呼ぶ側へ向かって依存 level を上げます。

このレポートは、変更リスクを完全に判定するものではありません。  
Doxygen が XML に出力した `references` と `referencedby` に基づくため、関数ポインター、マクロ経由、条件付きコンパイルで隠れた呼び出し、対象範囲外ライブラリへの呼び出しは分析対象に含まれない場合があります。

## 生成タイミング

レポート生成は doxyfw の make パイプラインに組み込まれています。

```text
Doxygen 実行
dependency report 生成
merge-member-docs.py
extract-graphs.py
preprocess.sh
doxybook2
postprocess.sh
```

`generate-dependency-report.py` は Doxygen XML が存在する段階で実行されます。  
そのため、doxybook2 が存在しない環境でも Doxygen XML が生成されていればレポートは生成されます。

## 出力先

出力先は Doxygen HTML の出力ディレクトリ配下です。

| 実行条件 | 出力先 |
|---|---|
| `CATEGORY` なし | `pages/doxygen/dependency/` |
| `CATEGORY=calc` | `pages/doxygen/calc/dependency/` |
| `CATEGORY=calc SUBCATEGORY=internal` | `pages/doxygen/calc_internal/dependency/` |

生成ファイルは以下の通りです。

| ファイル | 用途 |
|---|---|
| `index.html` | ブラウザーで閲覧する HTML レポート |
| `dependency-data.js` | HTML が読み込む分析データ |
| `dependency-functions.csv` | 表計算や差分確認で使う関数一覧 |
| `dependency-files.csv` | ファイル別の関数数、level 分布、分類分布 |
| `cytoscape.min.js` | グラフ タブで使う Cytoscape.js |
| `cytoscape.LICENSE.txt` | Cytoscape.js のライセンス |

`dependency-data.js` は `window.DoxyfwDependencyData = ...;` 形式です。  
この形式にしている理由は、`file://` で HTML を直接開いた場合でもブラウザーの `fetch()` 制限を受けずに表示できるようにするためです。

## 入力データ

入力は Doxygen が生成した XML ファイルです。  
主に `memberdef kind="function"`、`location`、`references`、`referencedby` を読み取ります。

関数の識別には Doxygen の `id` を使います。  
ただし、Doxygen は file ページと group ページに同じ実体関数の `memberdef` を出力することがあります。  
その場合は、関数名、実体ファイル、行番号が同じ `memberdef` を同一関数として扱い、file ページ側を優先して統合します。

ソース リンクは、関数の実体ファイルに対応する Doxygen の `*_source.html` へ向けます。  
HTML リンクは、代表として採用した Doxygen `memberdef` のページへ向けます。

## 依存関係の扱い

呼び出し関係は `caller -> callee` の向きで扱います。

`references` に現れる対象範囲内の関数を呼び出し先とします。  
対象範囲外の関数は、現仕様では呼び出し先数や level 算出に含めません。

`referencedby` は Doxygen XML から読み取りますが、最終的な呼び出し元一覧は `references` から作った edge をもとに再構成します。  
この処理により、group ページ由来の重複 `memberdef` を統合した後も、呼び出し元数を一貫した形で算出できます。

## 依存 level

`dependencyLevel` は、依存種別に対応する基準値と、対象範囲内の呼び出し深さである `dependencyDepth` から算出します。  
`leaf-static` は `0`、`leaf-global` は `1` になり、呼び出し先を持つ分類は分類ごとの基準値に `dependencyDepth` を加えた値になります。

`dependencyDepth` は、対象範囲内の呼び出し先を持たない関数を `0` とします。  
呼び出し先を持つ関数は、呼び出し先の最大 `dependencyDepth` に `1` を加えた値になります。

`dependencyRank` は分類に対応する並び順の重みです。  
この重みを先に反映することで、`leaf-static`、`leaf-global`、`file-local`、`libsrc` 内のファイル間コール、`src` 内のファイル間コール、`libsrc` 以外から `libsrc` へのカテゴリまたぎコールが、この順に大きな level になります。

循環依存に属する関数は、数値 level を持ちません。  
HTML と CSV では `cycle` として扱います。

この level は「確認順の目安」です。  
`0` の関数は対象範囲内で他関数に依存しないため、先に確認しやすい候補です。  
一方で、呼び出し元が多い関数は影響範囲が大きい可能性があるため、`inScopeCallerCount` もあわせて確認します。

## 分類

`dependencyClass` は以下のいずれかです。

| 分類 | rank | 条件 |
|---|---:|---|
| `leaf-static` | 0 | `static` 関数で、対象範囲内の呼び出し先がない |
| `leaf-global` | 1 | 非 `static` 関数で、対象範囲内の呼び出し先がない |
| `file-local` | 2 | 呼び出し先があり、すべて同一ファイル内の対象範囲内関数である |
| `libsrc-file-caller` | 3 | `libsrc` 内で別ファイルの対象範囲内関数を呼び出す |
| `src-file-caller` | 4 | `src` 内で別ファイルの対象範囲内関数を呼び出す |
| `other-to-libsrc-caller` | 5 | `libsrc` 以外から `libsrc` の対象範囲内関数を呼び出す |
| `cross-area-caller` | 6 | 上記以外のカテゴリをまたいで対象範囲内関数を呼び出す |
| `cycle` | - | 循環依存グループに属する |

`static` 関数は C ファイル内に限定される場合が多いため、`leaf-static` は局所的に確認しやすい候補として扱えます。  
ただし、`static` であっても他関数を呼ぶ場合は、呼び出し関係に応じて `file-local` やファイル間コールの分類になります。

`libsrc` から `src` の対象範囲内関数を呼び出す関係は仕様上想定しません。  
この関係を検出した場合、分類は `cross-area-caller` として扱い、レポート生成時に `Warning: reverse-boundary-caller detected` で始まる警告を出力します。

ファイルのカテゴリは、パスのセグメントで判定します。  
`libsrc` を含むパスは `libsrc`、`src` を含むパスは `src`、`include` を含むパスは `include`、それ以外は `other` です。

1 つの関数が複数種別の呼び出しを持つ場合は、最も rank が大きい呼び出し種別を `dominantCallKind` とし、`dependencyClass` に採用します。

## 循環依存

循環依存は strongly connected component として検出します。  
2 つ以上の関数が相互に到達できる場合、または自己呼び出しがある場合、その関数は `cycle` に分類されます。

循環グループは `dependency-data.js` の `sccs` に出力されます。  
CSV では各関数の `sccId` に循環グループ ID が入ります。

## HTML レポート

`index.html` はローカル閲覧と GitHub Pages の両方で動作する静的 HTML です。  
グラフ表示には、生成先へ同梱する Cytoscape.js を使います。  
外部 CDN には依存していません。

画面上部には、関数数、呼び出し関係数、ファイル数、`export` 関数数、`static` 関数数、leaf 関数数、循環グループ数を表示します。
画面上部のテーマ切り替えボタンで、ライト モードとダーク モードを切り替えられます。
初回表示ではブラウザーの配色設定を参照し、切り替え後は選択したテーマを同じブラウザーに保存します。

画面は `一覧`、`全体マップ`、`リンケージ` の 3 タブで構成します。

`一覧` タブの関数一覧では以下の列を表示します。

| 列 | 意味 |
|---|---|
| `level` | 依存 level または `cycle` |
| `分類` | `dependencyClass` |
| `export` | 公開 `include` 配下のヘッダーにある関数なら `yes` |
| `static` | static 関数なら `yes` |
| `領域` | 関数の実体ファイルのカテゴリ |
| `関数` | 関数名 |
| `ファイル` | 実体ファイル |
| `呼び出し先` | 対象範囲内の呼び出し先数 |
| `呼び出し元` | 対象範囲内の呼び出し元数 |
| `他ファイル` | 他ファイルの対象範囲内関数を呼び出す数 |

検索欄では関数名とファイル名を検索できます。  
level、分類、ファイルのフィルターも利用できます。

表は列見出しのクリックでソートできます。  
同じ列を再度クリックすると、昇順と降順が切り替わります。  
初期表示では `level` の昇順を選択します。  
同じ値を持つ行は、レポート生成時の決定論的な基本順序で並びます。

関数行を選択すると、詳細領域に基本情報、`rank`、`depth`、領域、呼び出し種別、`export`、Doxygen ページへのリンク、ソース ページへのリンク、1 hop の呼び出し先、1 hop の呼び出し元を表示します。  
Doxygen ページへのリンクは `doxyfw-dependency-doxygen`、ソース ページへのリンクは `doxyfw-dependency-source` を `target` に指定し、それぞれ用途別の別タブまたは別ウィンドウを再利用します。  
呼び出し先と呼び出し元の関数名は、Doxygen ページへのリンクではなく、同じ表の関数選択として動作します。

近傍項目から選択した関数が現在のフィルター条件で非表示になる場合でも、詳細領域はその関数へ遷移します。  
この場合は表の上に「現在のフィルターでは選択行は非表示です。」と表示し、`フィルター解除` ボタンで選択中の関数を表に再表示できます。

`全体マップ` タブでは、ファイルをノード、ファイル間の呼び出し関係を edge として表示します。  
同じファイル間に複数の関数呼び出しがある場合は edge を集約し、呼び出し数をラベルに表示します。  
ファイル ノードを選択すると、そのファイルの関数一覧と代表分類を表示します。
マップ背景の右クリック メニューから、現在の表示範囲またはマップ全体を SVG として保存できます。

`リンケージ` タブでは、選択中の関数を中心に、呼び出し元 2 hop と呼び出し先 2 hop を表示します。  
edge の向きは `caller -> callee` です。  
ノードを選択すると、同じ関数選択として一覧と詳細領域へ反映します。

グラフ タブでは、`Fit`、`中心へ移動`、`レイアウト再実行` を利用できます。  
リンケージでは、`breadthfirst` と `cose` のレイアウトを切り替えられます。

## CSV の列

`dependency-functions.csv` の列は以下の通りです。

| 列 | 意味 |
|---|---|
| `dependencyLevel` | 依存 level |
| `dependencyRank` | 分類に対応する依存種別の重み |
| `dependencyDepth` | 対象範囲内の呼び出し深さ |
| `dependencyClass` | 分類 |
| `sourceArea` | 関数の実体ファイルのカテゴリ |
| `maxCalleeArea` | 最も rank が大きい呼び出し先のカテゴリ |
| `dominantCallKind` | 分類に採用した呼び出し種別 |
| `isExported` | 公開 `include` 配下のヘッダーにある関数かどうか |
| `isStatic` | static 関数かどうか |
| `name` | 関数名 |
| `file` | 実体ファイル |
| `line` | 実体の開始行 |
| `inScopeCalleeCount` | 対象範囲内の呼び出し先数 |
| `inScopeCallerCount` | 対象範囲内の呼び出し元数 |
| `sameFileCalleeCount` | 同一ファイル内の呼び出し先数 |
| `crossFileCalleeCount` | 他ファイルの呼び出し先数 |
| `sccId` | 循環グループ ID |
| `id` | Doxygen の関数 ID |
| `htmlUrl` | Doxygen HTML ページへの相対 URL |
| `sourceUrl` | Doxygen ソース ページへの相対 URL |

`dependency-files.csv` の列は以下の通りです。

| 列 | 意味 |
|---|---|
| `path` | ファイル パス |
| `functionCount` | ファイル内の関数数 |
| `exportCount` | ファイル内の export 関数数 |
| `staticCount` | ファイル内の static 関数数 |
| `edgeCount` | ファイル内関数から対象範囲内関数への呼び出し数 |
| `dominantArea` | ファイル内で最も多い領域 |
| `levels` | level ごとの関数数を JSON 文字列で表した値 |
| `classes` | 分類ごとの関数数を JSON 文字列で表した値 |
| `areas` | 領域ごとの関数数を JSON 文字列で表した値 |

## データ形式

`dependency-data.js` の root オブジェクトは以下のキーを持ちます。

| キー | 内容 |
|---|---|
| `meta` | 生成時刻、対象 category、入力 XML、出力先など |
| `summary` | 件数の集計 |
| `functions` | 関数一覧 |
| `edges` | 呼び出し関係 |
| `files` | ファイル別集計 |
| `sccs` | 循環グループ |

`functions` の各要素は `dependency-functions.csv` と同等の情報を持ちます。  
`edges` の各要素は `caller`、`callee`、`sameFile`、`callKind`、`callerArea`、`calleeArea`、`callerFile`、`calleeFile` を持ちます。

## 利用手順

通常の Doxygen 生成を実行すると、レポートも同時に生成されます。

```bash
cd framework/doxyfw
CATEGORY=calc SUBCATEGORY=internal make
```

生成後、次の HTML をブラウザーで開きます。

```text
pages/doxygen/calc_internal/dependency/index.html
```

CSV を使う場合は、同じディレクトリの `dependency-functions.csv` と `dependency-files.csv` を参照します。

## 制限事項

本レポートは、Doxygen が認識した呼び出し関係だけを扱います。  
関数ポインター、マクロ展開後の呼び出し、プリプロセッサ条件で変わる呼び出しは、Doxygen XML に出ない場合があります。

対象範囲外の関数は level 算出に含めません。  
たとえば標準ライブラリや別カテゴリの関数を呼び出していても、同じ XML 出力に関数として含まれていなければ呼び出し先数には入りません。

依存 level は作業順序の候補を示す値です。  
変更時の安全性を保証する値ではないため、実際の変更ではテスト結果、公開 API かどうか、呼び出し元数、対象モジュールの責務をあわせて判断します。
