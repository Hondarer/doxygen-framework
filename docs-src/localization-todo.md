# テンプレート 日本語ローカライズ TODO

`doxyfw/templates/` 内の `.tmpl` ファイルに残存する英語文字列の一覧です。

----

## 対応済み

### class_members_details.tmpl ✅

セクション見出し・メンバー種別プレフィックスをすべて日本語化済み。

| 旧英語 | 新日本語 |
|---|---|
| `## Public Types Documentation` | `## 公開型ドキュメント` |
| `## Protected Types Documentation` | `## プロテクト型ドキュメント` |
| `## Public Slots Documentation` | `## 公開スロットドキュメント` |
| `## Protected Slots Documentation` | `## プロテクトスロットドキュメント` |
| `## Public Signals Documentation` | `## 公開シグナルドキュメント` |
| `## Protected Signals Documentation` | `## プロテクトシグナルドキュメント` |
| `## Public Events Documentation` | `## 公開イベントドキュメント` |
| `## Protected Events Documentation` | `## プロテクトイベントドキュメント` |
| `## Enum Constants Documentation` | `## 列挙定数ドキュメント` |
| `## Public Functions Documentation` | `## 公開関数ドキュメント` |
| `## Protected Functions Documentation` | `## プロテクト関数ドキュメント` |
| `## Public Property Documentation` | `## 公開プロパティドキュメント` |
| `## Protected Property Documentation` | `## プロテクトプロパティドキュメント` |
| `## Protected Attributes Documentation` | `## プロテクト属性ドキュメント` |
| `## Friends` | `## フレンド` |
| `### function {{name}}` | `### 関数 {{name}}` |
| `### property {{name}}` | `### プロパティ {{name}}` |
| `### slot {{name}}` | `### スロット {{name}}` |
| `### signal {{name}}` | `### シグナル {{name}}` |
| `### event {{name}}` | `### イベント {{name}}` |
| `### enumvalue {{name}}` | `### 列挙定数 {{name}}` |
| `### variable {{name}}` | `### 変数 {{name}}` |
| `### enum {{name}}` | `### 列挙型 {{name}}` |
| `### typedef {{name}}` | `### 型定義 {{name}}` |
| `### using {{name}}` | `### 型エイリアス {{name}}` |

### class_members_tables.tmpl ✅

> 注意: `kind_class.tmpl` から include されておらず、現状は出力に現れない。

セクション見出し・テーブルヘッダーをすべて日本語化済み。

| 旧英語 | 新日本語 |
|---|---|
| `## Public Classes` | `## 公開クラス` |
| `## Protected Classes` | `## プロテクトクラス` |
| `## Public Types` | `## 公開型` |
| `## Protected Types` | `## プロテクト型` |
| `## Public Slots` | `## 公開スロット` |
| `## Protected Slots` | `## プロテクトスロット` |
| `## Public Signals` | `## 公開シグナル` |
| `## Protected Signals` | `## プロテクトシグナル` |
| `## Public Events` | `## 公開イベント` |
| `## Protected Events` | `## プロテクトイベント` |
| `## Enum Constants` | `## 列挙定数` |
| `\| Enum constants \| Description \|` | `\| 列挙定数 \| 説明 \|` |
| `## Public Functions` | `## 公開関数` |
| `## Protected Functions` | `## プロテクト関数` |
| `## Public Properties` | `## 公開プロパティ` |
| `## Protected Properties` | `## プロテクトプロパティ` |
| `## Public Attributes` | `## 公開属性` |
| `## Protected Attributes` | `## プロテクト属性` |
| `## Friends` | `## フレンド` |

### class_members_inherited_tables.tmpl ✅

> 注意: `kind_class.tmpl` から include されておらず、現状は出力に現れない。

パターン `[アクセス修飾子] [カテゴリ] inherited from [クラス名]` を
`[クラス名] から継承した[カテゴリ]` 形式に変更済み。

### member_details.tmpl ✅

| 旧英語 | 新日本語 |
|---|---|
| `\| Enumerator \| Value \| Description \|` | `\| 列挙子 \| 値 \| 説明 \|` |

### header.tmpl (title 条件) ✅

`title` 変数の条件分岐に `Namespaces` と `Classes` を追加済み。

| 旧英語 | 新日本語 |
|---|---|
| `# Namespaces` | `# 名前空間の一覧` |
| `# Classes` | `# クラスの一覧` |

----

## 未対応

### header.tmpl

| 行 | 現在の英語 | 備考 |
|---|---|---|
| 15 | `# {{name}} {{title(kind)}} Reference` | `title(kind)` が英語 (例: `Namespace Reference`, `Class Reference`) を返す。doxybook2 の組み込み関数のため template 側での対応が困難。 |

### breadcrumbs.tmpl

| 行 | 現在の英語 |
|---|---|
| 2 | `**Module:**` |

### nonclass_members_tables.tmpl

> 注意: `kind_nonclass.tmpl` から include されておらず、現状は出力に現れない。

| 行 | 現在の英語 |
|---|---|
| 30 | `## Packages` / `## Namespaces` (言語分岐。両方英語のまま) |
| 63 | `## Slots` |
| 86 | `## Signals` |
| 132 | `## Attributes` |
