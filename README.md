# doxygen-framework

Doxygen と Doxybook2 を使って HTML と Markdown を生成するための設定、テンプレート、スクリプトを提供する repo です。

## 概要

この repo には以下が含まれます。

- Doxygen のベース設定
- Doxybook2 の設定とテンプレート
- XML の前処理と Markdown の後処理
- 警告抽出や出力整形の補助スクリプト

## クイックスタート

```bash
make
make clean
```

カテゴリ単位で実行する場合は、`CATEGORY` を指定します。

```bash
CATEGORY=calc make
```

## 主なファイル

- `makefile` - 生成処理の入口
- `Doxyfile` - Doxygen のベース設定
- `doxybook2-config.json` - Doxybook2 設定
- `templates/` - テンプレートと前後処理スクリプト
- `bin/` - 警告抽出や出力整形の補助スクリプト

## 詳細情報

作業ルールと補足は [AGENTS.md](./AGENTS.md)、補助ドキュメントは `docs/` を参照してください。

## 必要なツール

- Doxygen
- Doxybook2
- Python 3
- PlantUML

## ライセンス

[LICENSE](./LICENSE) を参照してください。
