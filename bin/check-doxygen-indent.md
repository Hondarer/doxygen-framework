# Doxygen コメント字下げレベルチェック・修正コマンド

`check-doxygen-indent.py` は、Doxygen コメントブロック（`/**` から `*/` まで）の字下げレベルが統一されているかをチェックし、不統一な場合に修正するコマンドです。

## 問題の背景

clang-format は、`/**` の行の字下げレベルを文脈に応じて自動調整します（例：extern C ブロック内では + 4 スペース）。しかし、その後に続く `* @brief` や `*/` の行の字下げレベルは自動調整されないため、見た目に矛盾が生じます。

### 不正な形式の例

```c
extern "C" {
/**
 * @brief  関数の説明です。
 */
void func(void);
}
```

修正後（`/**` が +4 スペース）：

```c
extern "C" {
    /**
     * @brief  関数の説明です。
     */
    void func(void);
}
```

しかし clang-format は `/**` のみ調整し、後続行は調整しません：

```c
extern "C" {
    /**
 * @brief  関数の説明です。  ← 字下げレベルが一致していない
 */
    void func(void);
}
```

本コマンドは、このような矛盾を検出し、すべての行の字下げレベルを統一します。

## インストール

`check-doxygen-indent.py` は `framework/doxyfw/bin/` に配置されています。

```bash
chmod +x framework/doxyfw/bin/check-doxygen-indent.py
```

## 使用方法

### チェックモード（既定）

指定したファイルまたはディレクトリをスキャンし、字下げレベルの不一致を報告します。

```bash
# 単一ファイルをチェック
python3 framework/doxyfw/bin/check-doxygen-indent.py --check app/com_util/prod/include/com_util/sync/sync.h

# ディレクトリ配下のすべての .h ファイルをチェック
python3 framework/doxyfw/bin/check-doxygen-indent.py --check app/com_util/prod/include/com_util
```

出力例：

```
🔍 チェックモード: 30 ファイルをスキャン中...

✅ 30 ファイルをスキャン: 問題なし
```

問題が見つかった場合：

```
❌ Doxygen コメント字下げレベルの不一致が検出されました

📄 app/com_util/prod/include/com_util/runtime/shutdown.h
  L42: /** (indent=4)
  期待される後続行のインデント: 5
    ✗ L43: indent=9 (expected=5)
       '         *  @enum           com_util_shutdown_code_kind_t'
    ...
```

### 修正プレビューモード

修正内容を表示します。実際には修正しません。

```bash
python3 framework/doxyfw/bin/check-doxygen-indent.py --dry-run app/com_util/prod/include/com_util/runtime/shutdown.h
```

出力例：

```
🔍 修正プレビューモード: 1 ファイルを処理中...

📄 app/com_util/prod/include/com_util/runtime/shutdown.h
  修正対象: 13 行

    L43: indent 9 → 5
      before: '         *  @enum           com_util_shutdown_code'
      after:  '     *  @enum           com_util_shutdown_code_kin'
    ...

📊 修正予定: 1 ファイル, 13 行

💡 実際に修正するには --fix オプションを使用してください
```

### 修正モード

実際にファイルの字下げレベルを修正します。

```bash
python3 framework/doxyfw/bin/check-doxygen-indent.py --fix app/com_util/prod/include/com_util/runtime/shutdown.h
```

出力例：

```
🔧 修正モード: 1 ファイルを処理中...

✅ 1 ファイルを修正しました (13 行)
  app/com_util/prod/include/com_util/runtime/shutdown.h: 13 行修正
```

修正後は、clang-format を適用して体裁を整えます。

```bash
clang-format -i app/com_util/prod/include/com_util/runtime/shutdown.h
```

## オプション

### --check（既定）

チェックモード：問題を検出して報告します。

### --dry-run

修正プレビューモード：修正内容を表示します（実際には修正しません）。

### --fix

修正モード：字下げレベルを統一します。

### --include-single-line

末尾コメント（`/**< ... */` が同一行）も対象に含めます。既定では除外されます。

```bash
# マクロの末尾コメントも処理する場合
python3 framework/doxyfw/bin/check-doxygen-indent.py --check --include-single-line app/com_util/prod/include
```

## 動作原理

### チェック処理

1. ファイルを行単位で走査
2. `/**` で始まるコメントを検出
3. 末尾コメント形式（`/**< ... */` が同一行）の場合はスキップ（既定）
4. `/**` のインデントを基準に、後続行の期待インデント（`/** のインデント + 1`）を計算
5. 後続行のインデントが期待値と異なる場合を報告
6. `*/` に到達するまで繰り返す

### 修正処理

1. スキャンと同じ方法で対象を特定
2. 不一致のある行を修正（期待インデントに揃える）
3. 改行文字を保持しながら修正
4. ファイルを上書き（`--dry-run` の場合は上書きしない）

## トラブルシューティング

### 「ファイルが見つかりません」

```bash
❌ エラー: .h ファイルが見つかりません
```

ターゲットが `.h` ファイルを含んでいることを確認してください。

```bash
python3 framework/doxyfw/bin/check-doxygen-indent.py --check app/com_util/prod/include/com_util
```

### 修正後に clang-format で元に戻る

本コマンド で修正したあと、`clang-format` を適用すると、`/**` の行の字下げレベルが再度調整される場合があります。その場合は、修正を繰り返すか、clang-format の設定を見直してください。

通常の workflow：

```bash
# 1. 修正プレビューで確認
python3 framework/doxyfw/bin/check-doxygen-indent.py --dry-run <target>

# 2. 実際に修正
python3 framework/doxyfw/bin/check-doxygen-indent.py --fix <target>

# 3. clang-format で体裁を整える
clang-format -i <target>

# 4. 再度チェック（問題があれば繰り返す）
python3 framework/doxyfw/bin/check-doxygen-indent.py --check <target>
```

## 関連ドキュメント

- `framework/doxyfw/.agents/skills/maintain-doxygen-comment/SKILL.md` — Doxygen コメント作成ガイドライン
- `framework/doxyfw/docs/cheatsheet.md` — Doxygen 記法チートシート
- `framework/doxyfw/docs/commands.md` — Doxygen コマンド リファレンス
