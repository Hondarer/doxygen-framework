---
name: maintain-doxygen-comment
description: |
  C ソースコードに Doxygen 形式のコメントを付与するときに使うスキルです。
  docs の原典と app/calc/prod の実例をもとに、記載場所、タグの使い分け、
  避ける書き方、確認項目をまとめます。
when_to_use: |
  - C のヘッダーやソースに Doxygen コメントを新規追加するとき
  - 既存コメントを repo の流儀に合わせて修正するとき
  - `@section`、`@par`、`@code` などの使い分けに迷うとき
---

# Doxygen コメント付与

このスキルは C 向けです。
原典は `docs/commands.md` と `docs/cheatsheet.md` で、この文書は実際のコメント付与作業で迷いやすい判断を先にまとめます。

## まず見る資料

- `docs/cheatsheet.md`
  - そのまま流用しやすい雛形がまとまっています
  - 記載場所ごとのコメント例、表、コードブロック、スレッド セーフの例があります
- `docs/commands.md`
  - 各タグの意味と使い分けがあります
  - `@section` と `@par` の役割差、`@code` と `@verbatim` の選択基準を確認できます
- `app/calc/prod`
  - repo 内の実際の書き方を確認できます

## 基本方針

- 宣言がある API は、Doxygen コメントをヘッダー側に書きます
- 実装側に同じ関数コメントを重複記載しません
- 実装 `.c` には必要に応じてファイルコメントだけを置き、関数本体の直前には `/* doxygen コメントは、ヘッダーに記載 */` を使います
- `@brief` は Doxybook2 により Markdown の YAML front matter にある `summary` としても出力されるため、`Linux: fd` のような半角コロン + 空白を含む表現は避けます
- タグ一覧を埋めるのではなく、利用者が必要とする制約、戻り値、使用例、注意点を優先して書きます
- `docs/` にない表現を使う場合は、Doxygen 出力結果まで確認します

参照先:

- `app/calc/prod/include/libcalc.h`
- `app/calc/prod/include/libcalcbase.h`
- `app/calc/prod/libsrc/calc/calcHandler.c`
- `app/calc/prod/libsrc/calcbase/add.c`

## コメントをどこに書くか

### 公開関数、内部共有関数

ヘッダーの宣言側に書きます。
`app/calc/prod/include/libcalc.h` と `app/calc/prod/include/libcalcbase.h` が規範です。

```c
/**
 *******************************************************************************
 *  @brief          指定された演算種別に基づいて計算を実行します。
 *  @param[in]      kind 演算の種別。
 *  @param[in]      a 第一オペランド。
 *  @param[in]      b 第二オペランド。
 *  @param[out]     result 計算結果を格納するポインタ。
 *  @return         成功時は CALC_SUCCESS、失敗時はそれ以外を返します。
 *  @warning        無効な kind や NULL を指定した場合は失敗します。
 *******************************************************************************
 */
extern int calcHandler(const int kind, const int a, const int b, int *result);
```

実装側は次の形を基本にします。

```c
/* doxygen コメントは、ヘッダーに記載 */
int calcHandler(const int kind, const int a, const int b, int *result)
```

### `.c` ファイル自体の説明

実装ファイルには `@file` コメントを書いて構いません。
`app/calc/prod/libsrc/calc/calcHandler.c` や `app/calc/prod/src/cmd/add/add.c` の形に合わせます。

```c
/**
 *******************************************************************************
 *  @file           calcHandler.c
 *  @brief          calcHandler 関数の実装ファイル。
 *  @author         c-modernization-kit sample team
 *  @date           2025/11/22
 *  @version        1.0.0
 *
 *  演算種別に基づいて適切な計算関数を呼び出すハンドラーを提供します。
 *
 *  @copyright      Copyright (C) CompanyName, Ltd. 2025. All rights reserved.
 *******************************************************************************
 */
```

## 使うことが多いタグ

### 関数コメントの基本セット

まずは次を起点にします。

