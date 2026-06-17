# ソース origin ヒントの埋め込み

## 概要

Doxybook2 が生成する `Files/` 配下の Markdown は `.gitignore` 対象であり、生成物そのものは Git で追跡されない。
これらの Markdown は実際には各ソース ファイル (C や C++ などのプログラム、あるいは Markdown) から生成される。
そこで `templates/inject-source-origin.py` が、生成 Markdown の先頭フロントマターに元ソースのパスを `git-origin` キーとして埋め込む。
docsfw 側はこのヒントを使い、生成 Markdown が `.gitignore` 対象であっても、追跡済みの元ソースへの Git リンクを表示できる。

## 解決の仕組み

`Files/` 配下の各 Markdown は、その Markdown 自身のパス (`Files/` からの相対) が Doxygen の INPUT 相対ソース パスと一致する。
Doxygen 実行ディレクトリ `DOXYGEN_RUNDIR` を基準に実在判定することで、プログラムと Markdown を統一した規則で元ソースに解決する。

`Files/` 配下の相対パス `P` に対する候補規則は次のとおり。

- `C1` は `P` の末尾 `.md` を除去したもの。プログラムやヘッダー用 (`include/calc.h.md` から `include/calc.h`)
- `C2` は `P` そのもの。Markdown ソース用 (`src/markdown_sample.md`)
- `DOXYGEN_RUNDIR/C1` が実在すれば `C1`、無ければ `DOXYGEN_RUNDIR/C2` が実在すれば `C2` を元ソースとする

解決した元ソースを `WORKSPACE_DIR` 相対パスに正規化し、フロントマター キー `git-origin` に書き込む。

```yaml
---
short-title: "calc.h"
git-origin: "app/calc/prod/include/calc.h"
---
```

トップレベルの `Files/README.md` は Doxybook2 が生成するファイル一覧の索引であり実ソースではないため除外する。
サブフォルダーの `README.md` (例 `Files/src/image/README.md`) は実ソースなので対象とする。

## 実行タイミング

`templates/postprocess.sh` の `restructure-files.py` 実行直後に呼び出す。
`Files/` の再編が完了し、各 Markdown のパスが INPUT 相対ソース パスと一致した後である必要がある。

```text
python3 "$SCRIPT_DIR/inject-source-origin.py" "$MARKDOWN_DIR" "$DOXYGEN_RUNDIR" "$WORKSPACE_ROOT"
```

## docsfw 側の連携

docsfw の発行処理は、対象 Markdown のフロントマターから `git-origin` を読み取り、`${workspaceFolder}/${git-origin}` が実体として存在すれば、その元ソースに対して Git リンクを解決する。
詳細は docsfw 側の `docs/git-link.md` を参照すること。
