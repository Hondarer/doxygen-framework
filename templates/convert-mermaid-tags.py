#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
convert-mermaid-tags.py - Doxygen XML の <mermaid> タグを Markdown のコード フェンスへ変換する

Doxybook2 v1.6.1 は <mermaid> タグを認識せず、警告を出してタグを取り除く。
このため、Doxybook2 へ渡す前に <mermaid> タグを Mermaid のコード フェンスと
Figure: キャプション行のテキストへ置き換える。

<mermaid> タグの発生源は次の 3 つで、いずれも同じ規則で変換する。

- Doxygen コメントの @mermaid "キャプション" ... @endmermaid
- extract-graphs.py が挿入する自動生成グラフ
- Doxygen の入力となる Markdown の ```mermaid コード フェンス (caption 属性なし)

使用方法: python3 convert-mermaid-tags.py <xml_directory>
"""

import html
import re
import sys
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

MERMAID_TAG_PATTERN = re.compile(r'<mermaid([^>]*)>(.*?)</mermaid>', re.DOTALL)
CAPTION_ATTR_PATTERN = re.compile(r'\bcaption="([^"]*)"')

# Figure: 行はコード フェンスの外にあり、Markdown の本文として解釈される。
# 名前に含まれる記号 (Foo<T>、operator*、operator[] など) を文字どおりに表示するため、
# Markdown で特別な意味を持つ記号を数値文字参照へ変換する。
# バックスラッシュによるエスケープは使用しない。\[ が postprocess.sh の LaTeX ブロック数式の
# 分離処理に一致し、キャプション行が分断されるためである。
# __ と $ は postprocess.sh がコード フェンス外の本文に対して変換するため、ここでは変換しない。
CAPTION_ESCAPE_CHARS = '\\`*<>[]~'
CAPTION_ESCAPE_TABLE = {ord(char): f'&#{ord(char)};' for char in CAPTION_ESCAPE_CHARS}


def escape_caption(caption):
    """キャプション内の Markdown の記号を数値文字参照へ変換する。"""
    return caption.translate(CAPTION_ESCAPE_TABLE)


def convert_tag(match):
    """1 つの <mermaid> タグを、コード フェンスと Figure: 行のテキストへ変換する。"""
    attrs = match.group(1)
    body = match.group(2)

    caption = ''
    caption_match = CAPTION_ATTR_PATTERN.search(attrs)
    if caption_match:
        caption = html.unescape(caption_match.group(1)).strip()

    # 本文の XML 実体参照 (&gt; など) は Doxybook2 が復号するため、ここでは復号しない。
    lines = body.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    dedented_body = textwrap.dedent('\n'.join(line.rstrip() for line in lines))

    # 前後に空行を置き、隣接するテキストと行が連結しないようにする。
    converted = f'\n\n```mermaid\n{dedented_body}\n```\n\n'
    if caption:
        # 数値文字参照の & は XML のテキストとしてエスケープする (&#42; は XML 上で &amp;#42;)。
        # Doxybook2 が復号し、Markdown へ &#42; を出力する。
        converted += f'Figure: {xml_escape(escape_caption(caption))}\n\n'
    return converted


def convert_text(xml_text):
    """XML テキスト中のすべての <mermaid> タグを変換する。"""
    return MERMAID_TAG_PATTERN.sub(convert_tag, xml_text)


def convert_file(xml_path):
    """XML ファイルを変換する。変更があった場合に True を返す。"""
    with open(xml_path, 'r', encoding='utf-8', newline='') as xml_file:
        original = xml_file.read()
    if '<mermaid' not in original:
        return False
    converted = convert_text(original)
    if converted == original:
        return False
    with open(xml_path, 'w', encoding='utf-8', newline='\n') as xml_file:
        xml_file.write(converted)
    return True


def main():
    if len(sys.argv) != 2:
        print('使用方法: convert-mermaid-tags.py <xml_directory>', file=sys.stderr)
        return 1

    xml_dir = Path(sys.argv[1])
    if not xml_dir.is_dir():
        print(f'エラー: 指定されたフォルダーが見つかりません: {xml_dir}', file=sys.stderr)
        return 1

    for xml_path in sorted(xml_dir.rglob('*')):
        if xml_path.is_file() and xml_path.suffix.lower() == '.xml':
            convert_file(xml_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
