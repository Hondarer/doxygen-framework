#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
inject-groups.py - Files ドキュメントへのグループセクション挿入

Doxygen XML を解析してグループ (@defgroup) を検出し、
グループメンバーの location から対応するソースファイルを特定して、
Files/*.md に ## グループタイトル セクションと !include ディレクティブを挿入する。

各 Files/*.md への include では、そのファイルで定義されたメンバーのみを含む
フィルタ済み中間 MD (Modules/perfile__*.md) を生成して参照する。
別ファイル起源のメンバーはフィルタ済み MD から除外される。

postprocess.sh が Files/*.md へ統合した後、perfile__*.md を削除する。
Modules/group__*.md はスタンドアロンのグループページとして保持する。

使用方法:
    python3 inject-groups.py <xml_dir> <docs_dir>
例:
    python3 inject-groups.py ../../xml/porter ../../docs/doxybook2/porter
"""

import sys
import os
import re
import glob
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# メンバーの宣言ファイル拡張子 → コード フェンスの言語指定
# Doxygen の group コンパウンドには language 属性がなく、Doxybook2 の
# メンバー描画で {{language}} が空になるため、宣言ファイルから言語を推定する。
EXT_LANGUAGE_MAP = {
    ".c": "cpp",
    ".h": "cpp",
    ".cc": "cpp",
    ".hh": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
}


def source_basename_to_md_name(basename):
    """
    ソースファイルのベースネームを Doxybook2 の Files ページ名に変換する。

    Doxygen の命名規則:
      アンダースコアを二重アンダースコアに変換し、ピリオドを _8 に変換する。

    例:
      libporter_const.h -> libporter__const_8h.md
      commRecvThread.h      -> commRecvThread_8h.md
    """
    return basename.replace("_", "__").replace(".", "_8") + ".md"


def build_file_compound_map(xml_dir):
    """
    ファイル コンパウンド XML を走査し、ソースファイルパス → compound_id のマップを構築する。

    group__*.xml などの非ファイル コンパウンドは除外する。
    compound_id は Doxybook2 が生成する .md ファイルのベース名に相当する。

    Returns:
        dict: {location_file_path: compound_id}
    """
    file_map = {}
    skip_names = {"compound.xsd", "combine.xslt", "index.xml", "Doxyfile.xml"}
    for xml_file in sorted(glob.glob(os.path.join(str(xml_dir), "*.xml"))):
        if os.path.basename(xml_file) in skip_names:
            continue
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except ET.ParseError:
            continue
        for compounddef in root.findall("compounddef"):
            if compounddef.get("kind") != "file":
                continue
            compound_id = compounddef.get("id", "")
            if not compound_id:
                continue
            location = compounddef.find("location")
            if location is not None:
                loc_file = location.get("file", "")
                if loc_file:
                    file_map[loc_file] = compound_id
    return file_map


def collect_groups(xml_dir):
    """
    XML ディレクトリからグループ情報と親子関係を収集する。

    各 group__*.xml の compounddef を解析し、すべてのメンバーの location を走査して
    「そのメンバーが定義されたファイル」ごとにグループを紐付ける (多対多マッピング)。
    グループメンバーが複数ファイルにまたがる場合、各ファイルに対して
    そのファイル内のメンバーのみを根拠にグループを関連付ける。

    また <innergroup> 要素から親子関係 (hierarchy) も収集する。

    Returns:
        tuple: (group_data, hierarchy, body_file_data, member_langs)
            group_data: {group_id: (title, {source_basename: (member_names_set, min_line)})}
                group_id: グループ ID (例: "group__COMM__RESULT")
                title: グループタイトル (例: "戻り値")
                source_basename: ソースファイルのベースネーム (例: "libporter_const.h")
                member_names_set: そのファイルで定義されたメンバー名の集合
                min_line: そのファイル内のメンバーの最小行番号 (ファイル内でのソートに使用)
            hierarchy: {parent_id: [(child_id, child_title), ...]}
                parent_id: 親グループ ID
                child_id: 子グループ ID
                child_title: 子グループのタイトル (XML の <innergroup> テキスト)
            body_file_data: {bodyfile_path: [(group_id, member_name, bodystart_line)]}
                bodyfile_path: Doxygen が記録した定義ファイルパス (例: "libsrc/calc/calcHandler.c")
                member_name:   メンバー名
                bodystart_line: 定義の開始行 (ソート用)
            member_langs: {group_id: {member_name: language}}
                宣言ファイルの拡張子から推定したコード フェンスの言語指定。
                EXT_LANGUAGE_MAP にない拡張子のメンバーは含まれない。
    """
    group_data = {}
    hierarchy = {}
    body_file_data = {}
    member_langs = {}

    for xml_file in sorted(glob.glob(os.path.join(str(xml_dir), "group__*.xml"))):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except ET.ParseError:
            continue

        for compounddef in root.findall("compounddef"):
            if compounddef.get("kind") != "group":
                continue

            group_id = compounddef.get("id", "")
            title = compounddef.findtext("title", "")
            if not group_id:
                continue

            # ファイルごとに { basename: (member_names_set, min_line) } を構築する
            file_data = {}
            for sectiondef in compounddef.findall("sectiondef"):
                for memberdef in sectiondef.findall("memberdef"):
                    location = memberdef.find("location")
                    if location is None:
                        continue
                    file_path = location.get("file", "")
                    if not file_path:
                        continue
                    name = memberdef.findtext("name", "")
                    line_str = location.get("line", "999999")
                    try:
                        line = int(line_str)
                    except ValueError:
                        line = 999999

                    basename = os.path.basename(file_path)
                    if basename not in file_data:
                        file_data[basename] = (set(), 999999)
                    names_set, cur_min = file_data[basename]
                    names_set.add(name)
                    if line < cur_min:
                        file_data[basename] = (names_set, line)

                    # 宣言ファイルの拡張子からフェンス言語を推定する
                    ext = os.path.splitext(basename)[1].lower()
                    lang = EXT_LANGUAGE_MAP.get(ext)
                    if lang:
                        if group_id not in member_langs:
                            member_langs[group_id] = {}
                        member_langs[group_id][name] = lang

                    # bodyfile (定義ファイル) を収集する
                    # bodyfile が宣言ファイル (file_path) と異なる場合のみ対象とする。
                    # #define のように bodyfile が存在しないメンバーはスキップする。
                    body_path = location.get("bodyfile", "")
                    if body_path and body_path != file_path:
                        try:
                            body_line = int(location.get("bodystart", "999999"))
                        except ValueError:
                            body_line = 999999
                        if body_path not in body_file_data:
                            body_file_data[body_path] = []
                        body_file_data[body_path].append((group_id, name, body_line))

            if file_data:
                group_data[group_id] = (title, file_data)

            # 子グループ (innergroup) を収集して親子関係を構築する
            innergroups = []
            for ig in compounddef.findall("innergroup"):
                child_refid = ig.get("refid", "")
                child_title = (ig.text or "").strip()
                if child_refid:
                    innergroups.append((child_refid, child_title))
            if innergroups:
                hierarchy[group_id] = innergroups

    return group_data, hierarchy, body_file_data, member_langs


def fix_member_fence_language(docs_dir, member_langs):
    """
    Modules/group__*.md のメンバー シグネチャ フェンスに言語指定を付与する。

    Doxygen の group コンパウンドには language 属性がなく、Doxybook2 の
    メンバー描画で {{language}} が空になるため、シグネチャのコード フェンスが
    言語指定なしの ``` で出力される。
    collect_groups が宣言ファイルの拡張子から推定した言語 (member_langs) を使い、
    メンバー見出しの直後 (空行のみを挟む) に現れる ``` 行へ言語を付与する。

    member_details.tmpl は function / variable / typedef 等のシグネチャ フェンスを
    メンバー描画の先頭に出力するため、この条件でシグネチャ フェンスのみを
    正確に特定できる。メンバー本文中の言語なしフェンス (@code 由来など) は
    見出し直後ではないため変更されない。

    perfile / perchild / body 注入より前に実行することで、グループ md から
    抽出されるすべての埋め込みセクションに言語指定が波及する。

    @param[in] docs_dir     doxybook2 出力ディレクトリ
    @param[in] member_langs {group_id: {member_name: language}}
    """
    structure_marker = "!doxyfw-structure-title!"
    processed = 0

    for modules_dir in sorted(docs_dir.rglob("Modules")):
        if not modules_dir.is_dir():
            continue

        for group_id in sorted(member_langs.keys()):
            name_langs = member_langs[group_id]
            group_md = modules_dir / "{}.md".format(group_id)
            if not group_md.exists():
                continue

            with open(str(group_md), "r", encoding="utf-8") as f:
                lines = f.read().split("\n")

            changed = False
            in_code_block = False
            pending_lang = None
            strip_inline_in_fence = False

            for i, line in enumerate(lines):
                if line.startswith("```"):
                    if not in_code_block:
                        strip_inline_in_fence = False
                        if pending_lang is not None and line == "```":
                            lines[i] = "```" + pending_lang
                            changed = True
                            # C# に inline キーワードはない。member_details.tmpl が
                            # language 空のときに出力した inline を除去する。
                            strip_inline_in_fence = (pending_lang == "csharp")
                    in_code_block = not in_code_block
                    pending_lang = None
                    continue

                if in_code_block:
                    if strip_inline_in_fence:
                        new_line = re.sub(r"\binline ", "", line)
                        if new_line != line:
                            lines[i] = new_line
                            changed = True
                    continue

                if line == "":
                    # 見出しとシグネチャ フェンスの間の空行では判定を維持する
                    continue

                heading_line = line
                if heading_line.startswith(structure_marker):
                    heading_line = heading_line[len(structure_marker):]

                if heading_line.startswith("### "):
                    pending_lang = name_langs.get(heading_line[4:].strip())
                else:
                    pending_lang = None

            if changed:
                with open(str(group_md), "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(lines))
                processed += 1

    print("[inject-groups] fence language fixed: {} file(s)".format(processed))


def parse_group_md_sections(md_path):
    """
    Doxybook2 が生成した Modules/*.md をパースし、メンバーセクションを分解する。

    YAML フロントマター・HTML コメント・H1 を読み飛ばした後、
    残りを H2 (セクション見出し) と H3 (個別メンバー) で分割する。
    コードブロック内の ## / ### はメンバー境界として扱わない。

    Returns:
        list: [(h2_heading_line, [(member_name, [content_lines]), ...]), ...]
            h2_heading_line: "## 定数、マクロ" 等の H2 見出し行
            member_name: "### COMM_SUCCESS" の "COMM_SUCCESS" 部分
            content_lines: H3 見出し行を含むそのメンバーのすべての行
    """
    with open(str(md_path), "r", encoding="utf-8") as f:
        raw_lines = f.read().split("\n")

    i = 0
    n = len(raw_lines)

    # YAML フロントマターをスキップ
    if i < n and raw_lines[i].strip() == "---":
        i += 1
        while i < n and raw_lines[i].strip() != "---":
            i += 1
        i += 1  # closing ---

    # HTML コメントをスキップ
    while i < n and raw_lines[i].startswith("<!--"):
        while i < n and "-->" not in raw_lines[i]:
            i += 1
        i += 1

    # H1 と直後の空行をスキップ
    while i < n and (raw_lines[i] == "" or raw_lines[i].startswith("# ")):
        i += 1

    remaining = raw_lines[i:]

    structure_marker = "!doxyfw-structure-title!"

    # H2/H3 境界でセクションを分解
    sections = []          # [(h2_line, [(name, [lines])])]
    current_h2 = None
    current_members = []   # [(name, [lines])]
    current_name = None
    current_lines = []
    in_code_block = False

    for line in remaining:
        if line.startswith("```"):
            in_code_block = not in_code_block

        heading_line = line
        if heading_line.startswith(structure_marker):
            heading_line = heading_line[len(structure_marker):]

        if not in_code_block and heading_line.startswith("## "):
            # 進行中のメンバーをフラッシュ
            if current_name is not None:
                current_members.append((current_name, current_lines))
                current_name = None
                current_lines = []
            # 進行中の H2 セクションをフラッシュ
            if current_h2 is not None:
                sections.append((current_h2, current_members))
                current_members = []
            current_h2 = line

        elif not in_code_block and heading_line.startswith("### "):
            # 進行中のメンバーをフラッシュ
            if current_name is not None:
                current_members.append((current_name, current_lines))
            current_name = heading_line[4:].strip()
            current_lines = [line]

        else:
            if current_name is not None:
                current_lines.append(line)

    # 末尾のメンバー・セクションをフラッシュ
    if current_name is not None:
        current_members.append((current_name, current_lines))
    if current_h2 is not None:
        sections.append((current_h2, current_members))

    return sections


# メンバー本文中の Classes include 行を検出する正規表現
# (例: !include Classes/structcom__util__realtime__timestamp.md)
_CLASSES_INCLUDE_RE = re.compile(r"^[ \t]*!include[ \t]+(Classes/.+\.md)[ \t]*$")


def _strip_classes_md_header(md_path):
    """
    raw Classes/*.md からフロントマター・先頭 HTML コメント・H1 を除いた本文行を返す。

    inject-groups.py は postprocess.sh より前に実行されるため、ここで読む内容は
    !doxyfw-structure-title! マーカー・!dunder!・!linebreak! が未変換の raw である。

    Doxybook2 出力では フロントマターと HTML コメントの間、HTML コメントと H1 の間に
    空行が入る。空行が混在しても本文先頭 (最初の H2 以降の実コンテンツ) まで
    確実にスキップするため、空行 / HTML コメント / H1 を区別せず読み飛ばす。
    """
    with open(str(md_path), "r", encoding="utf-8") as f:
        raw_lines = f.read().split("\n")

    i = 0
    n = len(raw_lines)

    # YAML フロントマターをスキップ
    if i < n and raw_lines[i].strip() == "---":
        i += 1
        while i < n and raw_lines[i].strip() != "---":
            i += 1
        i += 1  # closing ---

    # フロントマター後、本文開始まで 空行 / HTML コメント / H1 をスキップ
    while i < n:
        if raw_lines[i] == "":
            i += 1
            continue
        if raw_lines[i].startswith("<!--"):
            while i < n and "-->" not in raw_lines[i]:
                i += 1
            i += 1  # closing -->
            continue
        if raw_lines[i].startswith("# "):
            i += 1
            continue
        break

    return raw_lines[i:]


def resolve_classes_includes(member_lines, classes_dir, offset):
    """
    メンバー本文中の !include Classes/<name>.md を raw Classes 本文でインライン解決する。

    struct / class メンバーは member_details.tmpl により本文が
    !include Classes/struct....md の 1 行になる。これを Files/.c への注入経路で
    そのまま残すと、perfile の !include 展開 (postprocess.sh) の内側に位置する
    ネストした !include となり、postprocess.sh が解決できずリテラルとして残る。
    そこで inject-groups.py 段階で raw Classes 本文に展開しておき、
    postprocess.sh には常に 1 段だけの include を渡す。

    展開した Classes 本文の見出しは shift_heading_line で offset 段シフトする。
    perfile 経由 (postprocess.sh が後段で offset 1 を加える) では offset=1 を与え、
    最終的にスタンドアロン Modules ページと同じ offset 2 に揃える。

    @param[in] member_lines 1 メンバー分の行リスト
    @param[in] classes_dir  Classes ディレクトリ (None の場合は解決しない)
    @param[in] offset       展開した Classes 本文に与える見出しシフト段数
    @return    解決後の行リスト
    """
    if classes_dir is None:
        return member_lines

    resolved = []
    for line in member_lines:
        match = _CLASSES_INCLUDE_RE.match(line)
        if not match:
            resolved.append(line)
            continue

        # Classes/<name>.md の <name> 部分を取り出してファイルを特定する
        rel = match.group(1)
        classes_md = classes_dir / Path(rel).name
        if not classes_md.exists():
            # 解決できない場合は元の行を保持 (後方互換)
            resolved.append(line)
            continue

        body_lines = _strip_classes_md_header(classes_md)
        in_code_block = False
        for body_line in body_lines:
            if body_line.startswith("```"):
                in_code_block = not in_code_block
                resolved.append(body_line)
                continue
            if in_code_block:
                resolved.append(body_line)
                continue
            resolved.append(shift_heading_line(body_line, offset))

    return resolved


def generate_filtered_md(title, sections, member_names, classes_dir=None):
    """
    対象ファイルのメンバー名集合でフィルタした中間 MD コンテンツを生成する。

    member_names に含まれるメンバーのみを出力し、別ファイル起源のメンバーを除外する。
    H2/H3 見出しレベルは Doxybook2 出力のまま保持する。
    postprocess.sh の !include 処理が YAML・HTML コメント・H1 を除去し、
    heading_offset=1 でシフトして埋め込む。

    struct / class メンバー本文の !include Classes/...md は、postprocess.sh の
    perfile 展開の内側でネストし解決されないため、classes_dir が与えられた場合は
    resolve_classes_includes でここで raw Classes 本文に展開する。perfile は
    postprocess.sh が offset 1 で展開するため offset=1 を与え、最終的に
    スタンドアロン Modules ページと同じ offset 2 に揃える。
    """
    out = []
    out.append("---")
    out.append("author: inject-groups")
    out.append("toc: false")
    out.append("---")
    out.append("")
    out.append("<!-- IMPORTANT: This is an AUTOMATICALLY GENERATED file by inject-groups.py. Manual edits are NOT allowed. -->")
    out.append("")
    out.append("# {}".format(title))
    out.append("")

    for (h2_line, members) in sections:
        # このセクションで対象ファイルに属するメンバーだけを抽出
        filtered = [(name, lines) for (name, lines) in members if name in member_names]
        if not filtered:
            continue
        out.append(h2_line)
        out.append("")
        for (_, member_lines) in filtered:
            out.extend(resolve_classes_includes(member_lines, classes_dir, 1))
            out.append("")

    return "\n".join(out)


def shift_heading_line(line, offset):
    """
    見出し行を offset 段深くする。見出し以外の行はそのまま返す。

    !doxyfw-structure-title! / !doxyfw-detail-title! マーカー付きの見出しにも
    対応する (postprocess.sh の !include 展開と同じ規則)。レベルは H6 で飽和する。
    """
    match = re.match(
        r"^(!doxyfw-structure-title!|!doxyfw-detail-title!)?(#{1,6})([ \t].*)$",
        line,
    )
    if not match:
        return line
    prefix = match.group(1)
    if prefix is None:
        prefix = ""
    level = len(match.group(2)) + offset
    if level > 6:
        level = 6
    return prefix + "#" * level + match.group(3)


def build_embedded_group_section(title, sections, member_names, classes_dir=None):
    """
    対象メンバーのみを含むグループ セクションを、直接埋め込み用に組み立てる。

    !include を使わず、見出しを 1 段シフト済みのテキストとして返す。
    Classes/*.md のように自身が Files/*.md や Namespaces/*.md から !include
    される側のファイルでは、ネストした !include を postprocess.sh が解決
    できないため、この直接埋め込みを使う。

    グループ タイトルは !doxyfw-structure-title! マーカー付き H2 とし、
    !include 展開で H4 以深にシフトされても太字変換されず見出しとして残るようにする。

    struct / class メンバー本文の !include Classes/...md は、この埋め込み先 (Classes/*.md)
    が更に Files/*.md や Namespaces/*.md から !include されるためネストする。
    classes_dir が与えられた場合は resolve_classes_includes で raw Classes 本文に
    展開する。埋め込み自身が emit で見出しを 1 段シフトするため、ここでの追加
    offset は 0 とする。
    """
    out = ["", "!doxyfw-structure-title!## {}".format(title), ""]
    in_code_block = False

    def emit(line):
        nonlocal in_code_block
        if line.startswith("```"):
            in_code_block = not in_code_block
            out.append(line)
            return
        if in_code_block:
            out.append(line)
            return
        out.append(shift_heading_line(line, 1))

    for (h2_line, members) in sections:
        filtered = [(name, lines) for (name, lines) in members if name in member_names]
        if not filtered:
            continue
        emit(h2_line)
        out.append("")
        for (_, member_lines) in filtered:
            for member_line in resolve_classes_includes(member_lines, classes_dir, 0):
                emit(member_line)
            out.append("")

    return "\n".join(out)


def append_missing_group_sections(md_path, modules_dir, modules_rel,
                                  ordered_members, group_titles, log_prefix,
                                  embed=False, classes_dir=None):
    """
    対象 md に存在しないグループ メンバーをグループ セクションとして追記する。

    ordered_members の各メンバーについて、対象 md に見出し行 (### または ####) が
    存在するかを判定し、欠落メンバーのみを対象 md の末尾に
    ## グループタイトル セクションとして追記する。

    embed=False の場合はフィルタ済み中間 MD
    (Modules/perfile__<group_id>__<対象 md の stem>.md) を生成して !include で
    参照する (postprocess.sh が heading offset=1 で展開する)。
    embed=True の場合は見出しを 1 段シフトした内容を直接追記する。
    対象 md 自身が !include される側 (Classes/*.md) の場合に使う。

    @param[in] md_path         追記対象の md (Files/*.md または Classes/*.md)
    @param[in] modules_dir     Modules ディレクトリ
    @param[in] modules_rel     docs_dir からの Modules 相対パス (!include 用)
    @param[in] ordered_members [(group_id, member_name)] 出力したい順
    @param[in] group_titles    {group_id: title}
    @param[in] log_prefix      ログ表示用の種別 (例: "body", "class")
    @param[in] embed           True: 直接埋め込み / False: !include 参照
    @param[in] classes_dir     Classes ディレクトリ (struct メンバー本文の
                               !include Classes/...md をインライン解決する。None で無効)
    @return    True: 追記した / False: 追記不要または追記済み
    """
    content = md_path.read_text(encoding="utf-8")

    if not embed and "!include {}/perfile__".format(modules_rel) in content:
        print("  [skip] {}: perfile include already exists".format(md_path.name))
        return False

    # 欠落しているメンバーをグループごとに特定する。
    # 見出しレベルはネイティブ出力 (###) と直接埋め込み (####) の両方を許容する。
    # グループの出現順は ordered_members の順序を保持する。
    structure_marker = re.escape("!doxyfw-structure-title!")
    missing_names = {}  # {group_id: set(member_name)}
    group_order = []
    for (group_id, member_name) in ordered_members:
        pattern = re.compile(
            r"^(?:"
            + structure_marker
            + r")?####? "
            + re.escape(member_name)
            + r"[ \t]*$",
            re.MULTILINE,
        )
        if pattern.search(content):
            continue
        if group_id not in missing_names:
            missing_names[group_id] = set()
            group_order.append(group_id)
        missing_names[group_id].add(member_name)

    if not missing_names:
        return False

    append_lines = []
    for group_id in group_order:
        group_md = modules_dir / "{}.md".format(group_id)
        if not group_md.exists():
            print("  -> 警告: {} が見つかりません".format(group_md))
            continue

        sections = parse_group_md_sections(group_md)

        # グループ md に実在するメンバーだけを対象にする
        # (空セクションの追記を防ぐ)
        available = set()
        for (_, members) in sections:
            for (name, _) in members:
                available.add(name)
        effective = missing_names[group_id] & available
        if not effective:
            print("  -> 警告: {} に対象メンバーが見つかりません: {}".format(
                group_md.name, ", ".join(sorted(missing_names[group_id]))))
            continue

        title = group_titles.get(group_id, group_id)

        if embed:
            append_lines.append(
                build_embedded_group_section(title, sections, effective, classes_dir))
            append_lines.append("\n")
        else:
            filtered_content = generate_filtered_md(title, sections, effective, classes_dir)

            filtered_name = "perfile__{}__{}.md".format(group_id, md_path.stem)
            filtered_path = modules_dir / filtered_name
            with open(str(filtered_path), "w", encoding="utf-8", newline="\n") as f:
                f.write(filtered_content)

            append_lines.append("\n!doxyfw-structure-title!## {}\n".format(title))
            append_lines.append("\n!include {}/{}\n".format(modules_rel, filtered_name))

        print("  [{}] {}: {} を追記 (from {})".format(
            log_prefix, md_path.name, ", ".join(sorted(effective)), group_id))

    if not append_lines:
        return False

    with open(str(md_path), "a", encoding="utf-8", newline="\n") as f:
        f.write("".join(append_lines))

    return True


def inject_into_body_files_md(docs_dir, body_data, group_titles):
    """
    グループメンバーの定義ファイル (.c ページ) にグループセクションを補完する。

    Doxygen が FILE コンパウンド XML に <member refid="..."> (参照のみ) を出力した場合、
    Doxybook2 はそのメンバーを publicFunctions として扱わず、.c ページに
    メンバーが出力されない。
    この関数は Files/*.md への注入 (inject_into_files_md) と同じ perfile 機構を使い、
    欠落メンバーのみを .c ページの末尾に ## グループタイトル セクションとして追記する。

    inject-groups.py は postprocess.sh より前に実行されるため、
    追記内容は postprocess.sh の変換 (!include 展開、dunder エスケープ等) を
    同様に受ける。

    Files/*.md はこの時点でフラット構造 (restructure-files.py 実行前) であり、
    ファイル名は compound_id + ".md" 形式になっている。

    @param[in] docs_dir     doxybook2 出力ディレクトリ
    @param[in] body_data    {compound_id: [(group_id, member_name, line)]}
    @param[in] group_titles {group_id: title}
    """
    processed = 0

    for files_dir in sorted(docs_dir.rglob("Files")):
        if not files_dir.is_dir():
            continue

        modules_dir = files_dir.parent / "Modules"
        if not modules_dir.is_dir():
            continue

        modules_rel = str(modules_dir.relative_to(docs_dir))

        # struct メンバー本文の !include Classes/...md 解決用 (同階層の Classes)
        classes_dir = files_dir.parent / "Classes"
        if not classes_dir.is_dir():
            classes_dir = None

        for compound_id, member_infos in body_data.items():
            body_md_path = files_dir / (compound_id + ".md")
            if not body_md_path.exists():
                continue

            # グループの出現順は定義行を基準にする
            ordered_members = []
            for (group_id, member_name, _) in sorted(member_infos, key=lambda x: x[2]):
                ordered_members.append((group_id, member_name))

            if append_missing_group_sections(
                    body_md_path, modules_dir, modules_rel,
                    ordered_members, group_titles, "body", classes_dir=classes_dir):
                processed += 1

    print("[inject-groups] body files processed: {}".format(processed))


def collect_class_group_members(xml_dir):
    """
    クラス/構造体コンパウンドからグループへ移動したメンバーを収集する。

    C# などでクラス メンバーを @ingroup すると、Doxygen は memberdef を
    クラス コンパウンドからグループ コンパウンドへ移動し、クラス側には
    listofallmembers の参照だけが残る。
    listofallmembers の refid が group__ で始まるメンバーを「グループへ
    移動したメンバー」として収集する。

    Returns:
        dict: {class_compound_id: [(group_id, member_name), ...]}  (記載順)
    """
    result = {}
    skip_names = {"compound.xsd", "combine.xslt", "index.xml", "Doxyfile.xml"}
    # メンバー refid は <グループ compound id>_1<アンカー> 形式。
    # compound id 自体に _1 を含む場合があるため、最長一致で分割する。
    member_refid_re = re.compile(r"^(group__.+)_1[0-9a-zA-Z]+$")

    for xml_file in sorted(glob.glob(os.path.join(str(xml_dir), "*.xml"))):
        if os.path.basename(xml_file) in skip_names:
            continue
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except ET.ParseError:
            continue

        for compounddef in root.findall("compounddef"):
            if compounddef.get("kind") not in ("class", "struct", "interface", "union"):
                continue
            compound_id = compounddef.get("id", "")
            if not compound_id:
                continue

            lom = compounddef.find("listofallmembers")
            if lom is None:
                continue

            entries = []
            for member in lom.findall("member"):
                match = member_refid_re.match(member.get("refid", ""))
                if not match:
                    continue
                name = member.findtext("name", "")
                if not name:
                    continue
                entries.append((match.group(1), name))

            if entries:
                result[compound_id] = entries

    return result


def inject_into_class_files_md(docs_dir, class_group_members, group_titles):
    """
    グループへ移動したクラス メンバーをクラス ページへ補完する。

    inject_into_body_files_md と同じ perfile 機構で、欠落メンバーのみを
    Classes/*.md の末尾に ## グループタイトル セクションとして追記する。

    Classes/*.md は Files/*.md や Namespaces/*.md から !include される側のため、
    postprocess.sh はソート順 (Classes が Files / Namespaces より先) で
    処理することでネストした !include を解決する。

    @param[in] docs_dir            doxybook2 出力ディレクトリ
    @param[in] class_group_members {class_compound_id: [(group_id, member_name)]}
    @param[in] group_titles        {group_id: title}
    """
    processed = 0

    for classes_dir in sorted(docs_dir.rglob("Classes")):
        if not classes_dir.is_dir():
            continue

        modules_dir = classes_dir.parent / "Modules"
        if not modules_dir.is_dir():
            continue

        modules_rel = str(modules_dir.relative_to(docs_dir))

        for compound_id, ordered_members in class_group_members.items():
            class_md_path = classes_dir / (compound_id + ".md")
            if not class_md_path.exists():
                continue

            if append_missing_group_sections(
                    class_md_path, modules_dir, modules_rel,
                    ordered_members, group_titles, "class",
                    embed=True, classes_dir=classes_dir):
                processed += 1

    print("[inject-groups] class files processed: {}".format(processed))


def inject_into_files_md(files_md_path, groups, modules_dir, modules_rel, group_data,
                         class_member_names, classes_dir=None):
    """
    Files/*.md の末尾に ## グループタイトル セクションと !include ディレクティブを追記する。

    各グループについて、そのファイルで定義されたメンバーのみを含む
    フィルタ済み中間 MD (perfile__<group_id>__<files_stem>.md) を
    Modules/ に生成してから !include で参照する。

    クラスに属するメンバー (class_member_names) は除外する。
    クラス メンバーは inject_into_class_files_md が Classes/*.md へ注入し、
    Files ページにはクラスの埋め込み (## クラス/構造体 セクション) を通じて
    表示されるため、ファイル レベルで重複させない。

    すでに perfile の !include ディレクティブがある場合はスキップする。
    !include のパスは docs_dir からの相対パスで記述する
    (postprocess.sh が MARKDOWN_DIR 基準で解決するため)。

    @param[in] class_member_names {group_id: set(member_name)} クラス所属メンバー
    @param[in] classes_dir        Classes ディレクトリ (struct メンバー本文の
                                  !include Classes/...md をインライン解決する。None で無効)
    """
    with open(str(files_md_path), "r", encoding="utf-8") as f:
        content = f.read()

    if "!include {}/perfile__".format(modules_rel) in content:
        print("  [skip] {}: perfile include already exists".format(files_md_path.name))
        return

    files_stem = files_md_path.stem  # 例: libporter__const_8h
    source_basename = files_md_path.name  # 後でキーとして不要、groups から取得済み

    append_lines = []
    generated = []

    for (group_id, title, _) in groups:
        # このファイルに属するメンバー名集合を取得
        _, file_data = group_data[group_id]
        # files_md_path のソースベースネームを特定するため file_data のキーを逆引き
        # (groups の (group_id, title, min_line) はソースベースネーム別に組み立て済み)
        member_names = None
        for src_basename, (names_set, _) in file_data.items():
            if source_basename_to_md_name(src_basename) == files_md_path.name:
                member_names = names_set
                break

        if not member_names:
            continue

        # クラス所属メンバーを除外する (Classes/*.md 側で注入される)
        member_names = member_names - class_member_names.get(group_id, set())
        if not member_names:
            continue

        # Modules/group_id.md をパース
        group_md_path = modules_dir / "{}.md".format(group_id)
        if not group_md_path.exists():
            print("  -> 警告: {} が見つかりません".format(group_md_path))
            continue

        sections = parse_group_md_sections(group_md_path)
        filtered_content = generate_filtered_md(title, sections, member_names, classes_dir)

        # フィルタ済み中間 MD を Modules/ に書き出す
        filtered_name = "perfile__{}__{}.md".format(group_id, files_stem)
        filtered_path = modules_dir / filtered_name
        with open(str(filtered_path), "w", encoding="utf-8", newline="\n") as f:
            f.write(filtered_content)

        include_path = "{}/{}".format(modules_rel, filtered_name)
        append_lines.append("\n!doxyfw-structure-title!## {}\n".format(title))
        append_lines.append("\n!include {}\n".format(include_path))
        generated.append(group_id)

    if not generated:
        return

    with open(str(files_md_path), "a", encoding="utf-8", newline="\n") as f:
        f.write("".join(append_lines))

    print("  [ok] {}: {} inserted (filtered)".format(files_md_path.name, ", ".join(generated)))


def generate_perchild_md(group_md_path):
    """
    子グループの group__*.md を読み込み、**Module:** breadcrumb 行を除去した
    perchild 用コンテンツを生成する。

    フロントマター、HTML コメント、H1 は保持し、postprocess.sh の !include 処理に任せる。
    **Module:** で始まる行とその直後の連続する空行のみ除去する。

    Returns:
        str: perchild ファイルに書き出すコンテンツ
    """
    with open(str(group_md_path), "r", encoding="utf-8") as f:
        lines = f.read().split("\n")

    result = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("**Module:**"):
            # breadcrumb 行をスキップし、直後の連続する空行もスキップ
            i += 1
            while i < n and lines[i] == "":
                i += 1
            continue
        result.append(line)
        i += 1

    return "\n".join(result)


def flatten_descendants(parent_id, hierarchy):
    """
    グループ階層ツリーを DFS で走査し、子孫をフラットなリストとして返す。

    各子のタイトルは hierarchy の (child_id, child_title) タプルから取得する。
    path は直接の子から始まり、孫以降は / 区切りで連結する。
    3 層以上の場合も見出しレベルを増やさず、パス形式で表現する。

    例:
        A → B → D, A → C
        → [("group__B", "B"), ("group__D", "B/D"), ("group__C", "C")]

    Returns:
        list: [(descendant_id, path_title), ...]
    """
    result = []
    visited = set()

    def dfs(node_id, path_prefix):
        for child_id, child_title in hierarchy.get(node_id, []):
            if child_id in visited:
                continue
            visited.add(child_id)
            path = "{}/{}".format(path_prefix, child_title) if path_prefix else child_title
            result.append((child_id, path))
            dfs(child_id, path)

    dfs(parent_id, "")
    return result


def inject_children_into_parent_groups(docs_dir, hierarchy):
    """
    各親グループの Modules ページに子孫グループの内容を挿入する。

    Files 注入の perfile__ パターンと同様に perchild__*.md 中間ファイルを生成し、
    親グループ MD に ## 子グループタイトル セクションと !include ディレクティブを追記する。
    postprocess.sh が !include を heading_offset=1 で展開した後、
    perchild__*.md を削除する。

    3 層以上の階層は ## パス形式の見出しでフラットに表現し、
    見出しレベルの増加を回避する。
    """
    processed = 0

    for parent_id in sorted(hierarchy.keys()):
        descendants = flatten_descendants(parent_id, hierarchy)
        if not descendants:
            continue

        for modules_dir in sorted(docs_dir.rglob("Modules")):
            if not modules_dir.is_dir():
                continue

            parent_md = modules_dir / "{}.md".format(parent_id)
            if not parent_md.exists():
                continue

            modules_rel = str(modules_dir.relative_to(docs_dir))

            content = parent_md.read_text(encoding="utf-8")
            if "!include {}/perchild__".format(modules_rel) in content:
                print("  [skip] {}: perchild include already exists".format(parent_md.name))
                continue

            append_lines = []
            generated = []

            for descendant_id, path_title in descendants:
                child_md = modules_dir / "{}.md".format(descendant_id)
                if not child_md.exists():
                    print("  -> 警告: {} が見つかりません".format(child_md))
                    continue

                perchild_content = generate_perchild_md(child_md)
                perchild_name = "perchild__{}__{}.md".format(parent_id, descendant_id)
                perchild_path = modules_dir / perchild_name
                with open(str(perchild_path), "w", encoding="utf-8", newline="\n") as f:
                    f.write(perchild_content)

                include_path = "{}/{}".format(modules_rel, perchild_name)
                append_lines.append("\n!doxyfw-structure-title!## {}\n".format(path_title))
                append_lines.append("\n!include {}\n".format(include_path))
                generated.append(descendant_id)

            if not generated:
                continue

            with open(str(parent_md), "a", encoding="utf-8", newline="\n") as f:
                f.write("".join(append_lines))

            print("  [ok] {}: {} inserted".format(parent_md.name, ", ".join(generated)))
            processed += 1

    print("[inject-groups] parent groups processed: {}".format(processed))


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

    print("[inject-groups] xml={}  docs={}".format(xml_dir, docs_dir))

    # グループデータ収集:
    #   group_data:     {group_id: (title, {decl_basename: (names_set, min_line)})}
    #   hierarchy:      {parent_id: [(child_id, child_title), ...]}
    #   body_file_data: {bodyfile_path: [(group_id, name, line)]}
    #   member_langs:   {group_id: {name: language}}
    group_data, hierarchy, body_file_data, member_langs = collect_groups(xml_dir)

    if not group_data and not hierarchy:
        print("[inject-groups] Done: 0 file(s) processed")
        return 0

    # メンバー シグネチャ フェンスへの言語付与
    # (perfile / perchild / body のすべての抽出より前に行い、埋め込みへ波及させる)
    if member_langs:
        fix_member_fence_language(docs_dir, member_langs)

    # グループ タイトルのマップ (body / class 注入とログで使用)
    group_titles = {}
    for gid, (title, _) in group_data.items():
        group_titles[gid] = title

    # クラスへ所属するグループ メンバーの収集
    #   class_group_members: {class_compound_id: [(group_id, member_name)]}
    #   class_member_names:  {group_id: set(member_name)} (Files 注入の除外用)
    class_group_members = collect_class_group_members(xml_dir)
    class_member_names = {}
    for entries in class_group_members.values():
        for (gid, name) in entries:
            if gid not in class_member_names:
                class_member_names[gid] = set()
            class_member_names[gid].add(name)

    # ファイルごとのグループリスト構築: {source_basename: [(group_id, title, min_line), ...]}
    file_groups = {}
    for group_id, (title, file_data) in group_data.items():
        for basename, (_, min_line) in file_data.items():
            if basename not in file_groups:
                file_groups[basename] = []
            file_groups[basename].append((group_id, title, min_line))

    # 各ファイルのグループをそのファイル内での出現順にソート
    for basename in file_groups:
        file_groups[basename].sort(key=lambda x: x[2])

    # docs_dir 以下の Files/ ディレクトリを再帰的に探索
    processed = 0
    for files_dir in sorted(docs_dir.rglob("Files")):
        if not files_dir.is_dir():
            continue

        # Modules/ は Files/ と同じ階層 (category ディレクトリ直下) に配置
        modules_dir = files_dir.parent / "Modules"
        if not modules_dir.is_dir():
            continue

        # !include で使う相対パス (docs_dir からの相対)
        modules_rel = str(modules_dir.relative_to(docs_dir))

        # struct メンバー本文の !include Classes/...md 解決用 (同階層の Classes)
        classes_dir = files_dir.parent / "Classes"
        if not classes_dir.is_dir():
            classes_dir = None

        for source_basename, groups in file_groups.items():
            md_name = source_basename_to_md_name(source_basename)
            files_md_path = files_dir / md_name
            if not files_md_path.exists():
                continue

            inject_into_files_md(
                files_md_path, groups, modules_dir, modules_rel, group_data,
                class_member_names, classes_dir
            )
            processed += 1

    print("[inject-groups] Done: {} file(s) processed".format(processed))

    # 定義ファイル (.c ページ) へのグループセクション補完注入
    if body_file_data:
        # bodyfile_path → compound_id に変換する
        file_compound_map = build_file_compound_map(xml_dir)
        body_data = {}
        for body_path, infos in body_file_data.items():
            cid = file_compound_map.get(body_path)
            if cid:
                if cid not in body_data:
                    body_data[cid] = []
                body_data[cid].extend(infos)
        if body_data:
            inject_into_body_files_md(docs_dir, body_data, group_titles)

    # クラス ページへのグループ メンバー補完注入
    if class_group_members:
        inject_into_class_files_md(docs_dir, class_group_members, group_titles)

    # 親グループへの子グループ注入
    if hierarchy:
        inject_children_into_parent_groups(docs_dir, hierarchy)

    return 0


if __name__ == "__main__":
    sys.exit(main())
