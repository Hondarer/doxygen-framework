# makefile 使用方法

このドキュメントでは、doxyfw の makefile の使用方法とオプションについて説明します。

## 基本的な使用方法

### ドキュメント生成

```bash
cd framework/doxyfw
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
cd framework/doxyfw
make clean
```

生成されたドキュメント (`pages/doxygen`、`docs/doxybook2`、`xml`) を削除します。

## CATEGORY オプション

`CATEGORY` オプションを使用すると、ドキュメントを大分類ごとに生成できます。これにより、同一プロジェクト内で複数種類のドキュメントを管理できます。

### 概要

- **オプション名**: `CATEGORY`
- **デフォルト値**: 空 (大分類なし)
- **用途**: API ドキュメント、内部仕様書、テストドキュメントなど、異なる種類のドキュメントを分類して生成

### 動作仕様

#### CATEGORY 未指定時 (デフォルト)

```bash
cd framework/doxyfw
make
```

- **使用する設定ファイル**: `../../Doxyfile.part`
- **HTML 出力先**: `../../pages/doxygen/`
- **Markdown 出力先**: `../../docs/doxybook2/`
- **XML 中間ファイル**: `../../xml/` (処理後削除)

#### CATEGORY 指定時

```bash
cd framework/doxyfw
make CATEGORY=api
```

- **使用する設定ファイル**: `../../app/api/Doxyfile.part.api`
- **HTML 出力先**: `../../pages/doxygen/api/`
- **Markdown 出力先**: `../../docs/doxybook2/api/`
- **XML 中間ファイル**: `../../xml/api/` (処理後削除)

### 使用例

#### API ドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=api
```

このコマンドは `app/api/Doxyfile.part.api` を使用し、API 向けのドキュメントを生成します。

#### 内部仕様ドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=internal
```

このコマンドは `app/internal/Doxyfile.part.internal` を使用し、内部仕様向けのドキュメントを生成します。

#### テストドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=test
```

このコマンドは `app/test/Doxyfile.part.test` を使用し、テスト向けのドキュメントを生成します。

### クリーンアップ (CATEGORY 指定時)

特定の大分類のドキュメントのみを削除できます。

```bash
cd framework/doxyfw
make clean CATEGORY=api
```

このコマンドは `pages/doxygen/api/`、`docs/doxybook2/api/`、`xml/api/` を削除します。

さらに、親ディレクトリ (`pages/doxygen/`、`docs/doxybook2/`、`xml/`) が空になった場合は、親ディレクトリも自動的に削除されます。

### Doxyfile.part の命名規則

CATEGORY を使用する場合、設定ファイルは `app/<category>/` 配下に配置します。CATEGORY を使わない既定実行では、ワークスペース直下の `Doxyfile.part` を使用できます。

- **デフォルト**: `Doxyfile.part`
- **CATEGORY 指定時**: `app/{CATEGORY}/Doxyfile.part.{CATEGORY}`

#### ファイル配置例

```text
main-project/
+-- framework/
|   +-- doxyfw/              # doxyfw サブモジュール
+-- Doxyfile.part            # デフォルト設定
+-- prod/                    # CATEGORY 未指定時の既定ソースコード
+-- app/
|   +-- api/
|   |   +-- Doxyfile.part.api
|   |   +-- prod/
|   +-- internal/
|   |   +-- Doxyfile.part.internal
|   |   +-- prod/
|   +-- test/
|       +-- Doxyfile.part.test
|       +-- prod/
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

CATEGORY が指定された場合、makefile は以下の処理を自動的に行います。

1. `app/{CATEGORY}/Doxyfile.part.{CATEGORY}` を基本 Doxyfile と結合する
2. `app/{CATEGORY}/` を Doxygen の実行基準ディレクトリとして使用する
3. 結合した一時 Doxyfile の `OUTPUT_DIRECTORY` と `XML_OUTPUT` を書き換える
   - `OUTPUT_DIRECTORY = ../../pages/doxygen/{CATEGORY}`
   - `XML_OUTPUT = ../../../xml/{CATEGORY}`
4. `INPUT_FILTER` を `framework/doxyfw/input-filter.py` の絶対パスへ置き換える
5. 書き換えた一時 Doxyfile で Doxygen を実行する
6. 後段の Markdown コピー処理も同じ基準ディレクトリを使用する

#### デバッグ用 XML バックアップ

makefile にはデバッグ用の XML バックアップ機能がコメントアウトされています。この機能を有効にすると、前処理前の XML ファイルを `xml_org` ディレクトリにバックアップできます。

バックアップディレクトリの構造は `xml` と同じ階層構造になります。

- **CATEGORY 未指定時**: `xml_org/`
- **CATEGORY 指定時**: `xml_org/{CATEGORY}/`

makefile の以下の行のコメントを解除することで有効化できます。

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
   - `pages/doxygen/{CATEGORY}/`
   - `docs/doxybook2/{CATEGORY}/`
   - `xml/{CATEGORY}/`
2. 親ディレクトリが空になった場合、親ディレクトリも削除
   - `pages/doxygen/`
   - `docs/doxybook2/`
   - `xml/`

## トラブルシューティング

### CATEGORY 指定時に Doxyfile.part が見つからない

`app/{CATEGORY}/Doxyfile.part.{CATEGORY}` が存在しない場合、基本 Doxyfile のみで生成されます。意図した設定でドキュメントが生成されない場合は、ファイル名と配置場所を確認してください。

### 複数の大分類を一度に生成したい

複数の大分類を生成する場合は、個別に make コマンドを実行してください。

```bash
cd framework/doxyfw
make CATEGORY=api
make CATEGORY=internal
make CATEGORY=test
```

### 全ての大分類をクリーンアップしたい

各大分類を個別にクリーンアップするか、親ディレクトリから直接削除してください。

```bash
cd framework/doxyfw
make clean CATEGORY=api
make clean CATEGORY=internal
make clean CATEGORY=test
```

または

```bash
rm -rf pages/doxygen/* docs/doxybook2/* xml/*
```
