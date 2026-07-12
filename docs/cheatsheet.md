# CheatSheet

[Doxygen チート シート](https://qiita.com/yuta-yoshinaga/items/84887a89f6a21a7dcfd5) を参考に C 言語用にアレンジしたチート シートです。

Doxygen の生成処理は制限が多く、記載した内容が正しくドキュメント化されない場合が多いため、本チート シートをコピー＆ペーストして品質の良い Doxygen コメントを付与してください。

以下に無い記載を行う場合は、期待通りの出力が行われるかどうか、生成結果を確認するようにしてください。

## @brief の注意

この repo では Doxybook2 が `@brief` を Markdown の YAML front matter にある `summary` としても出力します。  
`Linux: fd` のように半角コロンの直後へ空白を続ける表現は、生成後の YAML で別のマッピングとして解釈され、Pandoc の変換時に警告が出る場合があります。

```c
/**
 *  @brief  ファイル ハンドルの抽象化構造体 (Linux の fd、Windows の HANDLE を保持)。
 */
```

`@brief` は YAML の構文と衝突しにくい短い文にし、詳細は空行を 1 行あけてタグなし本文へ分けてください。  
タグなし本文は Doxygen により details として扱われます。  
`@details` は、`@par` など別タグの本文に続けて details を再開したい場合のように、明示しないと所属が曖昧になる箇所で使います。

`@file` の `@brief` は、ファイルの種別を述べるラベルではなく、そのファイルが提供する機能を述べるですます体の一文にします。  
詳細は「記載場所別の例」の「@file の説明文の書き方」を参照してください。

## clang-format 適用後の字下げ確認

Doxygen コメントに `clang-format` を適用した後、以下を確認してください。

### コメント開始行と後続行の字下げレベルが一致しているか

`/**` 行のインデント位置と、その直後の `* ...` 行および `*/` 行のインデント位置が揃っていることを確認します。

**不正な例:**

```c
    /**                 // indent=4
 *  @brief  説明       // indent=1（ズレている）
 *  @param[in]  arg    // indent=1（ズレている）
    */                 // indent=4
```

**正しい例:**

```c
    /**                 // indent=4
     *  @brief  説明    // indent=5（/** と同じ深さ + 1）
     *  @param[in]  arg // indent=5
     */                // indent=5
```

### 確認方法

1. エディターで「インデント表示」機能 (例: VS Code の「render whitespace」) を有効にする
2. コメント開始行のインデント位置を基準に、後続行がすべて揃っているか視認する
3. 必要に応じて手動で先頭スペースを調整する

### なぜ確認が必要か

`clang-format` はコメント開始行 `/**` のインデント位置を自動調整しますが、後続行は調整しません。  
この結果として生じた不一致は、Doxygen パーサーやドキュメント生成時に問題を引き起こす可能性があります。

詳細は SKILL.md の「clang-format 適用後の字下げ一貫性」を参照してください。

## 関数のコメントをどこで行うべきか

ライブラリとヘッダーを配布した際に VS Code が解釈できるようにするため、ヘッダー (宣言) 側の Doxygen コメントは必ず記載してください。

ソース (実装) 側は、同じ Doxygen コメントを記載しておくこともできますが、情報が重複し保守性に懸念があることから、以下のようにします。

```c
/* Doxygen コメントは、ヘッダーに記載 */

int calcHandler(int kind, int a, int b)
```

マーカー コメントと関数定義の間には空行を 1 行入れてください。VS Code の C/C++ 拡張機能 (IntelliSense) がマーカー コメントを関数のドキュメントとしてホバー表示に拾うのを抑止するためです。

上の例のように、定義側にはエクスポート / 呼び出し規約マクロ (`CALC_EXPORT` / `CALC_API` 等) を付けません。宣言と定義での修飾子・マクロの配置は、コーディング規範の「宣言と定義の関係」に従います。

### 外部向けの説明と実装上の補足を分けて記載する

実装側にも記録したい補足がある場合は、外部利用者向けの説明をヘッダー (宣言) に、実装上の補足をソース (定義) に分けて記載できます。  
ソース側はマーカー コメントの代わりに `@details` で実装上の補足のみを記載し、`@brief` は宣言側に記載済みのため繰り返しません。

ヘッダー (宣言):

```c
/**
 *  @brief          指定された値を処理します。
 *
 *  外部利用者が参照して有益な説明をここに記載します。
 *
 *  @param[in]      value 入力値を表します。
 *  @return         処理結果を返します。
 */
int sample(int value);
```

ソース (定義):

```c
/* 外部利用者が参照する Doxygen コメントは、ヘッダーに記載 */
/**
 *  @details
 *  このファイルの実装上の補足をここに記載します。\n
 *  @brief は宣言側に記載済みのため、記載しません。
 *
 *  @par            実装メモ
 *  実装上の補足をここに記載します。
 */
int sample(int value)
{
    return value;
}
```

ソースを入力に含むビルド (internal) では、doxyfw が宣言側と定義側の説明を統合し、ヘッダーとソースの両方の Files ページへそろって出力します。  
詳細は [commands.md の「宣言 (ヘッダー) と定義 (ソース) に説明を分けて書く」](commands.md) を参照してください。

## 記載場所別の例

ファイル コメント (`@file`) はブロックの前後にセパレータを置きます。  
`@file` を含まない Doxygen コメントでは、関数、型、マクロ、補足説明のいずれもセパレータを置きません。

### @file の説明文の書き方

`@file` の `@brief` は、そのファイルが提供する機能・役割を述べる簡潔な一文にします。  
[Microsoft Learn の .NET API リファレンス](https://learn.microsoft.com/ja-jp/dotnet/api/system.io) にある名前空間サマリーや型サマリーに倣い、ですます体で「何を提供するか」を述べます。  
「～の実装ファイル。」「～のヘッダー ファイル。」「～の呼び出しコマンド。」のような、ファイルの種別だけを述べる体言止めのラベルは避けます。ファイルの種別はパスや拡張子から判断できるため、`@brief` には機能を記載します。

`@brief` に続くタグなし本文は、Microsoft の「注釈」に相当する補足としてですます体で記載します。

文末は、Microsoft の型サマリーで使われる次の表現を参考にします。

| 用途 | 文末例 |
|---|---|
| 機能や型を提供する | ～を提供します。 |
| 概念や値を表す | ～を表します。 |
| インターフェイスを実装する | ～を実装します。 |
| 定数や種別を定義する | ～を定義します。 |
| メソッドや API を公開する | ～を公開します。 |
| 機能を補助する | ～をサポートします。 |
| 複数の型や関数をまとめたファイル | ～する型 (関数) が含まれています。 |

例外型のサマリーのように、Microsoft 自身が体言止め (「～場合にスローされる例外。」) で記載している種類の説明は、体言止めのままで構いません。

### ソース・ヘッダー ファイル

`History` というコマンド (タグ) は存在しないので、ユーザー定義の見出しで表現しています。

```c
/**
 *******************************************************************************
 *  @file           filename.c
 *  @brief          ファイルの概要を表します。
 *
 *  コマンド (タグ) のないコメントは、details として扱われます。
 *  通常の詳細説明は @brief の後に空行を 1 行あけて記載します。
 *
 *  もし、ブロック内での改行を行いたい場合は、\n
 *  を使って改行します。`<br />` での改行は VS Code のツールヒントで
 *  改行と解釈されないことから非推奨です。
 *
 *  @author         初版作成者を表します。
 *  @date           yyyy/mm/dd (初版作成年月日を表します。)
 *  @version        現在のバージョンを表します。
 *  @par            History
 *                  - yyyy/mm/dd [修正ID](https://example.com/id/1234) 修正の概要
 *                      - 子リスト 1
 *                      - 子リスト 2
 *                  - yyyy/mm/dd [修正ID](https://example.com/id/5678) 修正の概要
 *                      - 子リスト 1
 *                        子リスト 1 の続き
 *  @copyright Copyright (C) CompanyName, Ltd. 2023-2025. All rights reserved.
 *
 *******************************************************************************
 */
```

### ヘッダー ファイル (@section を使用した構造化)

複数のマクロや定義をグループ化して説明する場合は、`@section` を使用します。

```c
/**
 *******************************************************************************
 *  @file           compiler.h
 *  @brief          コンパイラの種類とバージョンを検出し、統一的なマクロを提供します。
 *  @author         c-modernization-kit sample team
 *  @date           2026/02/06
 *
 *  検出したコンパイラに応じて、種類の識別マクロとインライン制御マクロを定義します。
 *
 *  @section        compiler_detection コンパイラ検出マクロ
 *
 *  検出されたコンパイラに応じて、以下のマクロを定義します。
 *
 *  | コンパイラ | 識別マクロ       | COMPILER_NAME |
 *  | ---------- | ---------------- | ------------- |
 *  | MSVC       | COMPILER_MSVC    | "MSVC"        |
 *  | GCC        | COMPILER_GCC     | "GCC"         |
 *  | Clang      | COMPILER_CLANG   | "Clang"       |
 *
 *  @note           Clang は __GNUC__ も定義するため、Clang を GCC より先に判定しています。
 *
 *  @section        inline_control インライン制御マクロ
 *
 *  コンパイラ固有のインライン制御属性を抽象化します。
 *
 *  使用例:
 *
    @code{.c}
    #include "compiler.h"

    FORCE_INLINE int fast_add(int a, int b)
    {
        return a + b;
    }
    @endcode
 *
 *  @copyright      Copyright (C) CompanyName, Ltd. 2025. All rights reserved.
 *
 *******************************************************************************
 */
```

### 関数 (メソッド)

```c
/**
 *  @brief          関数の説明を表します。
 *  @param[in]      引数 (参照専用)
 *  @param[out]     引数 (ポインター引数等)
 *  @param[in,out]  引数 (ポインター引数等)
 *  @return         関数戻り値の説明
 *  @warning        重大なエラーや危険の回避のための警告を表します。
 *  @attention      必須の制約条件・使用条件などの注意を表します。
 *  @important      見落とすと誤用や重大な判断ミスにつながる重要情報を表します。
 *  @note           技術的な背景や実装の注釈を表します。
 *  @remark         使用上のヒントや最適化のアドバイスなどの補足情報を表します。
 *  @deprecated     非推奨であることを記載します。
 *  @since          コードや API がいつから利用可能になったかを記載します。
 * 
 *  PlantUML の図を挿入することができます。<br>
 *  VS Code の PlantUML プラグインを使用するために、
 *  `@startuml` ~ `@enduml` の範囲は行頭の * を記載しません。
 * 
    @startuml
        caption 図のテスト
        circle a
        circle b
        rectangle "a/b" as devide
        circle return
        a -> devide : 被除数
        b -> devide : 除数
        devide -> return
    @enduml
 * 
 */
```

### 構造体および class のメンバー

```c
    int     intval;         /**< 変数の説明。 */
```

```c
 /**
 *  @brief          サンプルの列挙体を定義します。
 */
enum SampleEnum
{
    one,  /**< 1 つめの要素。 */
    two,  /**< 2 つめの要素。 */
    three /**< 3 つめの要素。 */
};
```

```c
/**
 *  @brief          ユーザー情報を保持する構造体を定義します。
 */
typedef struct
{
    int id;               /**< ユーザー ID。 */
    const char *name;     /**< ユーザー名。 */
    SampleEnum enumValue; /**< 列挙値。 */
} UserInfo;
```

## シナリオ別の記載例

### リスト

```c
/**
 *  @todo
 *                  - 親リスト 1
 *                      - 子リスト 1
 *                      - 子リスト 2
 *                  - 親リスト 2
 *                      - 子リスト 1
 *                      - 子リスト 2
 */
```

```c
/**
 *  @todo           Todo リストの説明
 *                  - 親リスト 1
 *                      - 子リスト 1
 *                      - 子リスト 2
 *                  - 親リスト 2
 *                      - 子リスト 1
 *                      - 子リスト 2
 */
```

### 表

字下げが多いとプレーン テキストのコード ブロックとして解釈されるため、表を書く際の列セパレータ `|` の字下げは行わないようにします。

Markdown pipe tables 形式の表はサポートされません。サポートされる書式は [Markdown Extensions - Tables](https://www.doxygen.nl/manual/markdown.html#md_tables) を参照してください。  
複雑な表は、[HTML 形式で記載する必要がある](https://www.doxygen.nl/manual/tables.html) ため、非推奨です。

通常の Markdown と異なり、列幅の指定などの書式情報は Doxygen の変換時に失われることがあります。

**不具合:**

表の見出しについて見出し定義の `-` の個数バイトに切り捨てられる不具合があるため、見出しが漢字 (マルチバイト文字) の場合は `-` の個数を調整し正しく表示されるかどうかを確認する必要があります (Doxygen 1.8.14 で現象を確認)。

```c
/**
 *  表を書く際、列セパレータ `|` の字下げは行わないようにします。
 *  (字下げが多いとプレーン テキストのコード ブロックとして解釈されるため)
 * 
 *  | No. | 名称                | 備考                        |
 *  | --: | ------------------- | --------------------------- |
 *  |   1 | 名称1               |                             |
 *  |   2 | 名称2               |                             |
 * 
 *  Table: 表のキャプション
 */
```

```c
/**
 *  | No. | ヘッダ文字列       |
 *  | --: | ------------------ |
 *  |   1 | 内容1<br />内容2   |
 *  |   2 | テスト             |
 *  |   3 | Test               |
 *
 *  Table: セル内での改行を含む表
 */
```

### コードの埋め込み

#### @code ~ @endcode を使用した例

`@code` と `@endcode` の行は、コード本体の各行と同様に、行頭の `*` を付けません。
`@code`、コード本体、`@endcode` は同じ 4 の倍数カラムから開始します。
コード例内のコメントには `//` を使います。`/* */` は、その終端記号が外側のドキュメント コメントを早期終端させるため使いません。

```c
/**
 *  @brief          文字列を連結します。
 *  @param[out]     dest 連結先のバッファー。
 *  @param[in]      src 連結元の文字列。
 *  @param[in]      destSize dest のバッファー サイズ。
 *  @return         成功した場合は 0、失敗した場合は -1。
 *
 *  この関数は安全に文字列を連結します。
 *
 *  使用例:
    @code{.c}
    char buffer[100] = "Hello, ";
    const char *name = "World";
    if (concatenateString(buffer, name, sizeof(buffer)) == 0) {
        printf("%s\n", buffer);  // 出力: Hello, World
    }
    @endcode
 */
int concatenateString(char *dest, const char *src, size_t destSize);
```

#### @verbatim ~ @endverbatim を使用した例

```c
/**
 *  @brief          設定ファイルを読み込みます。
 *  @param[in]      configPath 設定ファイルのパス。
 *  @return         設定情報を格納した構造体へのポインター。
 *
 *  以下の形式の設定ファイルを読み込みます:
 *
    @verbatim
    # Configuration file
    server.host=localhost
    server.port=8080
    database.name=mydb
    database.user=admin
    @endverbatim
 *
 *  コメント行 (#) は無視されます。
 */
Config *loadConfig(const char *configPath);
```

#### プレーン テキストの例

Doxygen コメント内でプレーン テキストを記載する場合は、`@code{.unparsed}` を使用します。
`.unparsed` は構文ハイライトせず、Doxygen コマンドを解釈させずに内容をそのまま見せたい場合に適しています。
このリポジトリの固有ルールとして、plain text 本文の行頭に `*` は記載せず、コード ブロック本文は `@code{.unparsed}` に合わせて 4 の倍数カラムから開始します。
この書き方では字下げが保持され、コード ブロック本文中の `@param` は Doxygen コマンドとして扱われません。

なお、Doxygen では、ログ・設定・コマンド出力・ASCII 図のような純粋な逐語表示には `@verbatim ~ @endverbatim` が推奨されているため、`@verbatim ~ @endverbatim` を優先選択してください。

```c
/**
 *  @brief          プレーン テキストのサンプルを示します。
 *
    @code{.unparsed}
    plain text
        indentation is preserved
    @param is not treated as a command here
    @endcode
 */
void plain_text(void);
```

#### Markdown 形式を使用した例

Doxygen コメント内で Markdown 形式の fenced code block を使う場合は、バッククォート 3 つではなく `~~~` を使用します。
[Doxygen の Markdown マニュアル](https://www.doxygen.nl/manual/markdown.html#md_fenced) では `~~~` の形式が fenced code block の基本例として示されており、言語指定付きの C コードは `~~~{.c}` と記載できます。

> [!NOTE]
> このリポジトリの推奨は、`@code` によるコード ブロック記法のため、Doxygen コメント内での Markdown 形式での記述は非推奨です。

```c
/**
 *  @brief          データベースに接続します。
 *  @param[in]      connectionString 接続文字列。
 *  @return         接続ハンドル。
 *
 *  以下のように接続文字列を指定します:
 *
 *  ~~~{.txt}
    host=localhost port=5432 dbname=mydb user=admin password=secret
 *  ~~~
 *
 *  接続に失敗した場合は NULL を返します。
 *
 *  使用例:
 *
 *  ~~~{.c}
    const char *connStr = "host=localhost dbname=test";
    DbHandle *handle = connectDatabase(connStr);
    if (handle != NULL) {
        // データベース操作
        disconnectDatabase(handle);
    }
 *  ~~~
 */
DbHandle *connectDatabase(const char *connectionString);
```

#### 複数のコード例を含む場合

```c
/**
 *  @brief          ファイルの内容を読み込みます。
 *  @param[in]      filename ファイル名。
 *  @param[out]     buffer 読み込んだ内容を格納するバッファー。
 *  @param[in]      bufferSize バッファーのサイズ。
 *  @return         読み込んだバイト数。失敗時は -1。
 *
 *  基本的な使用例:
    @code{.c}
    char buffer[1024];
    ssize_t bytesRead = readFile("data.txt", buffer, sizeof(buffer));
    if (bytesRead > 0) {
        printf("Read %zd bytes\n", bytesRead);
    }
    @endcode
 *
 *  エラー処理を含む例:
    @code{.c}
    char buffer[1024];
    ssize_t bytesRead = readFile("data.txt", buffer, sizeof(buffer));
    if (bytesRead == -1) {
        fprintf(stderr, "Error: Failed to read file\n");
        return EXIT_FAILURE;
    } else if (bytesRead == 0) {
        printf("File is empty\n");
    } else {
        buffer[bytesRead] = '\0';
        printf("Content: %s\n", buffer);
    }
    @endcode
 */
ssize_t readFile(const char *filename, char *buffer, size_t bufferSize);
```

### 画像の挿入

`@image` コマンドを使用して、ドキュメントに画像を挿入できます。

注: `@image` コマンドを使った画像ベースのドキュメンテーションは、修正や grep チェック、構成管理が困難なため、可能な限り避けてください。

```c
/**
 *  @brief          プログラムのエントリ ポイント。
 *  @param[in]      argc コマンド ライン引数の数。
 *  @param[in]      argv コマンド ライン引数の配列。
 *  @return         成功時は 0、失敗時は 0 以外の値を返します。
 *
 *  以下に、calc コマンドの処理フローを示します。
 *
 *  @image          html calc-flow.png "calc コマンドの処理フロー"
 *
 *  @attention      引数は正確に 3 つ必要です。
 */
int main(int argc, char *argv[]);
```

### スレッド セーフの記載

スレッド セーフかどうかを明記する場合は、`@par スレッド セーフ` を使用します。  
Doxygen にスレッド セーフを表す専用コマンドはないため、`@par` でユーザー定義の見出しとして表現します。

`@par スレッド セーフ` は `@warning` の直前に配置します。

#### 表現の型

Microsoft Learn 日本語版の Win32 API 文書では、スレッド セーフ性をおおむね次の型で記述します。  
本 repo の Doxygen コメントもこの型に揃えます。

| 型 | 文頭 |
| ------------ | ------------------------------ |
| 関数単位安全 | 「本関数はスレッド セーフです。」 |
| 関数単位非安全 | 「本関数はスレッド セーフではありません。」 |
| 部分安全 | 「A はスレッド セーフではありませんが、B はスレッド セーフです。」 |
| 群全体安全 | 「本 API のすべての関数は、異なるスレッドから同時に呼び出しても安全です。」 |

文頭でスレッド セーフ性を断言した直後に、次の 1 つ以上を簡潔に補足します。

- どの単位が安全なのか (関数単位、オブジェクト単位、ハンドル単位)
- 同一インスタンス、同一引数に対する同時操作が可能なのか
- 非安全な場合、何が起きうるのか (未定義動作、列挙の取りこぼし、二重解放など)
- 呼び出し側で何を同期する必要があるのか

参考: Microsoft Learn 日本語版の `CryptGetProvParam`、`IXpsPrintJob::Cancel`、`WS_ERROR`、  
Windows Web Services「スレッド セーフ」、Direct3D 11 のマルチスレッド概要などの記述。

#### 関数単位で「スレッド セーフです」と明示する例

「スレッド セーフである」だけで終わらせず、**どの対象と同期されるか** または  
**同一インスタンスに対する同時呼び出しが可能か** を 1 行添えます。

`@par` タグの前には空行を入れてください。空行がないと直前の details 本文が `@par` の本文として扱われます。  
`@par` など別タグの本文に続けて通常の details を書き足す場合は、所属を明確にするため `@details` を明示してください。

```c
/**
 *  @brief          ロガーを設定します。
 *  @param[in]      level 出力する最低ログ レベル。
 *  @return         成功時は 0、失敗時は -1。
 *
 *  @par            スレッド セーフ
 *  本関数はスレッド セーフです。\n
 *  内部でミューテックスを使用しており、同一ロガー インスタンスに対して
 *  複数スレッドから同時に呼び出せます。
 *
 *  @warning        level に無効な値を指定した場合は失敗を返します。
 */
int logConfig(LogLevel level);
```

#### 関数単位で「スレッド セーフではありません」と明示する例

「スレッド セーフではない」だけで終わらせず、**何が起きうるか** または  
**呼び出し側で何を保証する必要があるか** を必ず添えます。

```c
/**
 *  @brief          メッセージを送信します。
 *  @param[in]      handle セッション ハンドル。
 *  @param[in]      data   送信データへのポインター。
 *  @param[in]      len    送信データのバイト数。
 *  @return         成功時は 0、失敗時は -1。
 *
 *  @par            スレッド セーフ
 *  本関数はスレッド セーフではありません。\n
 *  同一 @p handle への並行呼び出しは未定義動作です。送信は 1 スレッドから行ってください。
 *
 *  @warning        handle が NULL の場合は失敗を返します。
 */
int sendMessage(Handle handle, const void *data, size_t len);
```

#### 引数の依存条件を述べる例

CRT 薄ラッパーや内部に共有状態を持たないが、引数 (ポインターや `FILE*` など) に対する  
同時アクセス保証を呼び出し側に求める関数では、引数名を主語にして条件を述べます。

```c
/**
 *  @par            スレッド セーフ
 *  本関数はスレッド セーフです。\n
 *  内部に共有状態を持ちません。同一 @p stream を複数スレッドで共有する場合、
 *  個々の操作の整合性は CRT および呼び出し側の同期に依存します。
 */
```

#### 避ける書き方

- 「共有状態へのアクセス方法に依存します。呼び出し側で同期してください」のみの定型句で  
  終わらせる書き方は避けます。**スレッド セーフかどうかの結論を文頭で明示** したうえで、  
  対象と条件を続ける形に統一します。
- 「マルチ スレッド セーフ」「リエントラント」などの語を断り書きなしで使うと  
  読み手が解釈に揺れるため、まず「本関数はスレッド セーフです / ではありません。」で断言します。

## 他の参考サイト

- [実践で使える! Doxygen コメント完全ガイド 2024 – 明日から使えるベスト プラクティス 10 選](https://dexall.co.jp/articles/?p=1917)
