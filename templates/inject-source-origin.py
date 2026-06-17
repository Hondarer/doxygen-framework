#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
inject-source-origin.py - Files/ 配下の各 md に元ソースの origin パスを埋め込む

Doxybook2 が生成する Files/ 配下の md は、その md 自身のパス (Files/ からの相対) が
Doxygen の INPUT 相対ソース パスと一致する。Doxygen 実行ディレクトリ DOXYGEN_RUNDIR を
基準に実在判定することで、プログラム ソースと Markdown ソースを統一規則で origin に解決する。

候補規則 (Files/ 配下相対パス P に対して):
  C1 = P の末尾 .md を除去   (プログラム/ヘッダー用、例 include/calc.h.md -> include/calc.h)
  C2 = P そのまま            (Markdown ソース用、例 src/markdown_sample.md)
  DOXYGEN_RUNDIR/C1 が実在すれば origin=C1、無ければ DOXYGEN_RUNDIR/C2 が実在すれば origin=C2

解決した origin を WORKSPACE_DIR 相対パスに正規化し、フロントマター キー git-origin として
埋め込む。docsfw 側はこのヒントを使って origin への Git リンクを表示する。

トップレベル Files/README.md は Doxybook2 が生成する `ファイルの一覧` 索引であり実ソースでは
ないため除外する。サブフォルダーの README.md (例 Files/src/image/README.md) は実ソースなので対象。

使用方法:
    python3 inject-source-origin.py <markdown_dir> <doxygen_rundir> <workspace_dir>
"""

import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def resolve_origin(rundir, rel_under_files):
    """
    Files/ 配下相対パスから元ソースの絶対パスを解決する。

    @param[in] rundir            Doxygen 実行ディレクトリの絶対パス
    @param[in] rel_under_files   Files/ からの相対パス (POSIX 区切り)

    @return 元ソースの絶対パス文字列。解決できなければ None
    """
    candidates = []
    if rel_under_files.endswith(".md"):
        candidates.append(rel_under_files[:-3])
    candidates.append(rel_under_files)

    for cand in candidates:
        abs_cand = os.path.normpath(os.path.join(rundir, cand))
        if os.path.isfile(abs_cand):
            return abs_cand
    return None


def inject_frontmatter(md_path, key, value):
    """
    md の先頭フロントマター ブロックへ `key: "value"` を挿入する。

    既存の同名キーがあれば置換する。フロントマターが無ければ新規生成する。

    @param[in] md_path  対象 md ファイルのパス
    @param[in] key      挿入するキー名
    @param[in] value    挿入する値 (文字列)
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


def inject_source_origin(markdown_dir, rundir, workspace_dir):
    """
    Files/ 配下の各 md に git-origin フロントマターを埋め込む。

    @param[in] markdown_dir   doxybook2 出力ディレクトリ
    @param[in] rundir         Doxygen 実行ディレクトリ
    @param[in] workspace_dir  ワークスペース ルート
    """
    files_dir = Path(markdown_dir) / "Files"
    if not files_dir.is_dir():
        print("Files/ が無いため git-origin 注入をスキップします: {0}".format(files_dir))
        return

    if not rundir or not os.path.isdir(rundir):
        print("DOXYGEN_RUNDIR が解決できないため git-origin 注入をスキップします: {0}".format(rundir))
        return

    rundir = os.path.abspath(rundir)
    workspace_dir = os.path.abspath(workspace_dir)

    count = 0
    for md_path in sorted(files_dir.rglob("*.md")):
        rel_under_files = md_path.relative_to(files_dir).as_posix()

        # トップレベル Files/README.md (ファイルの一覧 索引) は除外する
        if rel_under_files == "README.md":
            continue

        abs_origin = resolve_origin(rundir, rel_under_files)
        if abs_origin is None:
            continue

        ws_rel = os.path.relpath(abs_origin, workspace_dir).replace("\\", "/")
        inject_frontmatter(str(md_path), "git-origin", ws_rel)
        count += 1
        print("  git-origin: Files/{0} -> {1}".format(rel_under_files, ws_rel))

    print("git-origin を {0} 件の Files md に注入しました。".format(count))


def main():
    """エントリ ポイント。"""
    if len(sys.argv) != 4:
        print("使用方法: inject-source-origin.py <markdown_dir> <doxygen_rundir> <workspace_dir>",
              file=sys.stderr)
        sys.exit(1)

    markdown_dir = sys.argv[1]
    rundir = sys.argv[2]
    workspace_dir = sys.argv[3]

    if not os.path.isdir(markdown_dir):
        print("エラー: ディレクトリが存在しません: {0}".format(markdown_dir), file=sys.stderr)
        sys.exit(1)

    inject_source_origin(markdown_dir, rundir, workspace_dir)


if __name__ == "__main__":
    main()
