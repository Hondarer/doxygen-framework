# doxybook2 のテンプレート編集方法

doxybook2 のテンプレートの出力方法について以下にまとめます。

## doxybook2 のテンプレート出力方法

### テンプレートの生成

デフォルト テンプレートを指定したフォルダーに出力 (コピー) するには、以下のコマンドを実行します。

```bash
doxybook2 --generate-templates /path/to/folder
```

このコマンドを実行すると、実行ファイル内に保存されているデフォルト テンプレート ファイル群が指定したフォルダーにコピーされます。  
注意点として、フォルダーは事前に存在している必要があり、同名ファイルがある場合は上書きされます。

### カスタム テンプレートの使用

テンプレートを使用するには、`.tmpl` ファイル拡張子で終わるテンプレート ファイルを含むフォルダーを作成し、以下のように指定します。

```bash
doxybook2 --input ... --output ... --templates /path/to/folder
```

### テンプレートの種類

doxybook2 には以下のコア テンプレートがあります。

**主要テンプレート (設定ファイルで定義):**

- `templateIndexExamples`
- `templateIndexFiles`
- `templateIndexGroups`
- `templateIndexNamespaces`
- `templateIndexRelatedPages`
- `templateKindClass`
- `templateKindExample`
- `templateKindFile`
- `templateKindGroup`
- `templateKindDir`
- `templateKindNamespace`
- `templateKindPage`
- `templateKindUnion`
- `templateKindInterface`
- `templateKindStruct`

**依存テンプレート:**

- `meta`
- `header`
- `footer`
- `index`
- `breadcrumbs`
- `member_details`
- `mode_details`
- `class_members_tables`
- `class_members_inherited_tables`
- `class_members_details`

### テンプレートのデバッグ

```bash
doxybook2 --debug-templates ...
```

このオプションを使用すると、各テンプレートに対応する JSON ファイル (*.md.json) が生成され、テンプレートに渡されるデータ構造を確認できます。

#### テンプレートの中で利用可能なフィールドを確認する方法

```text
**利用可能フィールド:**
{% for key, value in param -%}
- `{{key}}`: "{{value}}"
{% endfor %}s
```

### テンプレート エンジン

doxybook2 は、Python Jinja ライクな C++ テンプレート エンジン「inja」を使用しており、`{% include "template_name" %}` や `{{ render("template_name", data) }}` などの構文が使用できます。

## 出力規約と制約

### ページ構成の規約 (## 概要 セクション)

doxybook2 出力の各ページ (Modules / Files / Classes / Namespaces / Examples / Pages) は、H1 直下に出力する brief と details を `## 概要` セクションとして出力します。

- 出力条件は「H1 直下に出力される内容があること」です。brief も details もないページには `## 概要` を出しません。
- 例外として、Classes ページは構造体定義のコード ブロックのみでも `## 概要` を出します (H1 直下に内容があれば概要に含める、が原則)。
- 実装は `templates/kind_*.tmpl` (kind_file / kind_nonclass / kind_group / kind_class / kind_example / kind_page) です。グループが kind_group と kind_nonclass のどちらにマップされるかは確定していないため、両者を同一構造に維持します。

### postprocess.sh の include 展開は 1 段のみ

`templates/postprocess.sh` の `!include` 解決はリーフ前提の 1 段のみです。
include したファイル内にさらに `!include` があってもネストは解決されず、その後の dunder 変換 (`__` を `&#95;&#95;` にする処理) でファイル名が壊れ、リテラルの `!include` 行として最終出力に露出します。

`inject-groups.py` のような注入スクリプトが挿入する内容に `!include` が含まれ得る場合は、postprocess の 1 段解決に頼らず、inject 段階でインライン展開するか、リーフであることを保証してください (既存例は `inject-groups.py` の `resolve_classes_includes()`)。

検証は次の grep が 0 件であることで行います。

```bash
grep -rn "^!include \|!include Classes/" app/*/docs
```
