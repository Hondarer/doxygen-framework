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

`CATEGORY` 指定時の Doxybook2 出力先は `app/<CATEGORY>/docs/doxybook2/` です。
`CATEGORY` 未指定時は従来どおり `docs/doxybook2/` を使用します。

`CATEGORY` 指定時は `app/<CATEGORY>/prod/Doxyfile.part` にコメントディレクティブを追加すると、Doxybook2 の Markdown 出力ディレクトリ名だけを変更できます。

```text
# DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME = api
```

この例では Markdown 出力先が `app/<CATEGORY>/docs/api/` になります。Doxygen HTML 出力先は変わらず `pages/doxygen/<CATEGORY>/` です。

値を空にした場合は未指定として扱われ、既定の `doxybook2` を使用します。
値を指定する場合はディレクトリ名 1 要素だけです。絶対パス、`.`、`..`、`/`、`\` を含む値は使用できません。

カスタム名を使用する app では、`docs/README.md` 内の Doxybook2 へのリンクと `\toc exclude` の対象も同じディレクトリ名に更新してください。

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
