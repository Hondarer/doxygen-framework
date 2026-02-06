# CheatSheet

[Doxygen チートシート](https://qiita.com/yuta-yoshinaga/items/84887a89f6a21a7dcfd5) を参考に C 言語用にアレンジしたチートシートです。

Doxygen の生成処理は制限が多く、記載した内容が正しくドキュメント化されない場合が多いため、本チートシートをコピー＆ペーストして品質の良い Doxygen コメントを付与してください。

以下に無い記載を行う場合は、期待通りの出力が行われるかどうか、生成結果を確認するようにしてください。

## 関数のコメントをどこで行うべきか

ライブラリとヘッダを配布した際に VS Code が解釈できるようにするため、ヘッダ (宣言) 側の Doxygen コメントは必ず記載してください。

ソース (実装) 側は、同じ Doxygen コメントを記載しておくこともできますが、情報が重複し保守性に懸念があることから、以下のようにするとよいでしょう。

```c
/* doxygen コメントは、ヘッダに記載 */
int calcHandler(int kind, int a, int b)
```

## 記載場所別の例

### ソース・ヘッダーファイル

`History` というコマンド (タグ) は存在しないので、ユーザー定義の見出しで表現しています。

```c
/**
 *******************************************************************************
 *  @file           filename.c
 *  @brief          ファイルの概要を表します。
 *  @author         初版作成者を表します。
 *  @date           yyyy/mm/dd (初版作成年月日を表します。)
 *  @version        現在のバージョンを表します。
 *  @par            History
 *                  - yyyy/mm/dd [修正ID](https://example.com/id/1234) 修正の概要
 *                      - 子リスト1
 *                      - 子リスト2
 *                  - yyyy/mm/dd [修正ID](https://example.com/id/5678) 修正の概要
 *                      - 子リスト1
 *                        子リスト1の続き
 *
 *  コマンド (タグ) のないコメントは、details として扱われます。
 *  前のブロックと分離するために 1 行あけて記載します。
 *
 *  もし、ブロック内での改行を行いたい場合は、\n
 *  を使って改行します。`<br />` での改行は VS Code のツールチップで
 *  改行と解釈されないことから非推奨です。
 *
 *  @copyright Copyright (C) CompanyName, Ltd. 2023-2025. All rights reserved.
 *
 *******************************************************************************
 */
```

### ヘッダーファイル (`@section` を使用した構造化)

複数のマクロや定義をグループ化して説明する場合は、`@section` を使用します。

```c
/**
 *******************************************************************************
 *  @file           compiler.h
 *  @brief          コンパイラ検出および抽象化マクロのヘッダーファイル。
 *  @author         c-modernization-kit sample team
 *  @date           2026/02/06
 *
 *  コンパイラの種類とバージョンを検出し、統一的なマクロを定義します。
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
 *  @code{.c}
 *  #include "compiler.h"
 *
 *  FORCE_INLINE int fast_add(int a, int b)
 *  {
 *      return a + b;
 *  }
 *  @endcode
 *
 *  @copyright      Copyright (C) CompanyName, Ltd. 2025. All rights reserved.
 *
 *******************************************************************************
 */
```

### 関数 (メソッド)

```c
/**
 *******************************************************************************
 *  @brief          関数の説明を表します。
 *  @param[in]      引数 (参照専用)
 *  @param[out]     引数 (ポインタ引数等)
 *  @param[in,out]  引数 (ポインタ引数等)
 *  @return         関数戻り値の説明
 *  @warning        重大なエラーや危険の回避のための警告を表します。
 *  @attention      必須の制約条件・使用条件などの注意を表します。
 *  @note           技術的な背景や実装の注釈を表します。
 *  @remarks        使用上のヒントや最適化のアドバイスなどの補足情報を表します。
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
 *******************************************************************************
 */
```

### 構造体および class のメンバー

```c
    int     intval;         /*!< 変数の説明 */
```

```c
 /**
 *  @brief          サンプルの列挙体を定義します。
 */
enum SampleEnum
{
    one,  /*!< 1 つめの要素 */
    two,  /*!< 2 つめの要素 */
    three /*!< 3 つめの要素 */
};
```

```c
/**
 *  @brief          ユーザー情報を保持する構造体を定義します。
 */
typedef struct
{
    int id;               /*!< ユーザーID */
    const char *name;     /*!< ユーザー名 */
    SampleEnum enumValue; /*!< 列挙値 */
} UserInfo;
```

## シナリオ別の記載例

### リスト

```c
/**
 *******************************************************************************
 *  @todo
 *                  - 親リスト1
 *                      - 子リスト1
 *                      - 子リスト2
 *                  - 親リスト2
 *                      - 子リスト1
 *                      - 子リスト2
 *******************************************************************************
 */
```

```c
/**
 *******************************************************************************
 *  @todo           Todo リストの説明
 *                  - 親リスト1
 *                      - 子リスト1
 *                      - 子リスト2
 *                  - 親リスト2
 *                      - 子リスト1
 *                      - 子リスト2
 *******************************************************************************
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
 *******************************************************************************
 *  @details
 *  表を書く際の列セパレータ `|` の字下げは行わないようにします。  
 *  (字下げが多いとプレーン テキストのコード ブロックとして解釈されるため)
 * 
 *  | No. | 名称                | 備考                        |
 *  | --: | ------------------- | --------------------------- |
 *  |   1 | 名称1               |                             |
 *  |   2 | 名称2               |                             |
 * 
 *  Table: 表のキャプション
 *******************************************************************************
 */
```

```c
/**
 *******************************************************************************
 *  @details
 *  | No. | ヘッダ文字列       |
 *  | --: | ------------------ |
 *  |   1 | 内容1<br />内容2   |
 *  |   2 | テスト             |
 *  |   3 | Test               |
 *
 *  Table: セル内での改行を含む表
 *******************************************************************************
 */
```

### コードの埋め込み

#### `@code ~ @endcode` を使用した例

```c
/**
 *******************************************************************************
 *  @brief          文字列を連結します。
 *  @param[out]     dest 連結先のバッファ。
 *  @param[in]      src 連結元の文字列。
 *  @param[in]      destSize dest のバッファサイズ。
 *  @return         成功した場合は 0、失敗した場合は -1。
 *  @details
 *  この関数は安全に文字列を連結します。
 *
 *  使用例:
 *  @code{.c}
 *  char buffer[100] = "Hello, ";
 *  const char *name = "World";
 *  if (concatenateString(buffer, name, sizeof(buffer)) == 0) {
 *      printf("%s\n", buffer);  // 出力: Hello, World
 *  }
 *  @endcode
 *******************************************************************************
 */
int concatenateString(char *dest, const char *src, size_t destSize);
```

#### `@verbatim ~ @endverbatim` を使用した例

```c
/**
 *******************************************************************************
 *  @brief          設定ファイルを読み込みます。
 *  @param[in]      configPath 設定ファイルのパス。
 *  @return         設定情報を格納した構造体へのポインタ。
 *  @details
 *  以下の形式の設定ファイルを読み込みます:
 *
 *  @verbatim
 *  # Configuration file
 *  server.host=localhost
 *  server.port=8080
 *  database.name=mydb
 *  database.user=admin
 *  @endverbatim
 *
 *  コメント行 (#) は無視されます。
 *******************************************************************************
 */
Config *loadConfig(const char *configPath);
```

#### Markdown 形式を使用した例

```c
/**
 *******************************************************************************
 *  @brief          データベースに接続します。
 *  @param[in]      connectionString 接続文字列。
 *  @return         接続ハンドル。
 *  @details
 *  以下のように接続文字列を指定します:
 *
 *  ```text
 *  host=localhost port=5432 dbname=mydb user=admin password=secret
 *  ```
 *
 *  接続に失敗した場合は NULL を返します。
 *
 *  使用例:
 *
 *  ```c
 *  const char *connStr = "host=localhost dbname=test";
 *  DbHandle *handle = connectDatabase(connStr);
 *  if (handle != NULL) {
 *      // データベース操作
 *      disconnectDatabase(handle);
 *  }
 *  ```
 *******************************************************************************
 */
DbHandle *connectDatabase(const char *connectionString);
```

#### 複数のコード例を含む場合

```c
/**
 *******************************************************************************
 *  @brief          ファイルの内容を読み込みます。
 *  @param[in]      filename ファイル名。
 *  @param[out]     buffer 読み込んだ内容を格納するバッファ。
 *  @param[in]      bufferSize バッファのサイズ。
 *  @return         読み込んだバイト数。失敗時は -1。
 *
 *  @details
 *  基本的な使用例:
 *  @code{.c}
 *  char buffer[1024];
 *  ssize_t bytesRead = readFile("data.txt", buffer, sizeof(buffer));
 *  if (bytesRead > 0) {
 *      printf("Read %zd bytes\n", bytesRead);
 *  }
 *  @endcode
 *
 *  エラー処理を含む例:
 *  @code{.c}
 *  char buffer[1024];
 *  ssize_t bytesRead = readFile("data.txt", buffer, sizeof(buffer));
 *  if (bytesRead == -1) {
 *      fprintf(stderr, "Error: Failed to read file\n");
 *      return EXIT_FAILURE;
 *  } else if (bytesRead == 0) {
 *      printf("File is empty\n");
 *  } else {
 *      buffer[bytesRead] = '\0';
 *      printf("Content: %s\n", buffer);
 *  }
 *  @endcode
 *******************************************************************************
 */
ssize_t readFile(const char *filename, char *buffer, size_t bufferSize);
```
