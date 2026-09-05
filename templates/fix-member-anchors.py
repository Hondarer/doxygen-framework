#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""fix-member-anchors.py - Doxybook2 形式のメンバー アンカーを実在する見出しへ合わせる

Doxybook2 は Doxygen のクロス参照 (@ref や `func()` の自動リンク) を
`[text](Path/to/page.md#function-cplat-memory-lock-self)` の形式で出力する。
アンカーは「種別 + ハイフン化したメンバー名」であり、アンダースコアもハイフンへ
変換される。

一方、doxyfw のテンプレート (nonclass_members_details.tmpl 等) が生成する見出しは
`### cplat_memory_lock_self` であり、Markdown から作られる id は
`cplat_memory_lock_self` になる。このため Doxybook2 のアンカーはどこにも一致せず、
リンクを開いてもページ先頭へ飛ぶ。

このスクリプトは、次の順で対処する。

1. `#<種別>-<ハイフン化した名前>` を `#<アンダースコアへ戻した名前>` へ書き戻す。
   参照先ファイルに同名の見出しが実在する場合だけ適用する。
   C/C++/C# の識別子にハイフンは使えないため、ハイフンからアンダースコアへの
   復元は一意に定まる。
2. 見出しが見つからない場合はアンカーを削除し、ページへのリンクだけを残す。
   patch-index-files.py が `#file-xxx.h` に対して行う処理と同じ方針である。

対象は Markdown ディレクトリ配下のすべての `*.md` で、処理は冪等である。

既知の制限: 名前空間配下の型は見出しが `名前空間::型名` になるため、名前が
一致せずアンカー削除の側へ倒れる。C を主対象とする本フレームワークでは該当しない。

使用方法: ./fix-member-anchors.py <markdown_directory>
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Doxybook2 がメンバーのアンカーに使う種別。
# 見出しがメンバー名そのものになる種別だけを対象とする。
# `file` は対象外。`#file-add.c` は patch-index-files.py が別途削除する。
MEMBER_KINDS = (
    "function",
    "variable",
    "define",
    "typedef",
    "enum",
    "using",
    "friend",
    "property",
    "event",
    "signal",
    "slot",
)

LINK_RE = re.compile(
    r"\]\("
    r"(?P<path>[^)#\s]*)"
    r"#(?P<kind>" + "|".join(MEMBER_KINDS) + r")-(?P<anchor>[^)\s]+)"
    r"\)"
)

HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*$")


def read_text(path: str) -> Optional[str]:
    """ファイルを UTF-8 として読む。読めない場合は None を返す。"""
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def collect_headings(path: str) -> set:
    """ファイルが持つ見出しの文字列を集める。"""
    text = read_text(path)
    if text is None:
        return set()
    headings = set()
    in_code_block = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        matched = HEADING_RE.match(line)
        if matched:
            headings.add(matched.group(1).strip())
    return headings


def fix_file(path: str, heading_cache: dict) -> int:
    """1 ファイルのメンバー アンカーを書き換える。書き換えた件数を返す。"""
    with open(path, "rb") as f:
        data = f.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return 0

    base_dir = os.path.dirname(path)
    count = 0

    def replace(matched: re.Match) -> str:
        nonlocal count
        link_path = matched.group("path")
        name = matched.group("anchor").replace("-", "_")

        target = path if link_path == "" else os.path.normpath(os.path.join(base_dir, link_path))
        if target not in heading_cache:
            heading_cache[target] = collect_headings(target)

        count += 1
        if name in heading_cache[target]:
            return "](%s#%s)" % (link_path, name.lower())
        # 見出しが見つからない場合はアンカーを落とし、ページへのリンクだけを残す。
        return "](%s)" % link_path

    fixed = LINK_RE.sub(replace, text)
    if fixed != text:
        with open(path, "wb") as f:
            f.write(fixed.encode("utf-8"))
    return count


def main() -> int:
    if len(sys.argv) != 2:
        print("使用方法: fix-member-anchors.py <markdown_directory>", file=sys.stderr)
        return 1

    markdown_dir = sys.argv[1]
    if not os.path.isdir(markdown_dir):
        print("ディレクトリが存在しません: %s" % markdown_dir, file=sys.stderr)
        return 1

    heading_cache: dict = {}
    total = 0
    for root, _dirs, files in os.walk(markdown_dir):
        for name in sorted(files):
            if name.endswith(".md"):
                total += fix_file(os.path.join(root, name), heading_cache)

    if total > 0:
        print("  Fixed member anchors: %d" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
