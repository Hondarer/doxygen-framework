# ドキュメントの性質に応じた出し分け

利用者の目的に応じて公開 API 仕様書と内部実装仕様書を出し分ける構成、およびヘッダーの宣言とソースの実装説明を統合する仕組みを説明します。

## ドキュメント分離の構成

同一のコードベースから、外部利用者向けのドキュメント (public) と、保守・開発者向けの内部仕様ドキュメント (internal) を分けて生成します。

### 出し分けの全体像

doxyfw は、入力範囲を切り替えるサブカテゴリ機能と、宣言側・定義側の説明を統合する XML 処理スクリプトを備えています。これらにより、ソース コードの二重記述を防ぎながら性質の異なるドキュメントを生成します。

```text
app/calc/
+-- prod/
|   +-- Doxyfile.part.public    -> 公開ヘッダーのみを解析 (include/)
|   +-- Doxyfile.part.internal  -> 実装コードを含めて解析 (include/, libsrc/)
|   +-- include/
|   |   +-- calc.h              -> 外部利用者向けの公開契約 (@brief, @param, @return)
|   +-- libsrc/
|       +-- calc.c              -> 保守者向けの実装メモ (@details)
+-- docs/
    +-- doxybook2_public/       -> 公開 API 仕様書 (Markdown)
    +-- doxybook2_internal/     -> 内部実装仕様書 (Markdown)
```

## サブカテゴリによる生成対象の分離

同一 app 内で複数の Doxygen ドキュメントを管理するために、`CATEGORY` (app 名) と `SUBCATEGORY` (ドキュメント種別) を組み合わせます。

### Doxyfile.part の命名規則

設定ファイルは `app/{CATEGORY}/prod/` 配下に配置します。

| ファイル名 | 用途 | 主な入力範囲 |
| :--- | :--- | :--- |
| `Doxyfile.part` | 既定設定 (単一ドキュメント) | プロジェクト全般 |
| `Doxyfile.part.public` | 公開 API ドキュメント | `include` 配下の公開ヘッダー |
| `Doxyfile.part.internal` | 内部仕様ドキュメント | `include`, `include_internal`, `libsrc` |
| `Doxyfile.part.{SUBCATEGORY}` | 任意の分類 (テスト仕様など) | 対象ディレクトリ |

Table: Doxyfile.part の命名規則と用途

`Doxyfile.part` と `Doxyfile.part.{SUBCATEGORY}` は共存できます。また、`Doxyfile.part` を置かず `Doxyfile.part.public` と `Doxyfile.part.internal` のみで構成することもできます。

### 設定例

公開 API 向けと内部仕様向けでは、入力対象ディレクトリ (`INPUT`) や抽出対象の可視性フラグを切り替えます。

#### 公開 API 向け (Doxyfile.part.public)

外部利用者に必要な公開ヘッダーと導入用 README のみを対象とします。

```text
PROJECT_NAME           = "Calc Public API"
INPUT                  = include \
                         ./README.md
USE_MDFILE_AS_MAINPAGE = ./README.md
```

#### 内部仕様向け (Doxyfile.part.internal)

公開ヘッダーに加え、内部共有ヘッダーや実装ソース コード全体を対象とし、静的関数や非公開メンバーも抽出対象に含めます。

```text
PROJECT_NAME           = "Calc Internal"
INPUT                  = include \
                         include_internal \
                         libsrc \
                         ./README.md
USE_MDFILE_AS_MAINPAGE = ./README.md
EXTRACT_ALL            = YES
EXTRACT_STATIC         = YES
EXTRACT_PRIVATE        = YES
```

### 出力先の規則

各サブカテゴリの生成成果物は、種別ごとに独立したディレクトリへ出力されます。

- **HTML 出力先**: `pages/doxygen/{CATEGORY}_{SUBCATEGORY}/`
- **Markdown 出力先**: `app/{CATEGORY}/docs/doxybook2_{SUBCATEGORY}/`

Markdown の出力先ディレクトリ名を変更したい場合は、`Doxyfile.part.<SUBCATEGORY>` 内にコメント ディレクティブを記述します。

```text
# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME = api
```

上記を指定した場合、Markdown の出力先は `app/{CATEGORY}/docs/api/` に変更されます。HTML の出力先は変更されません。

### make による一括生成

各 app の直下にある makefile (`app/{CATEGORY}/makefile`) の `doxy` ターゲットを実行すると、`prod/Doxyfile.part*` を走査し、定義されているすべてのサブカテゴリに対して doxyfw が順次呼び出されます。

```bash
make -C app/calc doxy
```

個別のサブカテゴリのみを手動で生成する場合は、doxyfw の makefile に対して `CATEGORY` と `SUBCATEGORY` を指定します。

```bash
make -C framework/doxyfw CATEGORY=calc SUBCATEGORY=public
make -C framework/doxyfw CATEGORY=calc SUBCATEGORY=internal
```

## 宣言側と定義側コメントの統合

公開 API ドキュメントと内部仕様ドキュメントを両立させる際、ヘッダーに実装の詳細を書き込みすぎると外部利用者の把握を妨げます。一方、ヘッダーとソースに同じ説明を重複して記述すると、将来の保守で記述の不整合が発生します。

doxyfw では、ヘッダーに利用者向けの説明を、ソースに実装メモを分担して記述し、内部仕様ビルド時にこれらを自動統合します。

### コメントの記述分担

関数に対する Doxygen コメントは、役割に応じて記述場所を分けます。

- **ヘッダーの宣言側**: `@brief`、関数の概要、引数 (`@param`)、戻り値 (`@return`)、事前条件、警告などの公開契約を記載します。
- **ソースの定義側**: `@details` を明示し、アルゴリズムの解説、実装メモ (`@par 実装メモ`)、ファイル内での使用例などを記載します。`@brief` はヘッダーで定義済みのため、定義側では記述しません。

ソースの定義側コメントの直前には、app コーディング規範に従いマーカー `/* Doxygen コメントは、ヘッダーに記載 */` を配置します。

#### ヘッダー側 (include/merge.h) の記述例

```c
/**
 *  @brief          入力値を処理する関数です。
 *
 *  外部利用者が参照する概要と契約を記載します。
 *
 *  @param[in]      value 入力値です。
 *  @return         処理結果を返します。
 */
int merge_func(int value);
```

#### ソース側 (src/merge.c) の記述例

```c
/* Doxygen コメントは、ヘッダーに記載 */

/**
 *  @details
 *  実装上の分岐処理やアルゴリズムの詳細を記載します。
 *
 *  @par            実装メモ
 *  定義側に記載した内部保守者向けの実装メモです。
 */
int merge_func(int value)
{
    return value;
}
```

### サンプル

[Hondarer/c-modernization-kit](https://github.com/Hondarer/c-modernization-kit) の `app/doxygen-sample` に、本機能のサンプル コードが配置されています。

- 宣言側ヘッダー: [app/doxygen-sample/prod/include/merge.h](https://github.com/Hondarer/c-modernization-kit/blob/main/app/doxygen-sample/prod/include/merge.h)
- 定義側ソース: [app/doxygen-sample/prod/src/merge.c](https://github.com/Hondarer/c-modernization-kit/blob/main/app/doxygen-sample/prod/src/merge.c)

`app/doxygen-sample` で `make doxy` を実行すると、生成結果の `app/doxygen-sample/docs/doxybook2_internal/Files/src/merge.c.md` において、ヘッダーに記載した `@brief` や引数・戻り値の説明と、ソースに記載した `@details` の実装メモが単一の関数説明として統合されていることを確認できます。
