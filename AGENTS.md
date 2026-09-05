# AGENTS.md

## 対象

Doxygen と Doxybook2 の設定、テンプレート、補助スクリプトを提供します。

## 作業別の入口

- 実行方法や出力先を変更する場合は `makefile` と [makefile の利用方法](docs/makefile-usage.md)
- 入力を変更する場合は `Doxyfile` と利用側の `Doxyfile.part`
- 出力変換を変更する場合は `doxybook2-config.json`、`templates/preprocess.sh`、`templates/postprocess.sh`、関係する `templates/*.py`
- 警告抽出を変更する場合は `bin/extract_doxy_warnings.sh`
- 概要が必要な場合は [README.md](README.md)、文書を探す場合は [文書一覧](docs/README.md)

## 変更時の確認

生成処理を変更した場合は、[保守と検証](docs/maintenance-verification.md) の出力比較と再生成条件を確認してください。  
生成結果は変更前後で比較し、標準出力だけでなく抽出された警告も確認してください。  
文書や図を変更する場合は、同文書の「文書の表記と図」を適用してください。  
Python に日本語出力を追加する場合は「Python の日本語出力」を参照してください。
