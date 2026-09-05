# AGENTS.md

## 対象範囲

この文書は、`framework/doxyfw/` 配下の作業に適用します。  
以降の規則は、この範囲に限って上位の規則へ追加されます。

## 表記ルール

- 本文の文末を `：` で終わらせないでください。
- 全角括弧 `（` `）` や全角コロン `：` を使わないでください。
- 日本語と英単語の間には半角スペースを記載してください。
- 特に言語指定のないコード ブロックでも、` ```text ` のように形式を明示してください。
- `Markdown` は同義語より優先してこの表記を使用してください。

## 図のルール

- 図を提示する場合は原則として PlantUML を使用してください。
- `@startuml` と `caption` には同じタイトル文字列を記載し、`title` は使用しないでください。
- フロー説明はアクティビティ図を優先し、シーケンス性が主題のときだけシーケンス図を使用してください。
- PlantUML が難しい場合は Mermaid を使ってよい。

## リポジトリ概要

Doxygen と Doxybook2 を組み合わせて、HTML と Markdown を生成するための設定、テンプレート、補助スクリプトを提供するリポジトリです。

## 必須参照

- [README.md](README.md)
- [文書一覧](docs/README.md)

## 作業時の入口

- `makefile` - Doxygen 実行、Markdown 生成、クリーンアップの入口
- `Doxyfile` - ベースの Doxygen 設定
- `doxybook2-config.json` - Doxybook2 設定
- `templates/` - 前処理、後処理、テンプレート、補助 Python スクリプト
- `bin/` - 入力フィルター、警告整形、警告抽出
- [docs/README.md](docs/README.md) - テンプレートや出力仕様に関する補助ドキュメントの入口

## 主要コマンド

```bash
make
CATEGORY=example make
make clean
```

## 注意点

- `makefile` は `CATEGORY` と `Doxyfile.part` の有無で入力や出力先を切り替えます。パスを変更する場合は先頭の変数定義を確認してください。
- `templates/preprocess.sh`、`templates/postprocess.sh`、`templates/*.py` は出力構造に直結するため、連鎖する処理全体を確認してください。
- テンプレート、postprocess、`templates/*.py` の変更検証は「変更前の生成済み Markdown を退避し、再生成後に `diff -ru` で突き合わせ、期待した差分だけであること」を確認する方式で行うこと。生成物 (`app/*/docs/doxybook2*`) は各アプリの .gitignore 対象であり、git diff では検証できません。テンプレート変更はワークスペース側 `app/*/make_doxy.stamp` のシグネチャ比較に含まれないため、`rm -f app/*/make_doxy.stamp` してから再生成して強制実行すること (`make clean` は不要)。
- 警告抽出は `bin/extract_doxy_warnings.sh` に依存するため、標準出力の表示だけで完了と判断しないでください。
- `templates/*.py` で日本語を出力するときは、モジュール レベルに以下を追加してください。  
  Windows のデフォルト `sys.stdout.encoding` は `cp932` であり、出力が文字化けします。

  ```python
  sys.stdout.reconfigure(encoding="utf-8")
  sys.stderr.reconfigure(encoding="utf-8")
  ```
