# Doxygen 着色出力の調査結果

## 調査概要

Doxygen の警告・エラーメッセージに対する ANSI カラーコード着色機能の有無について調査を実施しました。

## 調査結果

### Doxygen 本体の機能

Doxygen には、**警告やエラーメッセージを着色する機能は実装されていません**。

2022 年 1 月に GitHub Issue [#9038](https://github.com/doxygen/doxygen/issues/9038) にて機能要望が提出されていますが、2025 年 11 月時点でも未実装の状態です。

### 代替アプローチ

Doxygen 本体に機能がないため、外部フィルタースクリプトによる着色を実装しました。

## 実装方針

### 検出パターン

誤検知を防ぐため、以下のパターンでマッチングを行います。

- エラー: ` error: ` (前後にスペースを含む)
- ワーニング: ` warning: ` (前後にスペースを含む)

スペースを含めることで、コード内の文字列や変数名との誤マッチを防止します。

### 着色方法

ANSI カラーコードを使用して、ターミナル出力に色を付けます。

- エラー: 赤色 (ANSI コード `\033[0;31m`)
- ワーニング: 黄色 (ANSI コード `\033[0;33m`)
- リセット: `\033[0m`

## Doxygen の警告関連設定

Doxyfile には以下の警告関連設定が存在します。

```text
WARNINGS               = YES
WARN_IF_UNDOCUMENTED   = YES
WARN_IF_DOC_ERROR      = YES
WARN_IF_INCOMPLETE_DOC = YES
WARN_NO_PARAMDOC       = NO
WARN_IF_UNDOC_ENUM_VAL = NO
WARN_LAYOUT_FILE       = YES
WARN_AS_ERROR          = NO
WARN_FORMAT            = "$file:$line: $text"
WARN_LINE_FORMAT       = "at line $line of file $file"
WARN_LOGFILE           =
```

### 主要な設定項目

- `WARNINGS`: 警告メッセージの有効化
- `WARN_FORMAT`: 警告メッセージのフォーマット (`$file`, `$line`, `$text` のプレースホルダーを使用)
- `WARN_LOGFILE`: 警告ログの出力先ファイル (空の場合は stderr に出力)

## 出力バッファリング

Doxygen の出力をリダイレクトする際、バッファリングによって stdout と stderr の出力順序が入れ替わる問題が発生する可能性があります。

`-b` フラグを使用することで、この問題を回避できます。

```bash
doxygen -b > out.txt 2>&1
```

本実装では、`2>&1` でストリームを結合してフィルターに渡すため、バッファリング問題は発生しません。

## 参考情報

- [Colorize Command Line Output warnings · Issue #9038 · doxygen/doxygen](https://github.com/doxygen/doxygen/issues/9038)
- [Doxygen: Configuration](https://www.doxygen.nl/manual/config.html)
- [Force line buffering · Issue #8329 · doxygen/doxygen](https://github.com/doxygen/doxygen/issues/8329)
