# Doxygen コメント字下げレベル チェック・修正コマンド

`check-doxygen-indent.py` は、Doxygen コメント ブロック (`/**` から `*/` まで) の字下げレベルが統一されているかをチェックし、不統一な場合に修正するコマンドです。  
行頭に `*` を置かずに記述した図ブロックの字下げもチェックします (図ブロックは修正しません)。

## 問題の背景

clang-format は、`/**` の行の字下げレベルを文脈に応じて自動調整します (例: extern C ブロック内では + 4 スペース)。しかし、その後に続く `* @brief` や `*/` の行の字下げレベルは自動調整されないため、見た目に矛盾が生じます。

### 不正な形式の例

```c
extern "C" {
/**
 * @brief  関数の説明です。
 */
void func(void);
}
```

修正後 (`/**` が +4 スペース):

```c
extern "C" {
    /**
     * @brief  関数の説明です。
     */
    void func(void);
}
```

しかし clang-format は `/**` のみ調整し、後続行は調整しません:

```c
extern "C" {
    /**
 * @brief  関数の説明です。  ← 字下げレベルが一致していない
 */
    void func(void);
}
```

本コマンドは、このような矛盾を検出し、すべての行の字下げレベルを統一します。

### 図ブロックの字下げ

図ブロック (`@mermaid` 〜 `@endmermaid`、`@startuml` 〜 `@enduml`) は、エディターのプレビューを利用できるよう、行頭の `*` を置かずに記述できます。  
この場合、図ブロックの字下げは次の規範に従います。

- 開始行と終了行は、コメント本文と同じ桁に置きます。コメント本文の桁は、`*` を持つ行で `*` と後続の空白の次に来る文字の位置です。
- 図の本文は、開始行より浅い位置に置きません。

```c
    /**
     *  @par            呼び出しシーケンス
     *  処理の流れを示します。
     *
        @mermaid "処理の流れ"
        sequenceDiagram
            Caller->>API: 呼び出し
        @endmermaid
     *
     *  @par            スレッド セーフティ
     *  スレッド セーフです。
     */
```

この例のコメント本文の桁は 8 (0 始まり) で、開始行 `@mermaid` と終了行 `@endmermaid` も 8 桁目にあります。

規範に違反しても、Doxygen は多くの場合に警告を出しません。  
開始行が本文より浅いと、前後の `@par` の節が字下げコード ブロック (XML の `<verbatim>`) として出力されます。  
開始行が本文より深いと、図ブロック自体が `<verbatim>` になります。  
本コマンドは、このような字下げの不一致を検出します。

## インストール

`check-doxygen-indent.py` は `framework/doxyfw/bin/` に配置されています。

```bash
chmod +x framework/doxyfw/bin/check-doxygen-indent.py
```

## 使用方法

### チェック モード (既定)

指定したファイルまたはディレクトリをスキャンし、字下げレベルの不一致を報告します。

```bash
# 単一ファイルをチェック
python3 framework/doxyfw/bin/check-doxygen-indent.py --check app/example/prod/include/example/sync/sync.h

# ディレクトリ配下のすべての .h ファイルをチェック
python3 framework/doxyfw/bin/check-doxygen-indent.py --check app/example/prod/include/example
```

出力例:

```text
🔍 チェックモード: 30 ファイルをスキャン中...

✅ 30 ファイルをスキャン: 問題なし
```

問題が見つかった場合:

```
❌ Doxygen コメント字下げレベルの不一致が検出されました

📄 app/example/prod/include/example/runtime/shutdown.h
  L42: /** (indent=4)
  期待される後続行のインデント: 5
    ✗ L43: indent=9 (expected=5)
       '         *  @enum           cplat_shutdown_code_kind'
    ...
```

図ブロックの字下げの不一致が見つかった場合:

```text
❌ Doxygen コメントの図ブロックの字下げの不一致が検出されました

📄 app/example/prod/include/example/runtime/sequence.h
  L130: @mermaid (コメント本文の桁: 8)
    ✗ L130: 開始行 indent=4 (expected=8)
       '    @mermaid "example_run の呼び出しシーケンス"'
    ✗ L133: 図の本文 indent=2 (expected>=4)
       '  Caller->>API: 呼び出し'

💡 図ブロックは自動修正しません。開始行と終了行をコメント本文の桁に揃え、図の本文を開始行より浅くしないでください

📊 合計: 30 ファイルをスキャン
   1 個の図ブロックで字下げの不一致を検出
   2 行の図ブロックの不一致
```

開始行と図の本文の指摘には `✗`、終了行の指摘には `━` を付けます。`indent` は現在の桁、`expected` は期待する桁です。  
図の本文の指摘は `(expected>=4)` のように、開始行の桁以上を期待する形で表示します。

字下げレベルの不一致または図ブロックの字下げの不一致がある場合、チェック モードの終了コードは 1 です。

### 修正プレビュー モード

修正内容を表示します。実際には修正しません。

```bash
python3 framework/doxyfw/bin/check-doxygen-indent.py --dry-run app/example/prod/include/example/runtime/shutdown.h
```

