#!/usr/bin/env python3
import sys
import re

# 標準出力を UTF-8 に固定する
# Windows 環境では sys.stdout のエンコーディングが ANSI のため、
# この措置を行わないと文字化けしてしまう
try:
    # Python 3.7+
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    # Python 3.6 など
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    content = f.read()

# ```plantuml と、それに対応する ``` を削除
# Pages の Markdown でコードフェンスを利用すると、Doxygen の出力結果に
# コードフェンスが残ってしまう。
# PlantUML のコードフェンスだけを削除し、他のコードブロックは残す。
# Markdown ファイルでは通常のコードフェンス記法を使えるため、エディタでプレビューできる。
# 一方、Doxygen に渡される際にはコードフェンスが削除されるため、HTML 出力も正常に行える。
pattern = r'```plantuml\n(.*?)\n```'
content = re.sub(pattern, r'\1', content, flags=re.DOTALL)

print(content)
