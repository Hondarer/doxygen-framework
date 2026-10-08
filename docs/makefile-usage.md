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

このコマンドは次の処理を順次実行します。

1. 既存のドキュメントをクリーンアップ
2. Doxygen で C ソース コードを解析し、HTML と XML を生成
3. XML ファイルを前処理
4. Doxybook2 で Markdown に変換
5. Markdown ファイルを後処理

### クリーンアップ

```bash
cd framework/doxyfw
make clean
```

生成されたドキュメント (`pages/doxygen`、`docs/doxybook2`) を削除します。  
`CATEGORY` 指定時に生成された Markdown は、既定では `app/<CATEGORY>/docs/doxybook2` から削除されます。  
`# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME` を指定している場合は、指定したディレクトリが削除対象になります。

## CATEGORY と SUBCATEGORY オプション

`CATEGORY` および `SUBCATEGORY` オプションを使用すると、対象 app (大分類) やドキュメント種別 (小分類) を指定してドキュメントを生成できます。これにより、同一プロジェクト内で公開 API と内部仕様などの複数種類のドキュメントを管理できます。

公開 API や内部仕様の出し分け設計、および `Doxyfile.part` の命名規則や設定例の詳細は、[ドキュメントの性質に応じた出し分け](document-separation.md) を参照してください。

### 概要

- **オプション名**: `CATEGORY`, `SUBCATEGORY`
- **既定値**: 空 (指定なし)
- **用途**:
    - `CATEGORY`: 対象 app (`app/<CATEGORY>`) を指定します。
    - `SUBCATEGORY`: 公開 API (`public`) や内部仕様 (`internal`) など、ドキュメントの種別を指定します。

### 動作仕様

#### CATEGORY 未指定時 (既定)

```bash
cd framework/doxyfw
make
```

- **使用する設定ファイル**: `../../Doxyfile.part`
- **HTML 出力先**: `../../pages/doxygen/`
- **Markdown 出力先**: `../../docs/doxybook2/`
- **XML 中間ファイル**: `/tmp/doxyfw-tmp-{UID}/root/run.XXXXXX/xml/` (処理後削除)

#### CATEGORY 指定時 (SUBCATEGORY なし)

```bash
cd framework/doxyfw
make CATEGORY=api
```

- **使用する設定ファイル**: `../../app/api/prod/Doxyfile.part`
- **HTML 出力先**: `../../pages/doxygen/api/`
- **Markdown 出力先**: `../../app/api/docs/doxybook2/`
- **XML 中間ファイル**: `/tmp/doxyfw-tmp-{UID}/api/run.XXXXXX/xml/` (処理後削除)

#### CATEGORY および SUBCATEGORY 指定時

```bash
cd framework/doxyfw
make CATEGORY=calc SUBCATEGORY=public
```

- **使用する設定ファイル**: `../../app/calc/prod/Doxyfile.part.public`
- **HTML 出力先**: `../../pages/doxygen/calc_public/`
- **Markdown 出力先**: `../../app/calc/docs/doxybook2_public/`
- **XML 中間ファイル**: `/tmp/doxyfw-tmp-{UID}/calc_public/run.XXXXXX/xml/` (処理後削除)

### 使用例

