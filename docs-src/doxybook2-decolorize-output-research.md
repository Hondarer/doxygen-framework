# Doxybook2 出力の調査結果

## 調査概要

Doxybook2 の出力形式と着色パターンについて調査を実施しました。

## 調査結果

### Doxybook2 の着色機能

Doxybook2 は [spdlog](https://github.com/gabime/spdlog) ライブラリを使用してログ出力を行っており、デフォルトで ANSI カラーコードによる着色が有効になっています。

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
| `[warning]` | `\033[1;33m` | 🟡 黄 | 太字 |
| `[error]` | `\033[1;31m` | 🔴 赤 | 太字 |
| `[critical]` | `\033[1;41m` | 赤背景 | 太字 + 赤背景 |

## Doxybook2 のコマンドラインオプション

Doxybook2 には `-q, --quiet` オプションが存在します。

```bash
doxybook2 -q -i xml/ -o output/
```

このオプションは stdout を抑制し、stderr にエラーとワーニングのみを出力します。

## 参考情報

- [GitHub - matusnovak/doxybook2: Doxygen XML to Markdown (or JSON)](https://github.com/matusnovak/doxybook2)
- [GitHub - gabime/spdlog: Fast C++ logging library](https://github.com/gabime/spdlog)
- [spdlog::sinks::ansicolor_sink Class Template Reference](https://internal.dunescience.org/doxygen/classspdlog_1_1sinks_1_1ansicolor__sink.html)
- [spdlog Custom formatting Wiki](https://github.com/gabime/spdlog/wiki/Custom-formatting)
