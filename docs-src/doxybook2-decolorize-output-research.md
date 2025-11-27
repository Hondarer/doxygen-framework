# Doxybook2 脱色出力の調査結果

## 調査概要

Doxybook2 の出力メッセージから過剰な ANSI カラーコードを除去する機能の実装に向けて、Doxybook2 の着色パターンについて調査を実施しました。

## 調査結果

### Doxybook2 の着色機能

Doxybook2 は [spdlog](https://github.com/gabime/spdlog) ライブラリを使用してログ出力を行っており、**デフォルトで ANSI カラーコードによる着色が有効** になっています。

spdlog は 2022 年頃に Doxybook2 に統合され、以前のカスタム Log.hpp/cpp ファイルを置き換えています。

### spdlog の出力形式

spdlog のデフォルト出力形式は以下の通りです。

```text
[2022-07-05 14:25:26.685] [info] Welcome to spdlog!
[2022-07-05 14:25:26.686] [warning] Configuration file not found
[2022-07-05 14:25:26.687] [error] Failed to parse XML
```

各行の構成:
- タイムスタンプ (ミリ秒まで)
- ログレベル (`[info]`, `[warning]`, `[error]` など)
- メッセージ本文

### spdlog のデフォルト着色

spdlog の `ansicolor_sink` は、以下のデフォルトカラーマッピングを使用します。

| ログレベル | ANSI カラーコード | 表示色 | 備考 |
|------------|-------------------|--------|------|
| `[trace]` | `\033[37m` | 白 | 通常の太さ |
| `[debug]` | `\033[36m` | シアン | 通常の太さ |
| `[info]` | `\033[32m` | 🟢 緑 | 通常の太さ |
| `[warning]` | `\033[1;33m` | 🟡 黄 | **太字** |
| `[error]` | `\033[1;31m` | 🔴 赤 | **太字** |
| `[critical]` | `\033[1;41m` | 赤背景 | 太字 + 赤背景 |

### 問題点

Doxybook2 の実行時、`[info]` レベルのログが **緑色** で大量に出力され、視認性が低下します。

- Doxygen とは逆に、**着色が過剰** である
- `[info]` は情報メッセージであり、着色の必要性が低い
- `[warning]`、`[error]`、`[critical]` の太字も、強調が過剰である
- `[critical]` の赤背景も過剰であり、通常の赤文字で十分である

## 実装方針

### 目標

Doxygen 着色スクリプト (`doxygen-colorize-output.sh`) とは **逆のアプローチ** を採用します。

- **着色の削除**: 過剰な ANSI エスケープコードを除去
- **選択的処理**: `[info]` は完全脱色、`[warning]` / `[error]` / `[critical]` は太字を除去

### 処理ルール

| ログレベル | 処理内容 | 処理後の色 |
|------------|----------|------------|
| `[info]` | 全ての ANSI コードを削除 | デフォルト (着色なし) |
| `[warning]` | 太字コードを除去、黄色は維持 | 🟡 黄 (通常の太さ) |
| `[error]` | 太字コードを除去、赤色は維持 | 🔴 赤 (通常の太さ) |
| `[critical]` | 全ての ANSI コードを削除して赤色に変換 | 🔴 赤 (通常の太さ、背景なし) |
| その他 | そのまま出力 | 変更なし |

### ANSI エスケープコードのパターン

ANSI カラーコードは以下の形式で出力されます。

```text
\033[XXm          # 単一属性
\033[X;XXm        # 複数属性 (例: 1;33 = 太字 + 黄色)
\e[XXm            # \033 の省略形
```

主要なコード:
- `\033[0m`: リセット
- `\033[1m`: 太字
- `\033[31m`: 赤色
- `\033[33m`: 黄色
- `\033[1;31m`: 太字 + 赤色
- `\033[1;33m`: 太字 + 黄色

### 脱色方法

#### `[info]` 行の完全脱色

```bash
# 全ての ANSI エスケープコードを削除
sed 's/\x1b\[[0-9;]*m//g'
```

#### `[critical]` 行の完全脱色と赤色適用

```bash
# 全ての ANSI エスケープコードを削除
cleaned=$(echo "$line" | sed 's/\x1b\[[0-9;]*m//g')
# 通常の赤色で出力
echo -e "\033[0;31m${cleaned}\033[0m"
```

#### `[warning]` / `[error]` 行の太字除去

```bash
# \033[1;33m → \033[0;33m (太字 → 通常の太さ)
sed 's/\x1b\[1;/\x1b[0;/g'
```

## Doxybook2 のコマンドラインオプション

Doxybook2 には `-q, --quiet` オプションが存在します。

```bash
doxybook2 -q -i xml/ -o output/
```

このオプションは stdout を抑制し、stderr にエラーとワーニングのみを出力します。しかし、以下の理由から本実装では使用しません。

- 進捗状況が確認できなくなる
- `[info]` メッセージも有用な情報を含む場合がある
- 着色のみを制御したい (出力の抑制は不要)

## 参考情報

- [GitHub - matusnovak/doxybook2: Doxygen XML to Markdown (or JSON)](https://github.com/matusnovak/doxybook2)
- [GitHub - gabime/spdlog: Fast C++ logging library](https://github.com/gabime/spdlog)
- [spdlog::sinks::ansicolor_sink Class Template Reference](https://internal.dunescience.org/doxygen/classspdlog_1_1sinks_1_1ansicolor__sink.html)
- [spdlog Custom formatting Wiki](https://github.com/gabime/spdlog/wiki/Custom-formatting)
