#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
merge-member-docs.py - 宣言側 memberdef の説明をソース定義側 memberdef へ同期する

Doxygen は、ヘッダーで宣言しソースで定義する非グループ関数について、ファイル
コンパウンド XML へ宣言側と定義側の memberdef を別々に出力する。internal のように
ソースを INPUT に含む場合、宣言側 (ヘッダー) memberdef には宣言・定義のコメントが
Doxygen により統合された完全版が入るが、定義側 (ソース) memberdef は定義ローカルの
コメントのみで、宣言側の説明 (brief 以外の detaileddescription 等) が欠落する。
その結果、Doxybook2 が描画する Files/src/*.c.md に宣言側の説明が出力されない。

本スクリプトは Doxybook2 変換前に、宣言側 (統合済み完全版) memberdef の
briefdescription / detaileddescription / inbodydescription のインナー XML を、
対応する定義側 memberdef へ上書きコピーすることで、両ページに同じ統合結果を出力させる。

宣言側は既に「宣言コメント → 定義コメント」の順で統合されているため、上書きで過不足なく
揃う。連結すると定義側に既存する定義コメントが二重化するため、連結ではなく上書きとする。

グループへ移動した関数は、ファイル コンパウンドに完全な memberdef を持たず
<member refid="group__..."> 参照のみとなるため、本処理 (完全 memberdef が対象) では
自然に対象外となる (グループ メンバーは inject-groups.py が別途処理する)。

ダウンストリーム (extract-graphs.py / preprocess.sh) が XML を正規表現で扱い書式保持を
前提とするため、ElementTree での全文再シリアライズは行わず、正規表現による外科的な
テキスト置換で XML を書き換える (extract-graphs.py と同方針)。

使用方法:
    python3 merge-member-docs.py <xml_dir>
"""

import sys
import os
import glob
import re

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 関数 memberdef ブロック (memberdef はネストしないため非貪欲で安全に切り出せる)
MEMBERDEF_RE = re.compile(
    r'<memberdef\b[^>]*\bkind="function"[^>]*>.*?</memberdef>',
    re.DOTALL,
)

ID_RE = re.compile(r'<memberdef\b[^>]*\bid="([^"]*)"')
NAME_RE = re.compile(r'<name>(.*?)</name>', re.DOTALL)
ARGSSTRING_RE = re.compile(r'<argsstring>(.*?)</argsstring>', re.DOTALL)
LOCATION_RE = re.compile(r'<location\b([^>]*?)/?>')
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')

# 同期対象の説明セクション (インナー XML を入れ替える)
DESC_TAGS = ("briefdescription", "detaileddescription", "inbodydescription")


def parse_location_attrs(block):
    """memberdef ブロック内の最初の <location ...> の属性を dict で返す。"""
    m = LOCATION_RE.search(block)
    if not m:
        return {}
    return dict(ATTR_RE.findall(m.group(1)))


def get_inner(block, tag):
    """block 内の <tag>...</tag> のインナー XML を返す。存在しなければ None。"""
    m = re.search(
        r'<{tag}>(.*?)</{tag}>'.format(tag=tag), block, re.DOTALL
    )
    if not m:
        return None
    return m.group(1)


def set_inner(block, tag, inner):
    """block 内の <tag>...</tag> のインナー XML を inner へ置換した block を返す。

    置換対象が無い場合は block をそのまま返す。re.sub の置換文字列で
    バックスラッシュ等が特殊解釈されないよう、関数置換を用いる。
    """
    pattern = re.compile(
        r'(<{tag}>)(.*?)(</{tag}>)'.format(tag=tag), re.DOTALL
    )

    def repl(m):
        return m.group(1) + inner + m.group(3)

    return pattern.sub(repl, block, count=1)


def collect_members(xml_dir):
    """xml_dir の全 XML から関数 memberdef を収集する。

    Returns:
        list of dict:
            path:  由来 XML ファイル パス
            id:    memberdef id
            name:  関数名
            args:  argsstring
            file:  location/@file
            body:  location/@bodyfile (無ければ None)
            decl:  location/@declfile (無ければ None)
            block: memberdef ブロック テキスト
    """
    records = []
    for xml_file in sorted(glob.glob(os.path.join(str(xml_dir), "*.xml"))):
        base = os.path.basename(xml_file)
        if base in ("index.xml", "Doxyfile.xml"):
            continue
        try:
            with open(xml_file, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            print(
                "Error: failed to read {}: {}".format(xml_file, exc),
                file=sys.stderr,
            )
            return None

        for m in MEMBERDEF_RE.finditer(text):
            block = m.group(0)
            id_m = ID_RE.search(block)
            name_m = NAME_RE.search(block)
            args_m = ARGSSTRING_RE.search(block)
            loc = parse_location_attrs(block)
            records.append({
                "path": xml_file,
                "id": id_m.group(1) if id_m else "",
                "name": name_m.group(1).strip() if name_m else "",
                "args": args_m.group(1).strip() if args_m else "",
                "file": loc.get("file"),
                "body": loc.get("bodyfile"),
                "decl": loc.get("declfile"),
                "block": block,
            })
    return records


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <xml_dir>".format(sys.argv[0]), file=sys.stderr)
        return 1

    xml_dir = sys.argv[1]
    if not os.path.isdir(xml_dir):
        print("Error: xml_dir does not exist: {}".format(xml_dir), file=sys.stderr)
        return 1

    print("[merge-member-docs] xml={}".format(xml_dir))

    records = collect_members(xml_dir)
    if records is None:
        return 1

    # ペアリング キー = (name, argsstring, bodyfile)。
    # bodyfile が無いもの (本体なしの宣言だけ等) は対にならないため除外。
    groups = {}
    for rec in records:
        if not rec["body"]:
            continue
        key = (rec["name"], rec["args"], rec["body"])
        groups.setdefault(key, []).append(rec)

    # 由来ファイルごとに「定義側ブロック old -> new」の置換を蓄積する
    edits = {}  # {path: [(old_block, new_block), ...]}
    synced = 0

    for key, recs in groups.items():
        name, args, body = key
        # file != bodyfile = 宣言側 (ヘッダー側の統合済み完全版)
        # file == bodyfile = 定義側 (ソース側の定義ローカル版)
        decls = [r for r in recs if r["file"] and r["file"] != body]
        defs = [r for r in recs if r["file"] == body]

        # 宣言側・定義側が無い (= ソースのみ定義/本体なし宣言のみ) は対象外
        if not decls or not defs:
            continue

        if len(decls) != 1 or len(defs) != 1:
            print(
                "  [skip] {}{}: 宣言側 {} 件 / 定義側 {} 件 (一意でないため対象外)".format(
                    name, args, len(decls), len(defs)
                )
            )
            continue

        decl = decls[0]
        defn = defs[0]

        new_block = defn["block"]
        for tag in DESC_TAGS:
            inner = get_inner(decl["block"], tag)
            if inner is None:
                continue
            new_block = set_inner(new_block, tag, inner)

        if new_block == defn["block"]:
            # 既に同一 (冪等)
            continue

        edits.setdefault(defn["path"], []).append((defn["block"], new_block))
        synced += 1
        print("  [sync] {}{} -> {}".format(name, args, os.path.basename(defn["path"])))

    # ファイル単位で書き戻す
    for path, repls in edits.items():
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            print("Error: failed to read {}: {}".format(path, exc), file=sys.stderr)
            return 1

        for old_block, new_block in repls:
            if old_block not in text:
                print(
                    "Error: 定義側ブロックが見つかりません ({})".format(path),
                    file=sys.stderr,
                )
                return 1
            text = text.replace(old_block, new_block, 1)

        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        except OSError as exc:
            print("Error: failed to write {}: {}".format(path, exc), file=sys.stderr)
            return 1

    print("[merge-member-docs] Done: {} member(s) synced".format(synced))
    return 0


if __name__ == "__main__":
    sys.exit(main())
