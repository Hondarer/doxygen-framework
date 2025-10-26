# デバッグ方法

## テンプレートの中で利用可能なフィールドを確認する方法

```text
**利用可能フィールド:**
{% for key, value in param -%}
- `{{key}}`: "{{value}}"
{% endfor %}
```
