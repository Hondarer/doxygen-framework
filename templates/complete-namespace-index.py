#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
complete-namespace-index.py - 名前空間目次の欠落した親エントリを補完する

Doxybook2 は、文書化されたメンバーを持たない名前空間に対しても H1 見出しのみの
空ページを生成する。postprocess.sh はこの空ページを削除し、index_namespaces.md の
該当エントリ行も削除するが、子名前空間のエントリ行は残るため、親のない字下げ行だけが
取り残される。

例として、com_util 名前空間はメンバーをすべて子の com_util::regex_detail に持つため、
Namespaces/namespacecom__util.md が空ページとして削除され、目次は以下の状態になる。

    ::: {.collapsible-list open-level=-1}
        - 📄 [com_util::regex_detail](namespacecom__util_1_1regex__detail.md)
    :::

このスクリプトは、:: 修飾された名前から祖先の名前空間を求め、目次に現れない祖先を
リンクのない見出しとして補完する。個別ページは生成しない。

    ::: {.collapsible-list open-level=-1}
    - 📄 com_util
        - 📄 [com_util::regex_detail](namespacecom__util_1_1regex__detail.md)
    :::

アイコンは index.tmpl が名前空間に用いる 📄 で統一する。個別ページの有無で
アイコンの形を変えず、リンクの有無だけで区別する。
展開可能リストのトグルは子要素の有無で決まりリンクの有無に依存しないため、
リンクのない親行でも展開動作は損なわれない。
see: framework/docsfw/docs/collapsible-list.md

使用方法:
    python3 complete-namespace-index.py <markdown_directory>
例:
    python3 complete-namespace-index.py app/com_util/docs/doxybook2_internal
"""

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 名前空間の階層区切り
NAMESPACE_SEPARATOR = '::'

# 1 階層あたりの字下げ幅。postprocess.sh のリスト正規化と揃える。
INDENT_WIDTH = 4

# 名前空間のアイコン。index.tmpl と揃え、個別ページの有無に依らず 📄 で統一する。
NAMESPACE_ICON = '📄'

# 正規化後の目次エントリ行。リンクありとリンクなしの双方を受ける。
ENTRY_PATTERN = re.compile(
    r'^(?P<indent>[ ]*)- (?P<icon>📁|📄) '
    r'(?:\[(?P<linked_title>.+?)\]\((?P<url>.+?)\)|(?P<plain_title>.+?))'
    r'[ ]*$'
)


def parse_entry(line: str):
    """
    目次の 1 行を解析し、字下げ幅と表示名を返す。

    @param[in] line  対象の行 (改行を含まない)

    @return (字下げ幅, 表示名) のタプル。エントリ行でなければ None
    """
    match = ENTRY_PATTERN.match(line)
    if match is None:
        return None

    title = match.group('linked_title')
    if title is None:
        title = match.group('plain_title')

    return (len(match.group('indent')), title)


def ancestors_of(name: str) -> list:
    """
    :: 修飾された名前から、浅い順に祖先の名前を列挙する。

    @param[in] name  名前空間の表示名 (例: a::b::c)

    @return 祖先名のリスト (例: ["a", "a::b"])。祖先がなければ空リスト
    """
    parts = name.split(NAMESPACE_SEPARATOR)

    return [
        NAMESPACE_SEPARATOR.join(parts[:count])
        for count in range(1, len(parts))
    ]


def complete_namespace_index(index_path: Path) -> int:
    """
    index_namespaces.md に欠落した親名前空間のエントリ行を補完する。

    @param[in] index_path  index_namespaces.md の Path オブジェクト

    @return 補完した行数。変更なしなら 0
    """
    lines = index_path.read_text(encoding='utf-8').split('\n')

    known_names = set()
    for line in lines:
        entry = parse_entry(line)
        if entry is not None:
            known_names.add(entry[1])

    completed_lines = []
    inserted = 0

    for line in lines:
        entry = parse_entry(line)
        if entry is None:
            completed_lines.append(line)
            continue

        indent, name = entry
        depth = name.count(NAMESPACE_SEPARATOR) + 1

        for ancestor in ancestors_of(name):
            if ancestor in known_names:
                continue

            # 祖先の字下げは、子孫行の実際の字下げから階層差の分だけ戻して求める。
            # Doxybook2 の入れ子構造に依存せず、既存行との整合が取れる。
            ancestor_depth = ancestor.count(NAMESPACE_SEPARATOR) + 1
            ancestor_indent = indent - (depth - ancestor_depth) * INDENT_WIDTH
            if ancestor_indent < 0:
                ancestor_indent = 0

            completed_lines.append('{0}- {1} {2}'.format(
                ' ' * ancestor_indent, NAMESPACE_ICON, ancestor))
            # 補完済みの名前を記録し、後続の兄弟行で重複挿入しないようにする
            known_names.add(ancestor)
            inserted += 1

        completed_lines.append(line)

    if inserted == 0:
        return 0

    index_path.write_text('\n'.join(completed_lines), encoding='utf-8')

    return inserted


def main() -> None:
    """エントリ ポイント。"""
    if len(sys.argv) != 2:
        print('使用方法: complete-namespace-index.py <markdown_directory>',
              file=sys.stderr)
        sys.exit(1)

    markdown_dir = Path(sys.argv[1])
    if not markdown_dir.is_dir():
        print('エラー: ディレクトリが存在しません: {0}'.format(markdown_dir),
              file=sys.stderr)
        sys.exit(1)

    index_path = markdown_dir / 'index_namespaces.md'
    if not index_path.is_file():
        print('complete-namespace-index: index_namespaces.md がないため処理をスキップします。')
        return

    inserted = complete_namespace_index(index_path)

    if inserted > 0:
        print('complete-namespace-index: 親名前空間のエントリ {0} 件を補完しました。'.format(
            inserted))
    else:
        print('complete-namespace-index: 補完が必要な親名前空間はありませんでした。')


if __name__ == '__main__':
    main()
