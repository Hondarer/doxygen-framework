# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

このファイルは、このリポジトリでコードを扱う際の Claude Code (claude.ai/code) への指針を提供します。

## プロジェクト概要

これは、C ソースコードからドキュメントを生成する方法を実証する Doxygen ドキュメント学習プロジェクトです。プロジェクトには以下が含まれます。

- C 言語のシンプルな計算機関数
- ドキュメント生成用の Doxygen 設定
- マークダウンドキュメント用の Doxybook2 統合
- 日本語ドキュメント出力用のカスタムテンプレート

## 主要コマンド

### ドキュメント生成

```bash
cd doxyfw && make docs
```

このコマンドは以下の処理を順次実行します。

1. `../Doxyfile.part` が存在する場合、基本設定ファイルと結合して一時ファイルを作成し使用 (設定のオーバーライド対応)
2. `../prod` ディレクトリから C ソースファイルを解析し、`../xml/` に Doxygen XML ファイルと `../docs/doxygen/html/` に HTML ファイルを生成
3. `preprocess.sh` で XML ファイルを前処理 (PlantUML タグ、パラメータ direction 属性、linebreak タグを変換)
4. Doxybook2 で XML を `../docs-src/doxybook/` のマークダウンに変換 (カスタム日本語テンプレート使用)
5. `postprocess.sh` で `!include` ディレクティブを処理して関連コンテンツを統合

### クリーンアップ

```bash
cd doxyfw && make clean
```

生成されたドキュメント (`../docs/doxygen`、`../docs-src/doxybook`、`../xml`) を削除します。

## アーキテクチャ

### プロジェクト構造

```text
study-doxygen/
├── doxyfw/                    # ドキュメント生成環境
│   ├── makefile              # ドキュメント生成用 Makefile
│   └── config/               # 設定ファイル群
│       ├── Doxyfile          # Doxygen 設定
│       ├── doxybook-config.json  # Doxybook2 設定
│       └── templates/        # カスタム日本語テンプレート群
├── prod/src/                  # 実際の C ソースコード
│   ├── calculator.h/c        # 計算機 API (@ingroup public_api)
│   ├── samplestruct.h        # UserInfo 構造体定義
│   └── *.c                   # その他のサンプルコード
├── docs/doxygen/html/         # Doxygen 生成 HTML 出力
└── docs-src/doxybook/         # Doxybook2 生成マークダウン出力
```

### ソースコード構造

- `prod/src/calculator.h` - 関数宣言と `@ingroup public_api` による API 分類、ZERO_DEVIDE 定数定義
- `prod/src/calculator.c` - `@ingroup public_api` を使用した Doxygen コメント付きの実装
- `prod/src/samplestruct.h` - UserInfo 構造体とその他のサンプル定義

### ドキュメント生成パイプライン

1. Doxygen: C ソースファイルを解析し、`Doxyfile` 設定に基づいて XML ファイルと HTML ドキュメントを生成
2. プリプロセッシング: `preprocess.sh` スクリプトが変換前に XML ファイルを処理
3. Doxybook2: `doxyfw/config/doxybook-config.json` とカスタムテンプレートを使用して Doxygen XML をマークダウンに変換
4. ポストプロセッシング: `postprocess.sh` スクリプトが `!include` ディレクティブを処理して関連コンテンツを統合、不要ファイルを削除

### 主要設定ファイル

- `doxyfw/config/Doxyfile` - Doxygen 基本設定 (UTF-8 エンコーディング、全要素抽出、PlantUML 対応)
- `Doxyfile.part` - プロジェクト固有の設定オーバーライド (存在時は基本設定に追加結合)
- `doxyfw/config/doxybook-config.json` - Doxybook2 設定 (ソートあり、フォルダ使用なし、.md 拡張子)
- `doxyfw/config/templates/` - 日本語フォーマット用のカスタム Jinja2 テンプレート群

### 処理スクリプト詳細

#### preprocess.sh (前処理)

Doxybook2 変換前の XML ファイル前処理を実行します。

- PlantUML タグ（`<plantuml>` → "```plantuml\n@startuml"、`</plantuml>`→"@enduml\n```"）
- パラメータ direction 属性 (`direction="in"`→`[in]` プレフィックス追加)
- linebreak タグ（`<linebreak/>` → 改行文字への変換準備）

#### postprocess.sh (後処理)

Doxybook2 変換後の Markdown ファイル後処理を実行します。

- インクルードディレクティブ: `!include filename.md` でファイル内容を統合
- Markdown 整形: YAML フロントマター空行除去、連続空行統合、行末空白除去を処理
- ファイルクリーンアップ: 不要な `struct*.md`、`index_classes.md` 等を削除

### カスタムテンプレート

- `nonclass_members_details.tmpl` - API 出力セクション組織化のメインテンプレート
- `member_details.tmpl` - 関数・構造体等の個別要素書式設定
- `details.tmpl` - パラメータ・戻り値・警告等の共通書式

## 開発ガイド

### Doxygen 仕様とベストプラクティス

- 全パブリック関数に `@ingroup public_api` を付与して API をグループ化
- PlantUML サポート (前提: `Doxyfile` に `PLANTUML_JAR_PATH` が設定されていること)
- UTF-8 エンコーディングで日本語コメント対応
- 関数宣言はヘッダーで簡潔に、詳細実装コメントは .c ファイルに記述
- プロジェクト固有設定は `Doxyfile.part` で上書き (PROJECT_NAME 等)

### テンプレート開発時の注意点

- `!include` ディレクティブで関連コンテンツ統合 (例: 構造体詳細をグループページに統合)
- 相対パス・絶対パス両方をサポート
- デバッグ時は `postprocess.sh` 内の `set -x` のコメントアウト解除
