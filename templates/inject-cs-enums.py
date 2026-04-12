#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
inject-cs-enums.py - C# ファイルドキュメントへの enum セクション挿入

Doxygen XML を解析して C# の enum を検出し、
対応する Files/*_8cs.md に ## 型 セクションと !include ディレクティブを挿入する。

struct の !include 機構と同様に、postprocess.sh が Enums/*.md を
Files/*.md へ統合した後、Enums/ ディレクトリを削除する。

使用方法:
    python3 inject-cs-enums.py <xml_dir> <docs_dir>
例:
    python3 inject-cs-enums.py ../../xml/calc.net ../../docs/doxybook2/calc.net
"""

import sys
import os
import glob
from pathlib import Path
from xml.etree import ElementTree as ET


def get_text(elem):
    """XML 要素からプレーンテキストを取得する。タグを無視してテキストのみ結合。"""
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def cs_basename_to_md_name(cs_basename):
    """
    .cs ファイルのベースネームを Doxybook2 の Files ページ名に変換する。

    Doxygen の命名規則: ピリオドを _8 に変換。
    例: CalcKind.cs -> CalcKind_8cs.md
    """
    return cs_basename.replace(".", "_8") + ".md"


def collect_enums(xml_dir):
    """
    XML ディレクトリから C# の enum 情報を収集する。

    各 memberdef[@kind='enum'] の location[@file] で .cs ファイルと紐付ける。
    compounddef の compoundname から namespace 名を取得する。

    Returns:
        dict: {cs_basename: [enum_info, ...]}
            cs_basename: .cs ファイルのベースネーム (例: "CalcKind.cs")
            enum_info: {name, namespace, brief, details, enumvalues}
                enumvalues: [{name, value, brief}]
    """
    file_enums = {}

    for xml_file in sorted(glob.glob(os.path.join(str(xml_dir), "*.xml"))):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except ET.ParseError:
            continue

        # 各 compounddef を走査 (1 ファイルに通常 1 つだが念のため)
        for compounddef in root.findall("compounddef"):
            # compound 名 (namespace の場合は CalcLib など)
            compoundname = compounddef.findtext("compoundname", "")

            for sectiondef in compounddef.findall("sectiondef"):
                for memberdef in sectiondef.findall("memberdef"):
                    if memberdef.get("kind") != "enum":
                        continue

                    # ソースファイルのパス
                    location = memberdef.find("location")
                    if location is None:
                        continue
                    file_path = location.get("file", "")
                    if not file_path.endswith(".cs"):
                        continue

                    cs_basename = os.path.basename(file_path)
                    enum_name = memberdef.findtext("name", "")
                    if not enum_name:
                        continue

                    # namespace: compounddef が namespace の場合のみ設定
                    namespace = ""
                    if compounddef.get("kind") == "namespace":
                        namespace = compoundname

                    brief = get_text(memberdef.find("briefdescription"))
                    details = get_text(memberdef.find("detaileddescription"))
                    # details が brief と同じ場合は重複を避けるため空扱いにする
                    if details == brief:
                        details = ""

                    enumvalues = []
                    for ev in memberdef.findall("enumvalue"):
                        ev_name = ev.findtext("name", "")
                        ev_init_raw = ev.findtext("initializer", "")
                        # "= 1" -> "1" (先頭の "= " を除去)
                        if ev_init_raw.startswith("= "):
                            ev_value = ev_init_raw[2:].strip()
                        else:
                            ev_value = ev_init_raw.strip()
                        ev_brief = get_text(ev.find("briefdescription"))
                        # Markdown テーブル内の | をエスケープ
                        ev_brief_escaped = ev_brief.replace("|", "\\|")
                        enumvalues.append({
                            "name": ev_name,
                            "value": ev_value,
                            "brief": ev_brief_escaped,
                        })

                    enum_info = {
                        "name": enum_name,
                        "namespace": namespace,
                        "brief": brief,
                        "details": details,
                        "enumvalues": enumvalues,
                    }

                    if cs_basename not in file_enums:
                        file_enums[cs_basename] = []
                    file_enums[cs_basename].append(enum_info)

    return file_enums


def generate_enum_md(enum_info):
    """
    enum 情報から Enums/*.md の Markdown コンテンツを生成する。

    struct の Classes/*.md と同形式: YAML フロントマター + H1 + テーブル + 説明文。
    postprocess.sh の !include 処理が YAML・H1 を除去してコンテンツを統合する。
    """
    name = enum_info["name"]
    namespace = enum_info["namespace"]
    brief = enum_info["brief"]
    details = enum_info["details"]
    enumvalues = enum_info["enumvalues"]

    fqname = "{}::{}".format(namespace, name) if namespace else name

    lines = []

    # YAML フロントマター
    lines.append("---")
    if brief:
        safe_brief = brief.replace('"', '\\"')
        lines.append('summary: "{}"'.format(safe_brief))
    lines.append("author: inject-cs-enums")
    lines.append("toc: false")
    lines.append("---")
    lines.append("")
    lines.append("<!-- IMPORTANT: This is an AUTOMATICALLY GENERATED file by inject-cs-enums.py. Manual edits are NOT allowed. -->")
    lines.append("")

    # H1 (postprocess.sh の !include 処理が除去する)
    lines.append("# {}".format(fqname))
    lines.append("")

    # brief 説明文 (テーブルの前に出力)
    if brief:
        lines.append(brief)
        lines.append("")

    if details:
        lines.append(details)
        lines.append("")

    # 列挙値テーブル
    lines.append("| 列挙子 | 値 | 説明 |")
    lines.append("| ---------- | ----- | ----------- |")
    for ev in enumvalues:
        lines.append("| {} | {}| {} |".format(ev["name"], ev["value"], ev["brief"]))
    lines.append("")

    return "\n".join(lines)


def inject_into_files_md(files_md_path, enums, enums_rel):
    """
    Files/*.md の末尾に ## 型 セクションと !include ディレクティブを追記する。

    既に ## 型 セクションがある場合はスキップする。
    !include のパスは docs_dir からの相対パスで記述する
    (postprocess.sh が MARKDOWN_DIR 基準で解決するため)。
    """
    with open(str(files_md_path), "r", encoding="utf-8") as f:
        content = f.read()

    if "\n## 型\n" in content:
        print("  [skip] {}: ## 型 section already exists".format(files_md_path.name))
        return

    lines = ["\n## 型\n"]
    for enum_info in enums:
        enum_name = enum_info["name"]
        namespace = enum_info["namespace"]
        fqname = "{}::{}".format(namespace, enum_name) if namespace else enum_name
        enum_md_name = "{}.md".format(enum_name)
        include_path = "{}/{}".format(enums_rel, enum_md_name)
        lines.append("\n### {}\n".format(fqname))
        lines.append("\n!include {}\n".format(include_path))

    with open(str(files_md_path), "a", encoding="utf-8", newline="\n") as f:
        f.write("".join(lines))

    names = [e["name"] for e in enums]
    print("  [ok] {}: {} inserted".format(files_md_path.name, ", ".join(names)))


def main():
    if len(sys.argv) < 3:
        print("Usage: {} <xml_dir> <docs_dir>".format(sys.argv[0]), file=sys.stderr)
        return 1

    xml_dir = Path(sys.argv[1])
    docs_dir = Path(sys.argv[2])

    if not xml_dir.is_dir():
        print("Error: xml_dir does not exist: {}".format(xml_dir), file=sys.stderr)
        return 1
    if not docs_dir.is_dir():
        print("Error: docs_dir does not exist: {}".format(docs_dir), file=sys.stderr)
        return 1

    print("[inject-cs-enums] xml={}  docs={}".format(xml_dir, docs_dir))

    file_enums = collect_enums(xml_dir)

    if not file_enums:
        #print("  No C# enums found.")
        print("[inject-cs-enums] Done: 0 file(s) processed")
        return 0

    # docs_dir 以下の Files/ ディレクトリを再帰的に探索
    processed = 0
    for files_dir in sorted(docs_dir.rglob("Files")):
        if not files_dir.is_dir():
            continue

        # Enums/ は Files/ と同じ階層 (category ディレクトリ直下) に配置
        enums_dir = files_dir.parent / "Enums"
        # !include で使う相対パス (docs_dir からの相対)
        enums_rel = str(enums_dir.relative_to(docs_dir))

        for cs_basename, enums in file_enums.items():
            md_name = cs_basename_to_md_name(cs_basename)
            files_md_path = files_dir / md_name
            if not files_md_path.exists():
                continue

            # Enums/*.md を生成
            enums_dir.mkdir(parents=True, exist_ok=True)
            for enum_info in enums:
                enum_md_path = enums_dir / "{}.md".format(enum_info["name"])
                with open(str(enum_md_path), "w", encoding="utf-8", newline="\n") as f:
                    f.write(generate_enum_md(enum_info))
                print("  [generated] {}".format(enum_md_path.relative_to(docs_dir)))

            # Files/*.md に !include を追記
            inject_into_files_md(files_md_path, enums, enums_rel)
            processed += 1

    print("[inject-cs-enums] Done: {} file(s) processed".format(processed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