#### 大分類のみのドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=api
```

#### サブカテゴリ (公開 API / 内部仕様) のドキュメント生成

```bash
cd framework/doxyfw
make CATEGORY=calc SUBCATEGORY=public
make CATEGORY=calc SUBCATEGORY=internal
```

### クリーンアップ (CATEGORY / SUBCATEGORY 指定時)

指定した分類のドキュメントのみを削除できます。

```bash
cd framework/doxyfw
make clean CATEGORY=api
make clean CATEGORY=calc SUBCATEGORY=public
```

このコマンドは、対象の HTML 出力ディレクトリ、Markdown 出力ディレクトリ、および警告ファイルを削除します。親ディレクトリ (`pages/doxygen/`、`app/<CATEGORY>/docs/`) が空になった場合は、親ディレクトリも自動的に削除されます。

### 設定ファイル (Doxyfile.part) の配置

CATEGORY や SUBCATEGORY を指定した実行では、`app/{CATEGORY}/prod/` 配下の `Doxyfile.part` または `Doxyfile.part.{SUBCATEGORY}` を読み込みます。

- **既定**: `Doxyfile.part`
- **CATEGORY 指定時**: `app/{CATEGORY}/prod/Doxyfile.part`
- **SUBCATEGORY 指定時**: `app/{CATEGORY}/prod/Doxyfile.part.{SUBCATEGORY}`

公開 API 向け (`.public`) や内部仕様向け (`.internal`) などの性質に応じた設定例や、コメント統合の設計については、[ドキュメントの性質に応じた出し分け](document-separation.md) を参照してください。

### Doxybook2 出力ディレクトリ名の変更

`CATEGORY` 指定時は、`app/<CATEGORY>/prod/Doxyfile.part` にコメント ディレクティブを追加すると Doxybook2 の Markdown 出力ディレクトリ名だけを変更できます。

```text
# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME = api
```

この例では Markdown 出力先が `app/<CATEGORY>/docs/api/` になります。Doxygen HTML 出力先は変わらず `pages/doxygen/<CATEGORY>/` です。

`Doxyfile.part.<SUBCATEGORY>` でも同じディレクティブを使用できます。既定値は `doxybook2_<SUBCATEGORY>` です。

Doxygen に未知タグの警告を出力させないため、この設定は通常の Doxygen タグではなくコメントとして記述します。

値を空にした場合は未指定として扱われ、既定値を使用します。  
値を指定する場合はディレクトリ名 1 要素だけです。絶対パス、`.`、`..`、`/`、`\` を含む値はエラーになります。

カスタム名を使用する app では、`docs/README.md` 内の Doxybook2 へのリンクと `\toc exclude` の対象も同じディレクトリ名に更新してください。

### 内部動作

#### ドキュメント生成時

CATEGORY が指定された場合、makefile は次の処理を自動的に行います。

1. `app/{CATEGORY}/prod/Doxyfile.part` を基本 Doxyfile と結合します。
    - SUBCATEGORY 指定時は `app/{CATEGORY}/prod/Doxyfile.part.{SUBCATEGORY}` を使用します。
2. `app/{CATEGORY}/` を Doxygen の実行基準ディレクトリとして使用します。
3. 結合した一時 Doxyfile の `OUTPUT_DIRECTORY`、`XML_OUTPUT`、`GENERATE_TAGFILE` を実行単位の一時ディレクトリへ書き換えます。
    - SUBCATEGORY なし: `/tmp/doxyfw-tmp-{UID}/{CATEGORY}/run.XXXXXX/` 配下を使用します。
    - SUBCATEGORY あり: `/tmp/doxyfw-tmp-{UID}/{CATEGORY}_{SUBCATEGORY}/run.XXXXXX/` 配下を使用します。
4. `INPUT_FILTER` を `framework/doxyfw/bin_internal/input-filter.py` の絶対パスへ置き換えます。
5. 書き換えた一時 Doxyfile で Doxygen を実行します。
6. Doxybook2 の出力先として、既定では `app/{CATEGORY}/docs/doxybook2/` を使用します。
    - SUBCATEGORY 指定時は既定値が `app/{CATEGORY}/docs/doxybook2_{SUBCATEGORY}/` になります。
7. `# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME` がある場合は、Doxybook2 の出力先だけを `app/{CATEGORY}/docs/<name>/` に変更します。

`app/{CATEGORY}/makefile` の doxy ターゲットは `prod/Doxyfile.part*` を列挙し、`Doxyfile.part`、`Doxyfile.part.<SUBCATEGORY>` の各ファイルに対して doxyfw を 1 回ずつ呼び出します。警告ファイルは各 SUBCATEGORY ごとに独立します (`doxy.warn`、`doxy_<SUBCATEGORY>.warn`)。スキップ判定 (`make_doxy.stamp`) は `prod/` 配下の Doxygen 入力 (Doxyfile.part* と `INPUT` / `IMAGE_PATH` で参照される `prod/` 配下のソース、画像) のみを対象とし、SUBCATEGORY が分かれていても app 単位で 1 つの stamp に集約されます。

#### XML 中間ファイル

