#!/usr/bin/env python3
"""
Doxygen コメント セパレータ チェック・修正ツール

機能:
  - @file を含まない Doxygen コメントからセパレータ行を検出
  - --dry-run オプションで修正内容を表示 (実際には修正しない)
  - --fix オプションでセパレータ行を削除

使用例:
  check-doxygen-separators.py --check app
  check-doxygen-separators.py --dry-run app
  check-doxygen-separators.py --fix app
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
}

SEPARATOR_RE = re.compile(r"^\s*\*\s*\*{10,}\s*$")
DOXYGEN_START_RE = re.compile(r"/\*\*")
DOXYGEN_ONE_LINE_RE = re.compile(r"/\*\*.*\*/")


@dataclass(frozen=True)
class Issue:
    block_start_line: int
    separator_lines: tuple[int, ...]


def is_source_file(path):
    """チェック対象のソース ファイルかどうかを返します。"""
    return path.is_file() and path.suffix in SOURCE_EXTENSIONS


def filesystem_files(paths):
    """ファイル システムからチェック対象ファイルを列挙します。"""
    skip_dirs = {
        ".git",
        ".vs",
        "bin",
        "Debug",
        "Release",
        "node_modules",
        "obj",
        "pages",
    }

    files = []
    for path in paths:
        if path.is_file():
            if is_source_file(path):
                files.append(path)
            continue

        if not path.is_dir():
            continue

        for root, dirs, filenames in os.walk(path):
            dirs[:] = [name for name in dirs if name not in skip_dirs]
            root_path = Path(root)
            if "docs" in root_path.parts and "doxybook2" in root_path.parts:
                continue

            for filename in filenames:
                candidate = root_path / filename
                if is_source_file(candidate):
                    files.append(candidate)

    return files


def collect_files(paths):
    """チェック対象ファイルを重複なしで列挙します。"""
    files = filesystem_files(paths)
    return sorted(set(files))


def scan_lines(lines):
    """Doxygen コメント内の不要なセパレータ行を検出します。"""
    issues = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not DOXYGEN_START_RE.search(line):
            index += 1
            continue

        if DOXYGEN_ONE_LINE_RE.search(line):
            index += 1
            continue

        block_start = index
        block_end = index
        while block_end < len(lines):
            if "*/" in lines[block_end]:
                break
            block_end += 1

        if block_end >= len(lines):
            index += 1
            continue

        block_lines = lines[block_start : block_end + 1]
        if any("@file" in block_line for block_line in block_lines):
            index = block_end + 1
            continue

        separator_lines = tuple(
            line_number
            for line_number, block_line in enumerate(block_lines, start=block_start + 1)
            if SEPARATOR_RE.match(block_line)
        )
        if separator_lines:
            issues.append(
                Issue(
                    block_start_line=block_start + 1,
                    separator_lines=separator_lines,
                )
            )

        index = block_end + 1

    return issues


def read_lines(path):
    """UTF-8 テキストとしてファイルを読み込みます。"""
    try:
        with path.open("r", encoding="utf-8") as file:
            return file.readlines()
    except (OSError, UnicodeDecodeError) as error:
        print(f"警告: ファイルを読み込めません: {path} ({error})", file=sys.stderr)
        return None


def remove_separator_lines(lines, issues):
    """検出済みのセパレータ行を削除した行リストを返します。"""
    remove_lines = {
        line_number
        for issue in issues
        for line_number in issue.separator_lines
    }

    return [
        line
        for line_number, line in enumerate(lines, start=1)
        if line_number not in remove_lines
    ]


def report_issue(path, issue, dry_run):
    """検出内容を出力します。"""
    action = "削除予定" if dry_run else "検出"
    for line_number in issue.separator_lines:
        print(
            f"{path}:{line_number}: {action}: "
            f"@file 以外の Doxygen コメントにセパレータ行があります "
            f"(block start: {issue.block_start_line})"
        )


def process_file(path, mode):
    """1 ファイルをチェックまたは修正します。"""
    lines = read_lines(path)
    if lines is None:
        return 0

    issues = scan_lines(lines)
    if not issues:
        return 0

    if mode in {"check", "dry-run"}:
        for issue in issues:
            report_issue(path, issue, mode == "dry-run")
        return sum(len(issue.separator_lines) for issue in issues)

    fixed_lines = remove_separator_lines(lines, issues)
    try:
        with path.open("w", encoding="utf-8", newline="") as file:
            file.writelines(fixed_lines)
    except OSError as error:
        print(f"エラー: ファイルを書き込めません: {path} ({error})", file=sys.stderr)
        return sum(len(issue.separator_lines) for issue in issues)

    removed_count = sum(len(issue.separator_lines) for issue in issues)
    print(f"修正: {path} ({removed_count} 行削除)")
    return removed_count


def parse_args():
    """コマンドライン引数を解析します。"""
    parser = argparse.ArgumentParser(
        description="@file 以外の Doxygen コメントからセパレータ行を検出・削除します。"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--check",
        action="store_const",
        const="check",
        dest="mode",
        help="チェックのみ行います (既定)。",
    )
    mode_group.add_argument(
        "--dry-run",
        action="store_const",
        const="dry-run",
        dest="mode",
        help="修正内容を表示します。ファイルは変更しません。",
    )
    mode_group.add_argument(
        "--fix",
        action="store_const",
        const="fix",
        dest="mode",
        help="セパレータ行を削除します。",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="チェック対象のファイルまたはディレクトリ。",
    )
    parser.set_defaults(mode="check")
    return parser.parse_args()


def main():
    """エントリーポイント。"""
    args = parse_args()
    files = collect_files(args.paths)
    if not files:
        print("対象ファイルはありません。")
        return 0

    total = 0
    for path in files:
        total += process_file(path, args.mode)

    if args.mode == "fix":
        print(f"完了: {total} 行のセパレータを削除しました。")
        return 0

    if total == 0:
        print("OK: @file 以外の Doxygen コメントにセパレータ行はありません。")
        return 0

    print(f"NG: {total} 行のセパレータが残っています。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
