#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
inject-groups.py - Files ドキュメントへのグループセクション挿入

Doxygen XML を解析してグループ (@defgroup) を検出し、
グループメンバーの location から対応するソースファイルを特定して、
Files/*.md に ## カテゴリー セクションと !include ディレクティブを挿入する。

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
import glob
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


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


def collect_groups(xml_dir):
    """
    XML ディレクトリからグループ情報と親子関係を収集する。

    各 group__*.xml の compounddef を解析し、すべてのメンバーの location を走査して
    「そのメンバーが定義されたファイル」ごとにグループを紐付ける (多対多マッピング)。
    グループメンバーが複数ファイルにまたがる場合、各ファイルに対して
    そのファイル内のメンバーのみを根拠にグループを関連付ける。

    また <innergroup> 要素から親子関係 (hierarchy) も収集する。

    Returns:
        tuple: (group_data, hierarchy)
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
    """
    group_data = {}
    hierarchy = {}

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

    return group_data, hierarchy


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

        if not in_code_block and line.startswith("## "):
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

        elif not in_code_block and line.startswith("### "):
            # 進行中のメンバーをフラッシュ
            if current_name is not None:
                current_members.append((current_name, current_lines))
            current_name = line[4:].strip()
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


def generate_filtered_md(title, sections, member_names):
    """
    対象ファイルのメンバー名集合でフィルタした中間 MD コンテンツを生成する。

    member_names に含まれるメンバーのみを出力し、別ファイル起源のメンバーを除外する。
    H2/H3 見出しレベルは Doxybook2 出力のまま保持する。
    postprocess.sh の !include 処理が YAML・HTML コメント・H1 を除去し、
    heading_offset=2 でシフトして埋め込む。
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
            out.extend(member_lines)
            out.append("")

    return "\n".join(out)


def inject_into_files_md(files_md_path, groups, modules_dir, modules_rel, group_data):
    """
    Files/*.md の末尾に ## カテゴリー セクションと !include ディレクティブを追記する。

    各グループについて、そのファイルで定義されたメンバーのみを含む
    フィルタ済み中間 MD (perfile__<group_id>__<files_stem>.md) を
    Modules/ に生成してから !include で参照する。

    すでに ## カテゴリー セクションがある場合はスキップする。
    !include のパスは docs_dir からの相対パスで記述する
    (postprocess.sh が MARKDOWN_DIR 基準で解決するため)。
    """
    with open(str(files_md_path), "r", encoding="utf-8") as f:
        content = f.read()

    if "\n## カテゴリー\n" in content:
        print("  [skip] {}: ## カテゴリー section already exists".format(files_md_path.name))
        return

    files_stem = files_md_path.stem  # 例: libporter__const_8h
    source_basename = files_md_path.name  # 後でキーとして不要、groups から取得済み

    append_lines = ["\n## カテゴリー\n"]
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

        # Modules/group_id.md をパース
        group_md_path = modules_dir / "{}.md".format(group_id)
        if not group_md_path.exists():
            print("  -> 警告: {} が見つかりません".format(group_md_path))
            continue

        sections = parse_group_md_sections(group_md_path)
        filtered_content = generate_filtered_md(title, sections, member_names)

        # フィルタ済み中間 MD を Modules/ に書き出す
        filtered_name = "perfile__{}__{}.md".format(group_id, files_stem)
        filtered_path = modules_dir / filtered_name
        with open(str(filtered_path), "w", encoding="utf-8", newline="\n") as f:
            f.write(filtered_content)

        include_path = "{}/{}".format(modules_rel, filtered_name)
        append_lines.append("\n### {}\n".format(title))
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
    親グループ MD に ## カテゴリー セクションと !include ディレクティブを追記する。
    postprocess.sh が !include を heading_offset=2 で展開した後、
    perchild__*.md を削除する。

    3 層以上の階層は ### パス形式の見出しでフラットに表現し、
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

            content = parent_md.read_text(encoding="utf-8")
            if "\n## カテゴリー\n" in content:
                print("  [skip] {}: ## カテゴリー section already exists".format(parent_md.name))
                continue

            modules_rel = str(modules_dir.relative_to(docs_dir))
            append_lines = ["\n## カテゴリー\n"]
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
                append_lines.append("\n### {}\n".format(path_title))
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

    # グループデータ収集: ({group_id: (title, {basename: (names_set, min_line)})}, hierarchy)
    group_data, hierarchy = collect_groups(xml_dir)

    if not group_data and not hierarchy:
        print("[inject-groups] Done: 0 file(s) processed")
        return 0

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

        for source_basename, groups in file_groups.items():
            md_name = source_basename_to_md_name(source_basename)
            files_md_path = files_dir / md_name
            if not files_md_path.exists():
                continue

            inject_into_files_md(
                files_md_path, groups, modules_dir, modules_rel, group_data
            )
            processed += 1

    print("[inject-groups] Done: {} file(s) processed".format(processed))

    # 親グループへの子グループ注入
    if hierarchy:
        inject_children_into_parent_groups(docs_dir, hierarchy)

    return 0


if __name__ == "__main__":
    sys.exit(main())
