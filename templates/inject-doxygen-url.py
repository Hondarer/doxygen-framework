#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
inject-doxygen-url.py - Doxybook2 出力 md に対応 Doxygen HTML の URL を埋め込む

Doxygen tag file の compound 情報から、Doxybook2 が生成した Files/、Modules/、
Classes/、Namespaces/ 配下 Markdown と Doxygen HTML の単一ページを対応づける。
解決した URL は workspace ルート相対パスとして front matter キー doxygen-page-url に書き込む。

使用方法:
    python3 inject-doxygen-url.py <markdown_dir> <tagfile_path> <doxygen_html_root> <workspace_dir>
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def normalize_key(path):
    """比較用にパス区切りを POSIX 形式へ正規化する。"""
    return path.replace("\\", "/").strip("/")


def add_unique(mapping, key, value):
    """同一キーが異なる値を指す場合は衝突として None を保持する。"""
    key = normalize_key(key)
    if not key:
        return
    if key in mapping and mapping[key] != value:
        mapping[key] = None
    else:
        mapping[key] = value


def add_path_suffixes(mapping, path, value):
    """絶対パスと相対パスの差を吸収するため、全 suffix を候補にする。"""
    key = normalize_key(path)
    if not key:
        return

    parts = [part for part in key.split("/") if part]
    for i in range(len(parts)):
        add_unique(mapping, "/".join(parts[i:]), value)


def parse_tagfile(tagfile_path):
    """Doxygen tag file から file/page/compound の対応マップを構築する。"""
    tree = ET.parse(tagfile_path)
    root = tree.getroot()
    file_map = {}
    page_map = {}
    # Modules/Classes/Namespaces などは md ファイル名 = HTML ファイル名なので
    # basename 集合だけ持てば解決できる。
    compound_html_set = set()

    compound_kinds = {"group", "class", "struct", "namespace", "union", "interface"}

    for compound in root.findall("compound"):
        kind = compound.get("kind")
        name = compound.findtext("name") or ""
        filename = compound.findtext("filename") or ""
        if not name or not filename:
            continue

        if kind == "file":
            path = compound.findtext("path") or ""
            add_path_suffixes(file_map, os.path.join(path, name), filename)
            add_unique(file_map, name, filename)
        elif kind == "page":
            add_unique(page_map, name, filename)
        elif kind in compound_kinds:
            compound_html_set.add(os.path.basename(filename))

    return file_map, page_map, compound_html_set


