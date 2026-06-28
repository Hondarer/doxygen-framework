#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fix-anonymous-enums.py - 無名 enum の空 <name /> を placeholder に置換する

Doxygen は C の無名 enum (enum { val = 0, ... };) を XML に出力する際、
<memberdef kind="enum"> 直下に <name /> (空の name 要素) を生成する。
Doxybook2 はこの空 name を null 文字列として解釈し、std::string のコンストラクタが
basic_string::_M_construct null not valid で失敗してクラッシュする。

このスクリプトは XML 内の <memberdef kind="enum"> 直下の空 <name /> または
<name></name> を <name>__anonymous_enum_N__</name> に置換し、
Doxybook2 のクラッシュを防ぐ。

置換後の名前はドキュメントには表示されないため、出力 Markdown への影響はない。
(Doxybook2 は kind_file.tmpl で enum の name を見出しに使わない。)

使用方法:
    python3 fix-anonymous-enums.py <xml_directory>
例:
    python3 fix-anonymous-enums.py /tmp/doxyfw-tmp/com_internal/run.XXXXXX/xml
"""

import sys
import os
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def fix_anonymous_enums_in_file(xml_path: Path) -> int:
    """
    xml_path の XML ファイル内の <memberdef kind="enum"> 直下にある
    空の <name /> または <name></name> を一意なプレースホルダー名に置換する。

    @param[in] xml_path  対象 XML ファイルの Path オブジェクト

    @return 置換した箇所数。変更なしなら 0
    """
    with open(str(xml_path), 'r', encoding='utf-8') as f:
        content = f.read()

    # <memberdef kind="enum" ...> ... </memberdef> ブロック内の
    # 空 <name> 要素をファイル内通し番号付きプレースホルダーに置換する。
    counter = [0]

    def replace_in_enum_block(m: re.Match) -> str:
        """enum memberdef ブロック内の空 name を置換するコールバック。"""
        block = m.group(0)

        def do_replace(nm: re.Match) -> str:
            counter[0] += 1
            return '<name>__anonymous_enum_{0}__</name>'.format(counter[0])

        # <name /> と <name></name> の両形式に対応する
        block = re.sub(r'<name\s*/>', do_replace, block)
        block = re.sub(r'<name></name>', do_replace, block)
        return block

    new_content = re.sub(
        r'<memberdef\s+kind="enum"[^>]*>.*?</memberdef>',
        replace_in_enum_block,
        content,
        flags=re.DOTALL
    )

    if new_content == content:
        return 0

    with open(str(xml_path), 'w', encoding='utf-8') as f:
        f.write(new_content)

    return counter[0]


def main() -> None:
    """エントリ ポイント。"""
    if len(sys.argv) != 2:
        print('使用方法: fix-anonymous-enums.py <xml_directory>', file=sys.stderr)
        sys.exit(1)

    xml_dir = Path(sys.argv[1])
    if not xml_dir.is_dir():
        print('エラー: ディレクトリが存在しません: {0}'.format(xml_dir),
              file=sys.stderr)
        sys.exit(1)

    total = 0
    for xml_file in sorted(xml_dir.glob('*.xml')):
        count = fix_anonymous_enums_in_file(xml_file)
        if count > 0:
            print('  fix-anonymous-enums: {0} 箇所置換 in {1}'.format(
                count, xml_file.name))
            total += count

    if total > 0:
        print('fix-anonymous-enums: 合計 {0} 箇所の無名 enum 名を修正しました。'.format(
            total))
    else:
        print('fix-anonymous-enums: 無名 enum 名は見つかりませんでした。')


if __name__ == '__main__':
    main()
