# Makefile 使用方法

このドキュメントでは、doxyfw の Makefile の使用方法とオプションについて説明します。

## 基本的な使用方法

### ドキュメント生成

```bash
cd doxyfw
make
```

このコマンドは以下の処理を順次実行します。

1. 既存のドキュメントをクリーンアップ
2. Doxygen で C ソースコードを解析し、HTML と XML を生成
3. XML ファイルを前処理
4. Doxybook2 で Markdown に変換
5. Markdown ファイルを後処理

### クリーンアップ

```bash
cd doxyfw
make clean
```

生成されたドキュメント (`docs/doxygen`、`docs-src/doxybook`、`xml`) を削除します。

## CATEGORY オプション

`CATEGORY` オプションを使用すると、ドキュメントを大分類ごとに生成できます。これにより、同一プロジェクト内で複数種類のドキュメントを管理できます。

### 概要

- **オプション名**: `CATEGORY`
- **デフォルト値**: 空 (大分類なし)
- **用途**: API ドキュメント、内部仕様書、テストドキュメントなど、異なる種類のドキュメントを分類して生成

### 動作仕様

#### CATEGORY 未指定時 (デフォルト)

```bash
cd doxyfw
make
```

- **使用する設定ファイル**: `../Doxyfile.part`
- **HTML 出力先**: `../docs/doxygen/`
- **Markdown 出力先**: `../docs-src/doxybook/`
- **XML 中間ファイル**: `../xml/` (処理後削除)

#### CATEGORY 指定時

```bash
cd doxyfw
make CATEGORY=api
```

- **使用する設定ファイル**: `../Doxyfile.part.api`
- **HTML 出力先**: `../docs/doxygen/api/`
- **Markdown 出力先**: `../docs-src/doxybook/api/`
- **XML 中間ファイル**: `../xml/api/` (処理後削除)

### 使用例

#### API ドキュメント生成

```bash
cd doxyfw
make CATEGORY=api
```

このコマンドは `Doxyfile.part.api` を使用し、API 向けのドキュメントを生成します。

#### 内部仕様ドキュメント生成

```bash
cd doxyfw
make CATEGORY=internal
```

このコマンドは `Doxyfile.part.internal` を使用し、内部仕様向けのドキュメントを生成します。

#### テストドキュメント生成

```bash
cd doxyfw
make CATEGORY=test
```

このコマンドは `Doxyfile.part.test` を使用し、テスト向けのドキュメントを生成します。

### クリーンアップ (CATEGORY 指定時)

特定の大分類のドキュメントのみを削除できます。

```bash
cd doxyfw
make clean CATEGORY=api
```

このコマンドは `docs/doxygen/api/`、`docs-src/doxybook/api/`、`xml/api/` を削除します。

さらに、親ディレクトリ (`docs/doxygen/`、`docs-src/doxybook/`、`xml/`) が空になった場合は、親ディレクトリも自動的に削除されます。

### Doxyfile.part の命名規則

CATEGORY を使用する場合、メインプロジェクトのルートディレクトリに以下の命名規則でファイルを配置します。

- **デフォルト**: `Doxyfile.part`
- **CATEGORY 指定時**: `Doxyfile.part.{CATEGORY}`

#### ファイル配置例

```text
main-project/
+-- doxyfw/                  # doxyfw サブモジュール
+-- Doxyfile.part            # デフォルト設定
+-- Doxyfile.part.api        # API ドキュメント設定
+-- Doxyfile.part.internal   # 内部仕様ドキュメント設定
+-- Doxyfile.part.test       # テストドキュメント設定
+-- prod/                    # ソースコード
```

### Doxyfile.part の設定例

各大分類に応じて、異なる入力ディレクトリやプロジェクト名を指定できます。

#### Doxyfile.part.api

```text
PROJECT_NAME           = "API Documentation"
INPUT                  = prod/calc/include
```

#### Doxyfile.part.internal

```text
PROJECT_NAME           = "Internal Specification"
INPUT                  = prod/calc/libsrc prod/calc/include
EXTRACT_PRIVATE        = YES
EXTRACT_STATIC         = YES
```

#### Doxyfile.part.test

```text
PROJECT_NAME           = "Test Documentation"
INPUT                  = test/src
```

### 内部動作

#### ドキュメント生成時

CATEGORY が指定された場合、Makefile は以下の処理を自動的に行います。

1. `Doxyfile.part.{CATEGORY}` を基本 Doxyfile と結合
2. 結合した一時 Doxyfile の `OUTPUT_DIRECTORY` と `XML_OUTPUT` を書き換え
   - `OUTPUT_DIRECTORY = ../docs/doxygen/{CATEGORY}`
   - `XML_OUTPUT = ../../xml/{CATEGORY}`
3. 書き換えた一時 Doxyfile で Doxygen を実行
4. 以降の処理も CATEGORY に応じたディレクトリを使用

#### デバッグ用 XML バックアップ

Makefile にはデバッグ用の XML バックアップ機能がコメントアウトされています。この機能を有効にすると、前処理前の XML ファイルを `xml_org` ディレクトリにバックアップできます。

バックアップディレクトリの構造は `xml` と同じ階層構造になります。

- **CATEGORY 未指定時**: `xml_org/`
- **CATEGORY 指定時**: `xml_org/{CATEGORY}/`

Makefile の以下の行のコメントを解除することで有効化できます。

```makefile
#	rm -rf $(XML_ORG_DIR)
#	mkdir -p $(XML_ORG_DIR)
#	cp -rp $(XML_DIR)/* $(XML_ORG_DIR)/
```

および

```makefile
#	rm -rf $(XML_ORG_DIR)
```

#### クリーンアップ時

CATEGORY が指定された場合、clean ターゲットは以下の処理を自動的に行います。

1. CATEGORY に応じたサブディレクトリを削除
   - `docs/doxygen/{CATEGORY}/`
   - `docs-src/doxybook/{CATEGORY}/`
   - `xml/{CATEGORY}/`
2. 親ディレクトリが空になった場合、親ディレクトリも削除
   - `docs/doxygen/`
   - `docs-src/doxybook/`
   - `xml/`

## トラブルシューティング

### CATEGORY 指定時に Doxyfile.part が見つからない

`Doxyfile.part.{CATEGORY}` が存在しない場合、基本 Doxyfile のみで生成されます。意図した設定でドキュメントが生成されない場合は、ファイル名と配置場所を確認してください。

### 複数の大分類を一度に生成したい

複数の大分類を生成する場合は、個別に make コマンドを実行してください。

```bash
cd doxyfw
make CATEGORY=api
make CATEGORY=internal
make CATEGORY=test
```

### 全ての大分類をクリーンアップしたい

各大分類を個別にクリーンアップするか、親ディレクトリから直接削除してください。

```bash
cd doxyfw
make clean CATEGORY=api
make clean CATEGORY=internal
make clean CATEGORY=test
```

または

```bash
rm -rf docs/doxygen/* docs-src/doxybook/* xml/*
```
