# doxybook2 のテンプレート編集方法

doxybook2 のテンプレートの出力方法について以下にまとめます。

## doxybook2 のテンプレート出力方法

### テンプレートの生成

デフォルトテンプレートを指定したフォルダに出力 (コピー) するには、以下のコマンドを実行します。

```bash
doxybook2 --generate-templates /path/to/folder
```

このコマンドを実行すると、実行ファイル内に保存されているデフォルトテンプレートファイル群が指定したフォルダにコピーされます。  
注意点として、フォルダは事前に存在している必要があり、同名ファイルがある場合は上書きされます。

### カスタムテンプレートの使用

テンプレートを使用するには、`.tmpl` ファイル拡張子で終わるテンプレートファイルを含むフォルダを作成し、以下のように指定します。

```bash
doxybook2 --input ... --output ... --templates /path/to/folder
```

### テンプレートの種類

doxybook2 には以下のコアテンプレートがあります。

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

### テンプレートエンジン

doxybook2 は、Python Jinja ライクな C++ テンプレートエンジン「inja」を使用しており、`{% include "template_name" %}` や `{{ render("template_name", data) }}` などの構文が使用できます。
