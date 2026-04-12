# AGENTS.md

## 重要事項

- 自動ステージング、コミット禁止。指示があるまでステージング、コミットは行わないこと。
- 思考の断片は英語でもよいが、ユーザーに気づきを与えたり報告する際は日本語を用いること。

## 表記ルール

- 本文の文末を `：` で終わらせないこと。
- 全角括弧 `（` `）` や全角コロン `：` を使わないこと。
- 日本語と英単語の間には半角スペースを入れること。
- 特に言語指定のないコードブロックでも、` ```text ` のように形式を明示すること。
- `Markdown` は同義語より優先してこの表記を使うこと。

## 図のルール

- 図を提示する場合は原則として PlantUML を使うこと。
- `@startuml` と `caption` には同じタイトル文字列を入れ、`title` は使わないこと。
- フロー説明はアクティビティ図を優先し、シーケンス性が主題のときだけシーケンス図を使うこと。
- PlantUML が難しい場合は Mermaid を使ってよい。

## リポジトリ概要

Doxygen と Doxybook2 を組み合わせて、HTML と Markdown を生成するための設定、テンプレート、補助スクリプトを提供する repo です。

## 作業時の入口

- `makefile` - Doxygen 実行、Markdown 生成、クリーンアップの入口
- `Doxyfile` - ベースの Doxygen 設定
- `doxybook2-config.json` - Doxybook2 設定
- `templates/` - 前処理、後処理、テンプレート、補助 Python スクリプト
- `bin/` - 入力フィルタ、警告整形、警告抽出
- `docs/` - テンプレートや出力仕様に関する補助ドキュメント

## 主要コマンド

```bash
make
CATEGORY=calc make
make clean
```

## 注意点

- `makefile` は `CATEGORY` と `Doxyfile.part` の有無で入力や出力先を切り替える。パス変更時は先頭の変数定義を確認すること。
- `templates/preprocess.sh`、`templates/postprocess.sh`、`templates/*.py` は出力構造に直結するため、単独ではなく連鎖する処理全体で確認すること。
- 警告抽出は `bin/extract_doxy_warnings.sh` に依存するため、標準出力の見た目だけで完了扱いにしないこと。
