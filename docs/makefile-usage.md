# makefile 使用方法

このドキュメントでは、doxyfw の makefile の使用方法とオプションについて説明します。

## 基本的な使用方法

### ドキュメント生成

```bash
cd framework/doxyfw
make
```

別のワークスペースから呼び出す場合は、呼び出し元で `DOXYFW_HOME` に doxyfw の配置先を指定します。
doxyfw の makefile は `WORKSPACE_DIR` を workspace 側の基準ディレクトリとして使います。通常は呼び出し元 makefile が設定するため、手動指定は不要です。

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
`CATEGORY` 指定時に生成された Markdown は、既定では `app/<CATEGORY>/docs/doxybook2` から削除されます。
`# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME` を指定している場合は、指定したディレクトリが削除対象になります。

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

- **使用する設定ファイル**: `../../app/api/prod/Doxyfile.part`
- **HTML 出力先**: `../../pages/doxygen/api/`
- **Markdown 出力先**: `../../app/api/docs/doxybook2/`
- **XML 中間ファイル**: `../../xml/api/` (処理後削除)

### 使用例

#### API ドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=api
```

このコマンドは `app/api/Doxyfile.part` を使用し、API 向けのドキュメントを生成します。

#### 内部仕様ドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=internal
```

このコマンドは `app/internal/Doxyfile.part` を使用し、内部仕様向けのドキュメントを生成します。

#### テストドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=test
```

このコマンドは `app/test/Doxyfile.part` を使用し、テスト向けのドキュメントを生成します。

### クリーンアップ (CATEGORY 指定時)

特定の大分類のドキュメントのみを削除できます。

```bash
cd framework/doxyfw
make clean CATEGORY=api
```

このコマンドは `pages/doxygen/api/`、`app/api/docs/doxybook2/`、`xml/api/` を削除します。

さらに、親ディレクトリ (`pages/doxygen/`、`app/api/docs/`、`xml/`) が空になった場合は、親ディレクトリも自動的に削除されます。

### Doxyfile.part の命名規則

CATEGORY を使用する場合、設定ファイルは `app/<category>/prod/` 配下に配置します。CATEGORY を使わない既定実行では、ワークスペース直下の `Doxyfile.part` を使用できます。

- **デフォルト**: `Doxyfile.part`
- **CATEGORY 指定時**: `app/{CATEGORY}/prod/Doxyfile.part`

#### ファイル配置例

```text
main-project/
+-- framework/
|   +-- doxyfw/              # doxyfw サブモジュール
+-- Doxyfile.part            # デフォルト設定
+-- prod/                    # CATEGORY 未指定時の既定ソースコード
+-- app/
|   +-- api/
|   |   +-- prod/
|   |       +-- Doxyfile.part
|   +-- internal/
|   |   +-- prod/
|   |       +-- Doxyfile.part
|   +-- test/
|       +-- prod/
|           +-- Doxyfile.part
```

### Doxyfile.part の設定例

各大分類に応じて、異なる入力ディレクトリやプロジェクト名を指定できます。

#### app/api/prod/Doxyfile.part

```text
PROJECT_NAME           = "API Documentation"
INPUT                  = app/calc/prod/include
```

#### app/internal/prod/Doxyfile.part

```text
PROJECT_NAME           = "Internal Specification"
INPUT                  = app/calc/prod/libsrc app/calc/prod/include
EXTRACT_PRIVATE        = YES
EXTRACT_STATIC         = YES
```

#### app/test/prod/Doxyfile.part

```text
PROJECT_NAME           = "Test Documentation"
INPUT                  = app/calc/test/src
```

### Doxybook2 出力ディレクトリ名の変更

`CATEGORY` 指定時は、`app/<CATEGORY>/prod/Doxyfile.part` にコメントディレクティブを追加すると Doxybook2 の Markdown 出力ディレクトリ名だけを変更できます。

```text
# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME = api
```

この例では Markdown 出力先が `app/<CATEGORY>/docs/api/` になります。Doxygen HTML 出力先は変わらず `pages/doxygen/<CATEGORY>/` です。

Doxygen に未知タグ警告を出させないため、この設定は通常の Doxygen タグではなくコメントとして記述します。

値を空にした場合は未指定として扱われ、既定の `doxybook2` を使用します。
値を指定する場合はディレクトリ名 1 要素だけです。絶対パス、`.`、`..`、`/`、`\` を含む値はエラーになります。

カスタム名を使用する app では、`docs/README.md` 内の Doxybook2 へのリンクと `\toc exclude` の対象も同じディレクトリ名に更新してください。

### 内部動作

#### ドキュメント生成時

CATEGORY が指定された場合、makefile は以下の処理を自動的に行います。

1. `app/{CATEGORY}/prod/Doxyfile.part` を基本 Doxyfile と結合する
2. `app/{CATEGORY}/` を Doxygen の実行基準ディレクトリとして使用する
3. 結合した一時 Doxyfile の `OUTPUT_DIRECTORY` と `XML_OUTPUT` を書き換える
   - `OUTPUT_DIRECTORY = ../../pages/doxygen/{CATEGORY}`
   - `XML_OUTPUT = ../../../xml/{CATEGORY}`
4. `INPUT_FILTER` を `framework/doxyfw/bin/input-filter.py` の絶対パスへ置き換える
5. 書き換えた一時 Doxyfile で Doxygen を実行する
6. Doxybook2 の出力先として、既定では `app/{CATEGORY}/docs/doxybook2/` を使用する
7. `# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME` がある場合は、Doxybook2 の出力先だけを `app/{CATEGORY}/docs/<name>/` に変更する

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
   - Doxybook2 Markdown 出力ディレクトリ。既定では `app/{CATEGORY}/docs/doxybook2/`
   - `xml/{CATEGORY}/`
   - `# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME` がある場合の Markdown 出力ディレクトリは `app/{CATEGORY}/docs/<name>/`
2. 親ディレクトリが空になった場合、親ディレクトリも削除
   - `pages/doxygen/`
   - `app/{CATEGORY}/docs/`
   - `xml/`

## トラブルシューティング

### CATEGORY 指定時に Doxyfile.part が見つからない

`app/{CATEGORY}/prod/Doxyfile.part` が存在しない場合、基本 Doxyfile のみで生成されます。意図した設定でドキュメントが生成されない場合は、ファイル名と配置場所を確認してください。

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
rm -rf pages/doxygen/* docs/doxybook2/* app/*/docs/doxybook2/* xml/*
```
