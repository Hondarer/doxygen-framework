# doxygen-framework

Doxygen ドキュメント生成のための設定・テンプレート・スクリプト群を提供するフレームワークです。

## 概要

本リポジトリは C プロジェクトから高品質な日本語ドキュメントを生成するために必要な設定とツールを提供します。メインプロジェクトから git submodule として参照することを前提としています。

## 機能

- Doxygen 基本設定ファイル
- Doxybook2 設定・日本語カスタムテンプレート
- XML 前処理・後処理スクリプト
- HTML および Markdown 出力対応
- 実行補助スクリプトを `bin/` 配下に集約

## クイックスタート

```bash
# ドキュメント生成
cd framework/doxyfw
make

# 生成ファイル削除
cd framework/doxyfw
make clean
```

## 詳細ドキュメント

プロジェクト構造、設定方法、開発ガイドについては [CLAUDE.md](./CLAUDE.md) をご覧ください。

## 出力形式

- HTML: 親プロジェクトの `pages/doxygen/` に生成
- Markdown: 親プロジェクトの `docs/doxybook2/` に生成

## 必要なツール

- Doxygen
- Doxybook2
- PlantUML (図表生成時)

## ライセンス

[LICENSE](./LICENSE) を参照してください。
