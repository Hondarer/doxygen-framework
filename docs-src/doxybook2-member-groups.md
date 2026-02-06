# doxybook2 のメンバーグループ非対応について

doxybook2 は Doxygen の「メンバーグループ」(`@name` + `@{`/`@}`) 機能に対応しておらず、`<sectiondef kind="user-defined">` の `<header>` と `<description>` を完全に無視します。これは doxybook2 の設計上の制限です。

## Doxygen のメンバーグループ機能

Doxygen では、`@name` コマンドと `@{`/`@}` マーカーを使用して、メンバーをグループ化できます。

```c
/**
 * @name コンパイラ検出マクロ
 * @{
 */

/** @brief MSVC コンパイラの場合に定義されます。 */
#define COMPILER_MSVC

/** @brief GCC コンパイラの場合に定義されます。 */
#define COMPILER_GCC

/** @} */
```

この記法により、Doxygen は XML 出力で `<sectiondef kind="user-defined">` を生成します。

## Doxygen XML 出力の構造

```xml
<sectiondef kind="user-defined">
  <header>コンパイラ検出マクロ</header>
  <description>
    <para>グループの詳細説明...</para>
  </description>
  <memberdef kind="define" id="...">
    <name>COMPILER_MSVC</name>
    <briefdescription>...</briefdescription>
  </memberdef>
  <memberdef kind="define" id="...">
    <name>COMPILER_GCC</name>
    <briefdescription>...</briefdescription>
  </memberdef>
</sectiondef>
```

## doxybook2 の処理

doxybook2 のソースコード (Node.cpp) では、`sectiondef` 要素を以下のように処理しています。

```cpp
auto sectiondef = compounddef.firstChildElement("sectiondef");
while (sectiondef) {
    auto memberdef = sectiondef.firstChildElement("memberdef");
    while (memberdef) {
        // memberdef のみを抽出
        memberdef = memberdef.nextSiblingElement("memberdef");
    }
    sectiondef = sectiondef.nextSiblingElement("sectiondef");
}
```

この処理により、以下の情報が失われます。

| XML 要素 | doxybook2 の処理 |
|----------|------------------|
| `sectiondef kind` 属性 | 確認しない (すべての sectiondef を同一視) |
| `<header>` | 読み取らない (無視される) |
| `<description>` | 読み取らない (無視される) |
| `<memberdef>` | 抽出され、kind 属性に基づいてカテゴリ分け |

## 出力結果

### 期待される出力

```markdown
## コンパイラ検出マクロ

グループの詳細説明...

### COMPILER_MSVC

MSVC コンパイラの場合に定義されます。

### COMPILER_GCC

GCC コンパイラの場合に定義されます。
```

### 実際の出力

```markdown
## 定数、マクロ

### COMPILER_MSVC

MSVC コンパイラの場合に定義されます。

### COMPILER_GCC

GCC コンパイラの場合に定義されます。
```

グループヘッダーとグループ説明が欠落し、すべてのマクロが「定数、マクロ」セクションにまとめられます。

## 推奨ワークアラウンド: `@section` によるファイルドキュメントの構造化

doxybook2 と Doxygen を併用するプロジェクトでは、メンバーグループ (`@name` + `@{`/`@}`) の代わりに、`@section` コマンドを使用してファイルドキュメント内で内容を構造化することを推奨します。

### 理由

1. **doxybook2 が正しく処理する**: `@section` は `<sect1>` 要素として出力され、doxybook2 で見出しとして変換されます。
2. **グループ説明が保持される**: テーブル、使用例、注意事項などの詳細説明がドキュメントに反映されます。
3. **ファイル単位での一覧性**: ファイルドキュメントを開くだけで、すべてのマクログループの概要が把握できます。

### 変換前 (メンバーグループ使用)

```c
/**
 *  @file           compiler.h
 *  @brief          コンパイラ検出マクロのヘッダーファイル。
 */

/**
 *  @name           コンパイラ検出マクロ
 *  @brief          コンパイラの種類を検出します。
 *
 *  | コンパイラ | 識別マクロ    |
 *  | ---------- | ------------- |
 *  | MSVC       | COMPILER_MSVC |
 *  | GCC        | COMPILER_GCC  |
 *
 *  @{
 */
#define COMPILER_MSVC  /*!< MSVC の場合に定義 */
#define COMPILER_GCC   /*!< GCC の場合に定義 */
/** @} */
```

### 変換後 (推奨: `@section` 使用)

```c
/**
 *******************************************************************************
 *  @file           compiler.h
 *  @brief          コンパイラ検出マクロのヘッダーファイル。
 *
 *  @section        compiler_detection コンパイラ検出マクロ
 *
 *  コンパイラの種類を検出します。
 *
 *  | コンパイラ | 識別マクロ    |
 *  | ---------- | ------------- |
 *  | MSVC       | COMPILER_MSVC |
 *  | GCC        | COMPILER_GCC  |
 *
 *  @note           Clang は __GNUC__ も定義するため、先に判定しています。
 *
 *******************************************************************************
 */

#define COMPILER_MSVC  /*!< MSVC の場合に定義 */
#define COMPILER_GCC   /*!< GCC の場合に定義 */
```

### 出力結果の比較

| 項目 | メンバーグループ | `@section` 使用 |
| --- | --- | --- |
| グループ見出し | ❌ 出力されない | ✅ 出力される |
| グループ説明 (テーブル等) | ❌ 出力されない | ✅ 出力される |
| 個別マクロの説明 | ✅ 出力される | ✅ 出力される |
| Doxygen HTML 出力 | ✅ グループ化表示 | ✅ セクション表示 |

### 注意事項

`@section` は Doxygen XML で `<sect1>` として出力されます。doxybook2 はこれを Markdown の `#` (レベル1) に変換しますが、ファイルドキュメントの構造上 `#####` (レベル5) が適切です。

同様に、`@subsection` は `<sect2>` として出力され、doxybook2 は `##` (レベル2) に変換しますが、`######` (レベル6) が適切です。

本フレームワークでは、`preprocess.sh` で以下の変換を行うことで、適切な見出しレベルで出力されるようにしています。

| Doxygen コマンド | XML 要素 | 変換後 | Markdown 見出し |
| --- | --- | --- | --- |
| `@section` | `<sect1>` | `<sect5>` | `#####` (レベル5) |
| `@subsection` | `<sect2>` | `<sect6>` | `######` (レベル6) |

### 参考

- `@section` コマンドの詳細: [commands.md](commands.md)
- 使用例: [cheatsheet.md](cheatsheet.md)
