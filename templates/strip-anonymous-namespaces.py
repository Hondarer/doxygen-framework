#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
strip-anonymous-namespaces.py - 無名名前空間の compound を XML から除去する

Doxygen は EXTRACT_ANON_NSPACES = NO の設定でも、C++ の無名名前空間
(namespace { ... }) に対して kind="namespace" の compounddef と index.xml の
エントリを出力する。このとき、ファイル スコープの無名名前空間は
<compoundname></compoundname> (空要素) となる。
Doxybook2 はこの空要素を null 文字列として解釈し、std::string のコンストラクタが
basic_string::_M_construct null not valid で失敗して compound の読み込みを中断する。

入れ子の無名名前空間 (名前付き名前空間の内側にある無名名前空間) は compoundname が
親名前空間名で出力されるためクラッシュはしないが、親と同名の別 compound として
扱われ、名前空間一覧に重複エントリと存在しないファイルへのリンクが生成される。

EXTRACT_ANON_NSPACES = NO は無名名前空間を文書化しない意思表示であるため、
このスクリプトは該当 compound を XML 段階で除去し、Doxybook2 へ渡さない。
EXTRACT_ANON_NSPACES = YES の構成では Doxygen が実名 (anonymous_namespace{file.cc})
を付けるため、このスクリプトは何も除去しない。

無名名前空間の判定には index.xml の <name> を用いる。Doxygen は無名名前空間の名前を
@<8 進数字列> 形式で出力するため、compoundname の内容に依らず確実に判定できる。

使用方法:
    python3 strip-anonymous-namespaces.py <xml_directory>
例:
    python3 strip-anonymous-namespaces.py /tmp/doxyfw-tmp/com_util_internal/run.XXXXXX/xml
"""

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def collect_anonymous_namespace_refids(index_path: Path) -> list:
    """
    index.xml から無名名前空間 compound の refid を収集する。

    @param[in] index_path  index.xml の Path オブジェクト

    @return 無名名前空間 compound の refid のリスト。該当なしなら空リスト
    """
    content = index_path.read_text(encoding='utf-8')

    refids = []
    pattern = re.compile(
        r'<compound\s+refid="([^"]+)"\s+kind="namespace"\s*>\s*<name>([^<]*)</name>'
    )
    for match in pattern.finditer(content):
        if '@' in match.group(2):
            refids.append(match.group(1))

    return refids


def remove_index_entries(index_path: Path, refids: list) -> int:
    """
    index.xml から指定 refid の <compound> ブロックを配下の <member> ごと削除する。

    @param[in] index_path  index.xml の Path オブジェクト
    @param[in] refids      削除対象 compound の refid のリスト

    @return 削除した <compound> ブロックの数
    """
    content = index_path.read_text(encoding='utf-8')
    removed = 0

    for refid in refids:
        # <compound refid="..." ...> から対応する </compound> までをまとめて削除する。
        # index.xml の compound はネストしないため、最短一致で対応が取れる。
        pattern = re.compile(
            r'[ \t]*<compound\s+refid="{0}"[^>]*>.*?</compound>\n?'.format(
                re.escape(refid)),
            flags=re.DOTALL
        )
        content, count = pattern.subn('', content)
        removed += count

    index_path.write_text(content, encoding='utf-8')

    return removed


def remove_references_in_file(xml_path: Path, refids: list) -> int:
    """
    xml_path の XML から、指定 refid への参照を除去する。

    <innernamespace> は要素ごと削除し、<ref> はタグのみを外してテキストを残す。

    @param[in] xml_path  対象 XML ファイルの Path オブジェクト
    @param[in] refids    除去対象 compound の refid のリスト

    @return 除去した参照の数。変更なしなら 0
    """
    content = xml_path.read_text(encoding='utf-8')
    original = content
    removed = 0

    for refid in refids:
        escaped = re.escape(refid)

        # 親ファイル / 親名前空間からの <innernamespace> 参照を要素ごと削除する。
        pattern = re.compile(
            r'[ \t]*<innernamespace\s+refid="{0}"[^>]*>.*?</innernamespace>\n?'.format(
                escaped),
            flags=re.DOTALL
        )
        content, count = pattern.subn('', content)
        removed += count

        # 本文中の <ref> は、リンク先を失うためタグを外してテキストのみを残す。
        # refid は compound 自身とその配下メンバーの双方を前方一致で対象にする。
        pattern = re.compile(
            r'<ref\s+refid="{0}[^"]*"[^>]*>(.*?)</ref>'.format(escaped),
            flags=re.DOTALL
        )
        content, count = pattern.subn(r'\1', content)
        removed += count

    if content == original:
        return 0

    xml_path.write_text(content, encoding='utf-8')

    return removed


def main() -> None:
    """エントリ ポイント。"""
    if len(sys.argv) != 2:
        print('使用方法: strip-anonymous-namespaces.py <xml_directory>',
              file=sys.stderr)
        sys.exit(1)

    xml_dir = Path(sys.argv[1])
    if not xml_dir.is_dir():
        print('エラー: ディレクトリが存在しません: {0}'.format(xml_dir),
              file=sys.stderr)
        sys.exit(1)

    index_path = xml_dir / 'index.xml'
    if not index_path.is_file():
        print('strip-anonymous-namespaces: index.xml がないため処理をスキップします。')
        return

    refids = collect_anonymous_namespace_refids(index_path)
    if not refids:
        print('strip-anonymous-namespaces: 無名名前空間は見つかりませんでした。')
        return

    remove_index_entries(index_path, refids)

    removed_files = 0
    for refid in refids:
        compound_path = xml_dir / '{0}.xml'.format(refid)
        if compound_path.is_file():
            compound_path.unlink()
            removed_files += 1

    removed_refs = 0
    for xml_file in sorted(xml_dir.glob('*.xml')):
        removed_refs += remove_references_in_file(xml_file, refids)

    print('  strip-anonymous-namespaces: compound {0} 件を除去 (XML ファイル {1} 件削除)'.format(
        len(refids), removed_files))
    if removed_refs > 0:
        print('  strip-anonymous-namespaces: 残存参照 {0} 件を除去'.format(removed_refs))

    print('strip-anonymous-namespaces: 合計 {0} 件の無名名前空間を除去しました。'.format(
        len(refids)))


if __name__ == '__main__':
    main()
