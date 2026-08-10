# 宣言側 Doxygen コメントの定義側への同期

このドキュメントでは、ヘッダーで宣言しソースで定義した関数の Doxygen コメントを、ソース側の Markdown ページにも反映する仕組み (`templates/merge-member-docs.py`) について説明します。

## 背景

非グループ関数をヘッダーで宣言し、ソースで定義した場合、Doxygen XML は次のように出力されます (実査で確定した挙動)。

- ソースを INPUT に含むビルド (internal) では、宣言側 (`*_8h.xml`) の memberdef に、宣言コメントと定義コメントが「宣言、定義」の順で統合済みになる。
- 定義側 (`*_8c.xml`) の memberdef は定義ローカルのコメントのみで、宣言側の detaileddescription が欠落する。
- 宣言側 memberdef の `<location>` は `file` がヘッダー、`bodyfile` がソースを指す。定義側は `file` がソース (`file == bodyfile`) で、`declfile` 属性を持たない。
- グループ メンバーはファイル コンパウンドに完全な memberdef を持たず、`<member refid="group__...">` 参照のみとなる場合がある。完全版は group XML にあり、`materialize-group-members.py` がソース ファイル XML へ複製する。

このため、Doxybook2 が描画する `Files/src/*.c.md` は宣言側の説明が欠落した状態になります。

## 処理内容

`templates/merge-member-docs.py` は、Doxybook2 変換前 (`extract-graphs.py` の直前) に、宣言側 (統合済み完全版) の brief / detailed / inbody のインナー XML を定義側 memberdef へ上書きコピーします。

- 対応付けのキーは `(name, argsstring, bodyfile)` です。`file != bodyfile` を宣言側、`file == bodyfile` を定義側と判定します。
- 宣言側はすでに「宣言、定義」の統合順になっているため、連結ではなく上書きコピーを行います (連結すると内容が二重化します)。
- public ビルド (INPUT が include のみ) はソース コンパウンドが存在しないため、本スクリプトは無動作です。

グループへ移動したメンバーは、`extract-graphs.py` の実行後に `templates/materialize-group-members.py` が処理します。  
このスクリプトは group XML の memberdef を定義元の `.c`、`.cc`、`.cpp`、`.cxx`、`.cs` ファイル コンパウンドへ複製し、`index.xml` の対応する参照を複製後の ID へ変更します。  
処理対象は関数に限定せず、定数、マクロ、変数、列挙型、型定義など、Doxygen が memberdef として出力するすべての種類です。  
構造体、クラス、共用体はファイル コンパウンドの `innerclass` 参照を Doxybook2 が通常どおり描画するため、複製しません。

宣言と定義が別ファイルにあるメンバーは、複製した memberdef の `location` を `bodyfile` と `bodystart` が示す定義位置へ変更します。  
宣言位置を示す `declfile` などの属性は保持します。  
この処理により、ソース側の Files ページではグループ セクションの追記ではなく、通常の関数、定数、型などのセクションにメンバーが表示されます。

依存関係レポートは `materialize-group-members.py` より前の Doxygen XML から生成します。  
したがって、複製した memberdef が依存関係の関数数や呼び出し関係へ追加されることはありません。

## 回帰サンプル

ワークスペースの `app/doxygen-sample/prod/include/merge.h` と `app/doxygen-sample/prod/src/merge.c` が回帰検証用のサンプルです。  
internal ビルドで `Files/src/merge.c.md` に宣言側の説明が反映されることを確認します。