def inject_frontmatter(md_path, key, value):
    """
    md の先頭 front matter ブロックへ `key: "value"` を挿入する。

    既存の同名キーがあれば置換する。front matter が無ければ新規生成する。
    """
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_line = '{0}: "{1}"\n'.format(key, value)

    if lines and lines[0].rstrip("\r\n") == "---":
        close_index = None
        for i in range(1, len(lines)):
            if lines[i].rstrip("\r\n") == "---":
                close_index = i
                break
        if close_index is not None:
            body = lines[1:close_index]
            body = [ln for ln in body if not ln.lstrip().startswith(key + ":")]
            body.append(new_line)
            lines = [lines[0]] + body + lines[close_index:]
        else:
            lines = ["---\n", new_line, "---\n"] + lines
    else:
        lines = ["---\n", new_line, "---\n"] + lines

    with open(md_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def resolve_doxygen_filename(rel_under_files, file_map, page_map):
    """Files/ 配下相対パスから Doxygen HTML ファイル名を解決する。"""
    candidates = []
    if rel_under_files.endswith(".md"):
        candidates.append(rel_under_files[:-3])
    candidates.append(rel_under_files)

    for candidate in candidates:
        filename = file_map.get(normalize_key(candidate))
        if filename:
            return filename

    stem = Path(rel_under_files).stem
    page_candidates = ["md_" + stem]
    rel_no_ext = rel_under_files[:-3] if rel_under_files.endswith(".md") else rel_under_files
    page_candidates.append("md_" + normalize_key(rel_no_ext).replace("/", "_"))

    for candidate in page_candidates:
        filename = page_map.get(candidate)
        if filename:
            return filename

    return None


def inject_doxygen_urls(markdown_dir, tagfile_path, doxygen_html_root, workspace_dir):
    """Doxybook2 出力 md に doxygen-page-url front matter を埋め込む。"""
    markdown_dir_path = Path(markdown_dir)
    files_dir = markdown_dir_path / "Files"
    has_files = files_dir.is_dir()

    # basename = HTML ファイル名そのもの。
    # 例: Modules/group__CALC__PUBLIC__API.md → group__CALC__PUBLIC__API.html
    compound_dirs = ["Modules", "Classes", "Namespaces"]
    compound_dir_paths = [(name, markdown_dir_path / name) for name in compound_dirs]
    has_compound = any(p.is_dir() for _, p in compound_dir_paths)

    if not has_files and not has_compound:
        print("対象ディレクトリが無いため doxygen-page-url 注入をスキップします: {0}".format(markdown_dir))
        return

    if not os.path.isfile(tagfile_path):
        print("Doxygen tag file が無いため doxygen-page-url 注入をスキップします: {0}".format(tagfile_path))
        return

    file_map, page_map, compound_html_set = parse_tagfile(tagfile_path)
    workspace_dir = os.path.abspath(workspace_dir)
    doxygen_html_root = os.path.abspath(doxygen_html_root)

    count = 0

    if has_files:
        for md_path in sorted(files_dir.rglob("*.md")):
            rel_under_files = md_path.relative_to(files_dir).as_posix()

            # トップレベル Files/README.md はファイル一覧の索引であり、対応ソースではない。
            if rel_under_files == "README.md":
                continue

            filename = resolve_doxygen_filename(rel_under_files, file_map, page_map)
            if filename is None:
                continue

            html_path = os.path.join(doxygen_html_root, filename)
            ws_rel = os.path.relpath(html_path, workspace_dir).replace("\\", "/")
            inject_frontmatter(str(md_path), "doxygen-page-url", ws_rel)
            count += 1
            print("  doxygen-page-url: Files/{0} -> {1}".format(rel_under_files, ws_rel))

    for dir_name, dir_path in compound_dir_paths:
        if not dir_path.is_dir():
            continue
        for md_path in sorted(dir_path.rglob("*.md")):
            rel_under_dir = md_path.relative_to(dir_path).as_posix()
            # 各ディレクトリの README.md は索引であり、対応 HTML を持たない。
            if rel_under_dir == "README.md":
                continue

            html_basename = md_path.stem + ".html"
            if html_basename not in compound_html_set:
                continue

            html_path = os.path.join(doxygen_html_root, html_basename)
            ws_rel = os.path.relpath(html_path, workspace_dir).replace("\\", "/")
            inject_frontmatter(str(md_path), "doxygen-page-url", ws_rel)
            count += 1
            print("  doxygen-page-url: {0}/{1} -> {2}".format(dir_name, rel_under_dir, ws_rel))

    print("doxygen-page-url を {0} 件の md に注入しました。".format(count))


def main():
    """エントリ ポイント。"""
    if len(sys.argv) != 5:
        print(
            "使用方法: inject-doxygen-url.py <markdown_dir> <tagfile_path> <doxygen_html_root> <workspace_dir>",
            file=sys.stderr,
        )
        sys.exit(1)

    markdown_dir = sys.argv[1]
    tagfile_path = sys.argv[2]
    doxygen_html_root = sys.argv[3]
    workspace_dir = sys.argv[4]

    if not os.path.isdir(markdown_dir):
        print("エラー: ディレクトリが存在しません: {0}".format(markdown_dir), file=sys.stderr)
        sys.exit(1)

    inject_doxygen_urls(markdown_dir, tagfile_path, doxygen_html_root, workspace_dir)


if __name__ == "__main__":
    main()