```c
/**
 *******************************************************************************
 *  @brief          関数の役割を 1 行で書きます。
 *  @param[in]      input 参照専用の入力を説明します。
 *  @param[out]     output 出力先を説明します。
 *  @param[in,out]  state 更新される値を説明します。
 *  @return         戻り値の意味を説明します。
 *******************************************************************************
 */
```

必要に応じて以下を追加します。

- `@details`
  - `@brief` に収まらない処理概要や前提知識を書くとき
- `@pre`
  - 呼び出し前に満たす条件があるとき
- `@post`
  - 呼び出し後の状態保証が重要なとき
- `@attention`
  - 利用上の強い制約を書くとき
- `@warning`
  - 失敗条件や危険な使い方を書くとき
- `@note`
  - 技術的な背景や補足を書くとき
- `@remarks`
  - 運用上のヒントを書くとき
- `@deprecated`
  - 非推奨 API を示すとき
- `@since`
  - 導入バージョンが重要なとき

`@param` は宣言と一致している必要があります。
名前漏れや方向指定の誤りは警告原因になるため、関数シグネチャと一緒に確認します。

### `@brief` と YAML front matter

`@brief` は生成後の Markdown で `summary` にも使われます。
次のように半角コロンの直後へ空白を置く文は、YAML の構文と衝突する場合があります。

```c
/**
 *  @brief  ファイルハンドルの抽象化構造体 (Linux の fd、Windows の HANDLE を保持)。
 */
```

短い説明は YAML と衝突しにくい文にし、詳しい説明は `@details` や本文へ分けます。

### ファイルコメント

`@file`、`@brief`、本文、`@copyright` を基本とします。
`@author`、`@date`、`@version`、`@par History` は、対象モジュールの慣例に合わせて追加します。

### マクロと定数

短い説明で済むマクロは末尾コメントを使います。
`app/calc/prod/include/libcalc_const.h` が規範です。

```c
#define CALC_SUCCESS 0  /**< 成功の戻り値を表す定数。 */
#define CALC_ERROR   -1 /**< 失敗の戻り値を表す定数。 */
```

複数のマクロをまとめて説明したい場合は、ファイルコメント内で `@section` を使います。
`docs/cheatsheet.md` の `compiler.h` 例が `@section` の参照先で、`app/calc/prod/include/libcalc.h` の `#ifdef DOXYGEN` ブロックはマクロ説明の実例です。

### 列挙体、構造体、メンバー

型全体には `@brief` を置き、各要素やメンバーには `/**< ... */` を使います。

```c
/**
 *  @brief          ユーザー情報を保持する構造体です。
 */
typedef struct
{
    int id;               /**< ユーザー ID。 */
    const char *name;     /**< ユーザー名。 */
} UserInfo;
```

## `@section` と `@par` の使い分け

### `@section`

ファイル全体を構造化するときに使います。
主な用途は、ヘッダー内で関連するマクロ群や定義群をまとめて説明することです。

```c
/**
 *  @section        compiler_detection コンパイラ検出マクロ
 *
 *  検出されたコンパイラに応じて定義されるマクロを説明します。
 */
```

### `@par`

関数やファイルに補足の見出しを足したいときに使います。
`History` や `スレッド セーフ` のように、Doxygen に専用タグがない項目に向いています。

```c
/**
 *  @par            スレッド セーフ
 *  本関数はスレッドセーフではありません。\n
 *  同一ハンドルへの並行呼び出しは未定義動作です。
 *
 *  @warning        handle が NULL の場合は失敗を返します。
 */
```

`@par スレッド セーフ` は `@warning` の直前に置くのがこの repo の慣例です。

## コード例と文章整形

### `@code{.c} ~ @endcode`

プログラミングコードの例は、まずこれを使います。
`@code` と `@endcode` の行には `*` を付け、コード本体には `*` を付けません。

