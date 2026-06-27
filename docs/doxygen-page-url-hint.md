# Doxygen ページ URL ヒントの埋め込み

## 概要

Doxybook2 が生成する `Files/` 配下の Markdown には、同じ入力から Doxygen が生成した HTML の単一ページが対応することが多い。  
`templates/inject-doxygen-url.py` は Doxygen tag file を読み取り、生成 Markdown の先頭 front matter に対応 HTML へのパスを `doxygen-page-url` キーとして埋め込む。  
docsfw 側はこのヒントを使い、HTML のナビバーに Doxygen 単一ページへのリンクを表示できる。

## 解決の仕組み

Doxygen の `GENERATE_TAGFILE` で生成される tag file には、ソース ファイルとページの `compound` 情報が含まれる。  
`inject-doxygen-url.py` は `compound kind="file"` からファイル パスと HTML ファイル名の対応を作り、`compound kind="page"` から Markdown ページと HTML ファイル名の対応を作る。

`Files/` 配下の相対パス `P` に対する候補規則は次のとおり。

- `P` の末尾 `.md` を除去して file map を引く。
- `P` そのもので file map を引く。
- `md_` と basename を組み合わせて page map を引く。
- `md_` と拡張子なしの相対パスを `_` でつないだ名前で page map を引く。

解決した HTML ファイル名は、Doxygen HTML 出力ディレクトリを基準に workspace ルート相対パスへ変換する。  
現行設定では Doxygen HTML は `pages/doxygen/<CATEGORY_ID>/` 直下に出力される。

```yaml
---
short-title: "calc.h"
doxygen-page-url: "pages/doxygen/calc_public/calc_8h.html"
---
```

トップレベルの `Files/README.md` は Doxybook2 が生成するファイル一覧の索引であり実ソースではないため除外する。  
サブフォルダーの `README.md` は入力 Markdown として扱われるため、tag file から解決できる場合は対象にする。

## 実行タイミング

`templates/postprocess.sh` は `inject-source-origin.py` の直後に `inject-doxygen-url.py` を呼び出す。  
この時点では Pages 由来の Markdown が `Files/` に統合済みであり、Doxybook2 の出力構造が最終形に近い。

```text
python3 "$SCRIPT_DIR/inject-doxygen-url.py" "$MARKDOWN_DIR" "$DOXYFW_TAGFILE" "$DOXYFW_HTML_ROOT" "$WORKSPACE_ROOT"
```

`makefile` は Doxygen 実行時に `GENERATE_TAGFILE` を `$(XML_DIR)/doxyfw.tag` へ上書きする。  
tag file は postprocess で参照するため、`XML_DIR` は postprocess の後で削除する。

## docsfw 側の連携

docsfw の発行処理は、対象 Markdown の front matter から `doxygen-page-url` を読み取る。  
値が存在し、`doxygenLinkEnable` が `true` の場合、出力 HTML から Doxygen HTML への相対 URL を計算してナビバーにリンクを表示する。  
詳細は docsfw 側の `docs/doxygen-link.md` を参照すること。