XML 中間ファイルは `/tmp/doxyfw-tmp-{UID}/{CATEGORY_ID}/run.XXXXXX/xml/` に作成します。  
`CATEGORY` 未指定時の `{CATEGORY_ID}` は `root` です。  
`{UID}` は実行ユーザーの `id -u` の値です。Linux の `/tmp` は全ユーザーで共有されるため、別ユーザー (sudo 実行や root のコンテナーなど) が作成したディレクトリへの書き込みで失敗しないよう、ユーザーごとに分けます。  
Doxygen 実行ごとに `mktemp` で実行単位のディレクトリを作成するため、異なる app の `make doxy` が同時に実行されても XML 中間ファイルは共有されません。  
終了時に削除するのは実行単位の `run.XXXXXX/` とロックだけです。親ディレクトリ (`/tmp/doxyfw-tmp-{UID}/`、`/tmp/doxyfw-tmp-{UID}/{CATEGORY_ID}/`、`/tmp/doxyfw-locks-{UID}/`) は、並列実行中の別の実行と競合しないよう空でも残します。

前処理前の XML を保存したい場合は、該当 run ディレクトリを削除する前に個別に退避してください。

#### クリーンアップ時

CATEGORY が指定された場合、clean ターゲットは次の処理を自動的に行います。

1. 警告ファイルを削除
    - `app/{CATEGORY}/doxy.warn` (SUBCATEGORY ありの場合は `app/{CATEGORY}/doxy_{SUBCATEGORY}.warn`)
2. CATEGORY に応じたサブディレクトリを削除
    - `pages/doxygen/{CATEGORY}/` (SUBCATEGORY ありの場合は `pages/doxygen/{CATEGORY}_{SUBCATEGORY}/`)
    - Doxybook2 Markdown 出力ディレクトリ。既定では `app/{CATEGORY}/docs/doxybook2/`
        - SUBCATEGORY ありの場合は既定で `app/{CATEGORY}/docs/doxybook2_{SUBCATEGORY}/`
    - `# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME` がある場合の Markdown 出力ディレクトリは `app/{CATEGORY}/docs/<name>/`
3. 親ディレクトリが空になった場合、親ディレクトリも削除
    - `pages/doxygen/`
    - `app/{CATEGORY}/docs/`

## トラブルシューティング

### CATEGORY 指定時に Doxyfile.part が見つからない

`app/{CATEGORY}/prod/Doxyfile.part` が存在しない場合、生成は行わずエラー終了します。

`Doxyfile.part.{SUBCATEGORY}` だけが存在する大分類では、`SUBCATEGORY` の指定が必須です。指定がないときは、利用できる小分類の一覧とコマンド例をエラー メッセージに表示します。

```text
ERROR: /path/to/app/example/prod/Doxyfile.part not found.
CATEGORY=cplat is configured per subcategory. Specify one of: internal public
  make -C "/path/to/framework/doxyfw" CATEGORY=cplat SUBCATEGORY=internal
  make -C "/path/to/framework/doxyfw" CATEGORY=cplat SUBCATEGORY=public
To run every subcategory at once, use: make -C "/path/to/app/example" doxy
```

`Doxyfile.part` も `Doxyfile.part.*` も存在しない大分類では、Doxygen が設定されていない旨を表示して終了します。

基本 Doxyfile のみで生成しない理由は、その `INPUT` が `./README.md ./src ./include` であり、`libsrc` を含まないためです。この入力で生成すると、`libsrc` 配下を指す `\ref` の解決に失敗し、`include` で宣言した関数の定義位置を `src` 側の呼び出し行と誤認した依存関係レポートが出力されます。いずれも生成自体は成功するため、警告を確認しない限り不完全なドキュメントを見落としやすくなります。

### SUBCATEGORY の制約違反でエラーになる

`SUBCATEGORY` にディレクトリ区切り文字 (`/`、`\`) または空白文字が含まれているか、`.`、`..` が指定されていると make エラーになります。それ以外の文字 (日本語含む) は使用できます。

また、`SUBCATEGORY` は `CATEGORY` と同時に指定する必要があります。`CATEGORY` が空の場合に `SUBCATEGORY` を指定するとエラーになります。

### 複数の大分類を一度に生成したい

複数の大分類を生成する場合は、個別に make コマンドを実行してください。

```bash
cd framework/doxyfw
make CATEGORY=api
make CATEGORY=internal
make CATEGORY=test
```

### すべての大分類をクリーンアップしたい

各大分類を個別にクリーンアップするか、親ディレクトリから直接削除してください。

```bash
cd framework/doxyfw
make clean CATEGORY=api
make clean CATEGORY=internal
make clean CATEGORY=test
```

または

```bash
rm -rf pages/doxygen/* docs/doxybook2/* app/*/docs/doxybook2/*
```