```c
/**
 *  @par            使用例
 *  @code{.c}
    int result;
    if (add(10, 20, &result) == CALC_SUCCESS) {
        printf("%d\n", result);
    }
 *  @endcode
 */
```

参照先:

- `app/calc/prod/include/libcalc.h`
- `app/calc/prod/include/libcalcbase.h`
- `app/calc/prod/src/cmd/add/add.c`

### `@verbatim ~ @endverbatim`

シェルコマンド、設定ファイル、Doxygen コマンド自体の例示に使います。
シンタックスハイライトは不要だが、そのままの形を保ちたいときに選びます。

### Markdown 形式のコードブロック

複数言語が混ざる例では Markdown のコードブロックも使えます。
ただし、この repo では C の使用例が中心なので、関数コメント内のコード例は `@code{.c}` を優先して問題ありません。

### 改行

コメント本文の途中で明示的に改行したい場合は `\n` を使います。
`<br />` は VS Code のツールチップで改行として扱われないため非推奨です。

## 表、PlantUML、画像

### 表

- 表の `|` は字下げしすぎないようにします
- Markdown pipe tables は制限があるため、複雑な表は避けます
- 見出しに日本語を使う場合、罫線の `-` の数によって表示が崩れることがあるため、生成結果を確認します

### PlantUML

図が本当に必要なら PlantUML を使います。
`@startuml` から `@enduml` の範囲は行頭の `*` を付けない形にします。

### `@image`

画像ベースの説明は、修正、grep、構成管理が難しいため、可能な限り避けます。
まずはテキスト、表、コード例、PlantUML を検討します。

## repo 内の実例

### 関数コメントを宣言側に置く例

- `app/calc/prod/include/libcalc.h`
- `app/calc/prod/include/libcalcbase.h`

### 実装側で重複記載しない例

- `app/calc/prod/libsrc/calc/calcHandler.c`
- `app/calc/prod/libsrc/calcbase/add.c`
- `app/calc/prod/libsrc/calcbase/subtract.c`
- `app/calc/prod/libsrc/calcbase/multiply.c`
- `app/calc/prod/libsrc/calcbase/divide.c`

### ファイルコメントと `main()` コメントの例

- `app/calc/prod/src/cmd/add/add.c`
- `app/calc/prod/src/cmd/calc/calc.c`
- `app/calc/prod/src/cmd/shared-and-static-calc/shared-and-static-calc.c`

### マクロ説明の例

- `app/calc/prod/include/libcalc_const.h`
- `app/calc/prod/include/libcalc.h`

## 作業手順

1. 対象がヘッダーかソースかを確認する
2. 宣言側に置くべきコメントか、ファイルコメントか、末尾コメントかを決める
3. `docs/cheatsheet.md` の雛形を起点に必要なタグだけ残す
4. `docs/commands.md` を見て、`@section`、`@par`、`@code` などの使い分けを確認する
5. `app/calc/prod` の近い例に表記を揃える
6. Doxygen の変換結果で崩れや警告が出そうな箇所を見直す

## 避ける書き方

- ヘッダーとソースの両方に同じ関数コメントを持たせる
- `@brief` に `Linux: fd` のような半角コロン + 空白を含む表現を置く
- `@param` の名前や方向が宣言と一致していない
- `@section` を関数単位の補足見出しに使う
- `@par` でファイル全体の大きな構造化をしようとする
- `@code` ブロックのコード本体まで `*` を付ける
- `<br />` を改行用途で使う
- 画像だけに依存した説明を作る
- docs にない複雑な書式を、出力確認なしで採用する

## 確認項目

- コメントの記載場所が適切か
- `@brief` が YAML front matter の `summary` として出力されても解釈を壊さないか
- `@brief` だけで足りない内容は `@details` や `@note` に分離できているか
- `@param`、`@return`、`@warning` が実装と矛盾していないか
- `@section` と `@par` の使い分けが適切か
- コードブロック、表、PlantUML の書式が `docs/` の規約に沿っているか
- `app/calc/prod` の既存表記から不必要に外れていないか
