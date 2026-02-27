# テンプレート 日本語ローカライズ TODO

`doxyfw/templates/` 内の `.tmpl` ファイルに残存する英語文字列の一覧です。

----

## class_members_tables.tmpl

セクション見出しが未翻訳。

| 行 | 現在の英語 |
|---|---|
| 1 | `## Public Classes` |
| 9 | `## Protected Classes` |
| 17 | `## Public Types` |
| 34 | `## Protected Types` |
| 51 | `## Public Slots` |
| 74 | `## Protected Slots` |
| 97 | `## Public Signals` |
| 120 | `## Protected Signals` |
| 143 | `## Public Events` |
| 166 | `## Protected Events` |
| 189 | `## Enum Constants` |
| 191 | テーブルヘッダー `\| Enum constants \| Description \|` |
| 197 | `## Public Functions` |
| 220 | `## Protected Functions` |
| 243 | `## Public Properties` |
| 252 | `## Protected Properties` |
| 261 | `## Public Attributes` |
| 270 | `## Protected Attributes` |
| 279 | `## Friends` |

----

## class_members_details.tmpl

詳細セクション見出しが未翻訳。

| 行 | 現在の英語 |
|---|---|
| 3 | `## Public Types Documentation` |
| 10 | `## Protected Types Documentation` |
| 17 | `## Public Slots Documentation` |
| 24 | `## Protected Slots Documentation` |
| 31 | `## Public Signals Documentation` |
| 38 | `## Protected Signals Documentation` |
| 45 | `## Public Events Documentation` |
| 52 | `## Protected Events Documentation` |
| 59 | `## Enum Constants Documentation` |
| 66 | `## Public Functions Documentation` |
| 73 | `## Protected Functions Documentation` |
| 80 | `## Public Property Documentation` |
| 87 | `## Protected Property Documentation` |
| 101 | `## Protected Attributes Documentation` |
| 108 | `## Friends` |

----

## class_members_inherited_tables.tmpl

継承元ラベルがすべて英語。パターンは `**[アクセス修飾子] [カテゴリ] inherited from [クラス名]**`。

| 行 | 現在の英語 |
|---|---|
| 3 | `Public Classes inherited from` |
| 12 | `Protected Classes inherited from` |
| 21 | `Public Types inherited from` |
| 39 | `Protected Types inherited from` |
| 57 | `Public Slots inherited from` |
| 81 | `Protected Slots inherited from` |
| 105 | `Public Signals inherited from` |
| 129 | `Protected Signals inherited from` |
| 153 | `Public Events inherited from` |
| 177 | `Protected Events inherited from` |
| 201 | `Public Functions inherited from` |
| 225 | `Protected Functions inherited from` |
| 249 | `Public Properties inherited from` |
| 259 | `Protected Properties inherited from` |
| 269 | `Public Attributes inherited from` |
| 279 | `Protected Attributes inherited from` |
| 288 | `Friends inherited from` |

----

## nonclass_members_tables.tmpl

> 注意: L1 のコメント「上位テンプレートで不活化しているため、呼び出されない」により、
> 現状では出力に現れない。修正の要否を確認すること。

| 行 | 現在の英語 |
|---|---|
| 30 | `## Packages` / `## Namespaces` (言語分岐。両方英語のまま) |
| 63 | `## Slots` |
| 86 | `## Signals` |
| 132 | `## Attributes` |

----

## header.tmpl

| 行 | 現在の英語 | 備考 |
|---|---|---|
| 15 | `# {{name}} {{title(kind)}} Reference` | 末尾の `Reference` が英語 |

----

## breadcrumbs.tmpl

| 行 | 現在の英語 |
|---|---|
| 2 | `**Module:**` |
