# doxygen-framework

Doxygen と Doxybook2 を連携させ、ソース コードから HTML 仕様書や Markdown ドキュメントを生成するフレームワークです。

共通の Doxygen 設定や Doxybook2 テンプレートのほか、公開 API と内部仕様に応じたドキュメントの出し分け、ヘッダーとソースのコメント同期、出力の前後処理を提供します。

## 重要な文書

### コメントの記述

ソース コードに Doxygen コメントを記述・確認する際に参照します。

- [Doxygen 記法の要点](cheatsheet.md) - コメント構文の雛形と基本的な書き方
- [コマンド一覧](commands.md) - サポートする Doxygen コマンドの一覧と仕様

### 生成の構成と実行

各 app でドキュメントを生成する際、および公開・内部の出し分けを構成する際に参照します。

- [ドキュメントの性質に応じた出し分け](document-separation.md) - 公開 API と内部仕様の分離構成、コメント同期
- [makefile の利用方法](makefile-usage.md) - make コマンドによる生成手順とオプション
- [入力ファイルの選択](choose-input.md) - Doxyfile での解析対象ディレクトリ指定方法

### フレームワークの保守

doxyfw のテンプレートやスクリプトを変更する際に参照します。

- [生成処理の保守と検証](maintenance-verification.md) - 変更時の出力比較と検証手順

## 文書一覧

\toc depth=-1 exclude-basedir=true
