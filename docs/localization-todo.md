# テンプレート 日本語ローカライズ TODO

`framework/doxyfw/templates/` 内の `.tmpl` ファイルに残存する英語文字列の一覧です。

## 未対応

### header.tmpl

Table: header.tmpl のローカライズ未対応箇所一覧

| 行 | 現在の英語 | 備考 |
|---|---|---|
| 15 | `# {{name}} {{title(kind)}} Reference` | `title(kind)` が英語 (例: `Namespace Reference`, `Class Reference`) を返す。doxybook2 の組み込み関数のため template 側での対応が困難。 |

### breadcrumbs.tmpl

Table: breadcrumbs.tmpl のローカライズ未対応箇所一覧

| 行 | 現在の英語 |
|---|---|
| 2 | `**Module:**` |

### nonclass_members_tables.tmpl

> [!NOTE]
> `kind_nonclass.tmpl` から include されておらず、現状は出力に現れません。

Table: nonclass_members_tables.tmpl のローカライズ未対応箇所一覧

| 行 | 現在の英語 |
|---|---|
| 30 | `## Packages` / `## Namespaces` (言語分岐。両方英語のまま) |
| 63 | `## Slots` |
| 86 | `## Signals` |
| 132 | `## Attributes` |
