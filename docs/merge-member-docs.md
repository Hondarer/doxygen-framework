# 宣言側 Doxygen コメントの定義側への同期

このドキュメントでは、ヘッダーで宣言しソースで定義した関数の Doxygen コメントを、ソース側の Markdown ページにも反映する仕組み (`templates/merge-member-docs.py`) について説明します。

## 背景

非グループ関数をヘッダーで宣言し、ソースで定義した場合、Doxygen XML は次のように出力されます (実査で確定した挙動)。

- ソースを INPUT に含むビルド (internal) では、宣言側 (`*_8h.xml`) の memberdef に、宣言コメントと定義コメントが「宣言、定義」の順で統合済みになる。
- 定義側 (`*_8c.xml`) の memberdef は定義ローカルのコメントのみで、宣言側の detaileddescription が欠落する。
- 宣言側 memberdef の `<location>` は `file` がヘッダー、`bodyfile` がソースを指す。定義側は `file` がソース (`file == bodyfile`) で、`declfile` 属性を持たない。
- グループ関数はファイル コンパウンドに完全な memberdef を持たず `<member refid="group__...">` 参照のみとなる。完全版は group XML にあり、`inject-groups.py` が処理する。

このため、Doxybook2 が描画する `Files/src/*.c.md` は宣言側の説明が欠落した状態になります。

## 処理内容

`templates/merge-member-docs.py` は、Doxybook2 変換前 (`extract-graphs.py` の直前) に、宣言側 (統合済み完全版) の brief / detailed / inbody のインナー XML を定義側 memberdef へ上書きコピーします。

- 対応付けのキーは `(name, argsstring, bodyfile)` です。`file != bodyfile` を宣言側、`file == bodyfile` を定義側と判定します。
- 宣言側はすでに「宣言、定義」の統合順になっているため、連結ではなく上書きコピーを行います (連結すると内容が二重化します)。
- public ビルド (INPUT が include のみ) はソース コンパウンドが存在しないため、本スクリプトは無動作です。

## 回帰サンプル

ワークスペースの `app/doxygen-sample/prod/include/merge.h` と `app/doxygen-sample/prod/src/merge.c` が回帰検証用のサンプルです。  
internal ビルドで `Files/src/merge.c.md` に宣言側の説明が反映されることを確認します。