出力例:

```
🔍 修正プレビューモード: 1 ファイルを処理中...

📄 app/example/prod/include/example/runtime/shutdown.h
  修正対象: 13 行

    L43: indent 9 → 5
      before: '         *  @enum           cplat_shutdown_code'
      after:  '     *  @enum           cplat_shutdown_code_kin'
    ...

📊 修正予定: 1 ファイル, 13 行

💡 実際に修正するには --fix オプションを使用してください
```

図ブロックの字下げの不一致は、修正を反映した場合の内容でチェックし、チェック モードと同じ形式で修正プレビューの後に表示します。

### 修正モード

実際にファイルの字下げレベルを修正します。

```bash
python3 framework/doxyfw/bin/check-doxygen-indent.py --fix app/example/prod/include/example/runtime/shutdown.h
```

出力例:

```
🔧 修正モード: 1 ファイルを処理中...

✅ 1 ファイルを修正しました (13 行)
  app/example/prod/include/example/runtime/shutdown.h: 13 行修正
```

修正モードは図ブロックを書き換えません。修正後の内容でチェックし、図ブロックの字下げの不一致を指摘として表示します。  
修正プレビュー モードと修正モードの終了コードは、図ブロックの指摘の有無にかかわらず 0 です。

修正後は、clang-format を適用して体裁を整えます。

```bash
clang-format -i app/example/prod/include/example/runtime/shutdown.h
```

## オプション

### --check (既定)

チェック モード: 問題を検出して報告します。

### --dry-run

修正プレビュー モード: 修正内容を表示します (実際には修正しません)。

### --fix

修正モード: 字下げレベルを統一します。

### --include-single-line

末尾コメント (`/**< ... */` が同一行) も対象に含めます。既定では除外されます。

```bash
# マクロの末尾コメントも処理する場合
python3 framework/doxyfw/bin/check-doxygen-indent.py --check --include-single-line app/example/prod/include
```

## 動作原理

### チェック処理

1. ファイルを行単位で走査
2. `/**` で始まるコメントを検出
3. 末尾コメント形式 (`/**< ... */` が同一行) の場合はスキップ (既定)
4. `/**` のインデントを基準に、後続行の期待インデント (`/** のインデント + 1`) を計算
5. 後続行のインデントが期待値と異なる場合を報告
6. `*/` に到達するまで処理を反復

### 図ブロックのチェック処理

1. `/**` から `*/` までのコメント内で、行頭に `*` を置かずに記述された図ブロックの開始行を検出
    - 開始行: `@mermaid`、`@startuml`、`\mermaid`、`\startuml`
    - 終了行: `@endmermaid`、`@enduml`、`\endmermaid`、`\enduml`
2. 図ブロックより前にある、`*` を持ち本文のある最も近い行から、コメント本文の桁を求める
3. 開始行または終了行の字下げがコメント本文の桁と一致しない場合を報告
4. 図の本文 (空行を除く) に開始行より浅い行がある場合を報告

行頭に `*` を持つ図ブロック (`*  @mermaid` の形式) は、字下げレベルのチェックの対象であり、図ブロックのチェックの対象外です。  
図ブロックより前に本文のある行がない場合は、開始行と終了行の桁をチェックせず、図の本文の深さだけをチェックします。

### 修正処理

1. スキャンと同じ方法で対象を特定
2. 不一致のある行を修正 (期待インデントに揃える)
3. 改行文字を保持しながら修正
4. ファイルを上書き (`--dry-run` の場合は上書きしない)

図ブロックは修正の対象外です。  
図の本文の相対的な字下げを保ったまま移動する必要があるため、図ブロックの字下げは手動で修正します。

## トラブルシューティング

### 「ファイルが見つかりません」

```bash
❌ エラー: .h ファイルが見つかりません
```

ターゲットが `.h` ファイルを含んでいることを確認してください。

```bash
python3 framework/doxyfw/bin/check-doxygen-indent.py --check app/example/prod/include/example
```

### 修正後に clang-format で元に戻る

本コマンドで修正した後、`clang-format` を適用すると、`/**` の行の字下げレベルが再度調整される場合があります。その場合は、修正を繰り返すか、clang-format の設定を見直してください。

通常のワークフロー:

```bash
# 1. 修正プレビューで確認
python3 framework/doxyfw/bin/check-doxygen-indent.py --dry-run <target>

# 2. 実際に修正
python3 framework/doxyfw/bin/check-doxygen-indent.py --fix <target>

# 3. clang-format で体裁を整える
clang-format -i <target>

# 4. 再度チェック (問題があれば繰り返す)
python3 framework/doxyfw/bin/check-doxygen-indent.py --check <target>
```

## 関連ドキュメント

- `framework/doxyfw/.agents/skills/maintain-doxygen-comment/SKILL.md` — Doxygen コメント作成ガイドライン
- `framework/doxyfw/docs/cheatsheet.md` — Doxygen 記法チート シート
- `framework/doxyfw/docs/commands.md` — Doxygen コマンド リファレンス
