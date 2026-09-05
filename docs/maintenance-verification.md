# Doxygen 生成処理の保守と検証

## 出力変換を変更する場合

テンプレート、`postprocess`、`templates/*.py` の出力変換を変更する場合は、対象の変更前生成 Markdown を退避します。  
同じ入力から再生成した結果を `diff -ru` などで比較し、意図した差分だけであることを確認します。  
生成物は Git 管理対象外のため、`git diff` だけでは比較できません。

テンプレート変更が利用側の `make_doxy.stamp` のシグネチャに含まれない場合は、対象 app のスタンプを除いて再生成します。  
ワークスペースと対象 app の絶対パスを確認し、対象外のスタンプを削除しません。  
この場合に `make clean` は不要です。  
実行方法は [makefile の利用方法](makefile-usage.md) を参照してください。

## Python の日本語出力

Windows で日本語を出力する処理を追加する場合は、既存スクリプトの stdout / stderr の UTF-8 設定に合わせます。  
出力の文字化けが発生した場合は実行環境のエンコーディングも確認します。

```python
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
```

## 文書の表記と図

本文の文末を全角コロンで終わらせず、括弧とコロンは半角を使います。  
日本語と英単語の間には半角スペースを置き、コード ブロックには `text` などの形式を明示します。  
`Markdown` の表記を優先します。

図を追加または変更する場合は PlantUML を基本とします。  
`@startuml` と `caption` には同じタイトル文字列を記載し、`title` は使用しません。  
フロー説明はアクティビティ図、シーケンス性が主題の場合はシーケンス図を使います。  
PlantUML で表現しにくい場合は Mermaid を使えます。
