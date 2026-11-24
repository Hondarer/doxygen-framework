#!/usr/bin/env python3
"""
Doxygen コメント内の末尾が奇数個のバックスラッシュで終わるコード スパン検出ツール

機能:
  - Doxygen コメント (/** ... */, /*! ... */, ///, //!) の中のインライン コード スパンを走査
  - 末尾のバックスラッシュが奇数個のコード スパンを検出し、行番号つきで報告
  - 検出された場合は終了コード 1 を返す

背景:
  Doxygen 1.12.0 以降では、コード スパンの末尾へ内部コマンド \\endiskip を挿入する。
  コード スパンの末尾が奇数個のバックスラッシュだと、直後の \\endiskip の先頭の \\ と
  結合してエスケープされたバックスラッシュと文字列 endiskip として出力へ漏れる。
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

SKIP_DIRS = {
    ".git",
    ".vs",
    "bin",
    "Debug",
    "Release",
    "node_modules",
    "obj",
    "pages",
}

BLOCK_VERBATIM_START_RE = re.compile(
    r"^\s*([@\\])(code|verbatim|mermaid|startuml)(?![A-Za-z0-9_])"
)
FENCE_RE = re.compile(r"^\s*(~~~+|```+)")


@dataclass(frozen=True)
class Issue:
    """検出されたコード スパンの 1 件を表します。"""

    line_number: int
    code_span: str


def is_source_file(path):
    """チェック対象のソース ファイルかどうかを返します。"""
    return path.is_file() and path.suffix in SOURCE_EXTENSIONS


def is_generated_doxybook2_dir(root_path):
    """Doxybook2 の生成物ディレクトリ配下かどうかを返します。"""
    parts = root_path.parts
    for idx, part in enumerate(parts):
        if part == "docs" and idx + 1 < len(parts) and parts[idx + 1].startswith("doxybook2"):
            return True
    return False


def filesystem_files(paths):
    """ファイル システムからチェック対象ファイルを列挙します。"""
    files = []
    for path in paths:
        if path.is_file():
            if is_source_file(path):
                files.append(path)
            continue

        if not path.is_dir():
            continue

        for root, dirs, filenames in os.walk(path):
            dirs[:] = [name for name in sorted(dirs) if name not in SKIP_DIRS]
            root_path = Path(root)
            if is_generated_doxybook2_dir(root_path):
                continue

            for filename in sorted(filenames):
                candidate = root_path / filename
                if is_source_file(candidate):
                    files.append(candidate)

    return files


def collect_files(paths):
    """チェック対象ファイルを重複なしで列挙します。"""
    return sorted(set(filesystem_files(paths)))


def strip_block_comment_line(line_text, is_first, is_last):
    """ブロック コメント内の 1 行から外枠記号を除いた本文を返します。"""
    text = line_text
    if is_first:
        if text.startswith("/**<") or text.startswith("/*!<"):
            text = text[4:]
        elif text.startswith("/**") or text.startswith("/*!"):
            text = text[3:]
    if is_last:
        if text.endswith("*/"):
            text = text[:-2]
    if not is_first:
        match = re.match(r"^[ \t]*\*(?!/)", text)
        if match:
            text = text[match.end():]
    return text


def strip_line_comment(line_text):
    """行コメント (///, //!) から先頭のコメント記号を除いた本文を返します。"""
    if line_text.startswith("///<") or line_text.startswith("//!<"):
        return line_text[4:]
    if line_text.startswith("///") or line_text.startswith("//!"):
        return line_text[3:]
    return line_text


def extract_doxygen_blocks(text):
    """C/C++ ソース文字列から Doxygen コメント ブロックの行リストを抽出します。

    各要素は (line_number, body_text) のリストです。
    文字列リテラルや非 Doxygen コメント内の `/**` 等は無視します。
    """
    blocks = []
    n = len(text)
    i = 0
    line_num = 1
    pending_line_block = []

    def flush_line_block():
        nonlocal pending_line_block
        if pending_line_block:
            blocks.append(pending_line_block)
            pending_line_block = []

    while i < n:
        ch = text[i]

        # 文字列・文字リテラルをスキップする
        if ch in ('"', "'"):
            flush_line_block()
            quote = ch
            i += 1
            while i < n:
                c = text[i]
                if c == "\\":
                    if i + 1 < n:
                        if text[i + 1] == "\n":
                            line_num += 1
                        i += 2
                    else:
                        i += 1
                    continue
                if c == "\n":
                    line_num += 1
                    i += 1
                    break
                if c == quote:
                    i += 1
                    break
                i += 1
            continue

        # 行コメントを処理する
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            end = text.find("\n", i)
            if end == -1:
                end = n
            comment_line = text[i:end]
            is_doxy_line = (
                comment_line.startswith("//!")
                or (comment_line.startswith("///") and not comment_line.startswith("////"))
            )
            if is_doxy_line:
                pending_line_block.append((line_num, strip_line_comment(comment_line)))
            else:
                flush_line_block()
            if end < n:
                line_num += 1
                i = end + 1
            else:
                i = n
            continue

        # ブロック コメントを処理する
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            flush_line_block()
            end = text.find("*/", i + 2)
            if end == -1:
                end = n
                raw_comment = text[i:end]
                next_i = n
            else:
                raw_comment = text[i : end + 2]
                next_i = end + 2

            is_doxy_block = (
                (raw_comment.startswith("/**") and raw_comment != "/**/")
                or raw_comment.startswith("/*!")
            )
            raw_lines = raw_comment.split("\n")
            if is_doxy_block:
                block = []
                for idx, raw_line in enumerate(raw_lines):
                    body = strip_block_comment_line(
                        raw_line,
                        is_first=(idx == 0),
                        is_last=(idx == len(raw_lines) - 1 and end != n),
                    )
                    block.append((line_num + idx, body))
                blocks.append(block)

            line_num += len(raw_lines) - 1
            i = next_i
            continue

        if ch == "\n":
            line_num += 1
            i += 1
            # 空行を挟むと /// ブロックは分かれるが、先頭の空白行だけでは継続を許す
            # ただし次の非空白文字が // でなければ flush する
            j = i
            while j < n and text[j] in (" ", "\t"):
                j += 1
            if j >= n or not text.startswith("//", j):
                flush_line_block()
            continue

        if ch not in (" ", "\t", "\r"):
            flush_line_block()
        i += 1

    flush_line_block()
    return blocks


def filter_non_prose_lines(block):
    """@code / @verbatim / @mermaid / @startuml / ~~~ などの逐語・図ブロックを除外します。"""
    prose_lines = []
    end_cmd_re = None
    fence_char = None
    fence_len = 0

    for line_no, text in block:
        if end_cmd_re is not None:
            if end_cmd_re.search(text):
                end_cmd_re = None
            prose_lines.append((line_no, ""))
            continue

        if fence_char is not None:
            stripped = text.lstrip()
            if stripped.startswith(fence_char * fence_len) and stripped.strip(fence_char + " \t") == "":
                fence_char = None
                fence_len = 0
            prose_lines.append((line_no, ""))
            continue

        cmd_match = BLOCK_VERBATIM_START_RE.match(text)
        if cmd_match:
            cmd = cmd_match.group(2)
            end_name = "end" + cmd if cmd != "startuml" else "enduml"
            end_cmd_re = re.compile(rf"[@\\]{end_name}(?![A-Za-z0-9_])")
            if end_cmd_re.search(text[cmd_match.end():]):
                end_cmd_re = None
            prose_lines.append((line_no, ""))
            continue

        fence_match = FENCE_RE.match(text)
        if fence_match:
            fence = fence_match.group(1)
            fence_char = fence[0]
            fence_len = len(fence)
            prose_lines.append((line_no, ""))
            continue

        prose_lines.append((line_no, text))

    return prose_lines


def normalize_code_span_content(content, delim_len):
    """CommonMark の複数バッククォート空白除去に合わせてコード スパンの中身を返します。"""
    if (
        delim_len >= 2
        and len(content) >= 2
        and content[0] == " "
        and content[-1] == " "
        and content.strip(" ") != ""
    ):
        return content[1:-1]
    return content


def has_odd_trailing_backslashes(content):
    """文字列末尾の連続バックスラッシュが奇数個かどうかを返します。"""
    trailing = len(content) - len(content.rstrip("\\"))
    return (trailing % 2) == 1


def scan_paragraph(chars_with_lines):
    """1 つの段落 (文字と行番号の並び) から不正なコード スパンを検出します。"""
    issues = []
    n = len(chars_with_lines)
    i = 0

    while i < n:
        ch, start_line = chars_with_lines[i]
        if ch == "\\":
            if i + 1 < n and chars_with_lines[i + 1][0] in ("\\", "`"):
                i += 2
            else:
                i += 1
            continue

        if ch != "`":
            i += 1
            continue

        # 開きバッククォート列の長さを数える
        j = i
        while j < n and chars_with_lines[j][0] == "`":
            j += 1
        delim_len = j - i

        # 同じ長さの閉じバッククォート列を探す
        k = j
        found_close = False
        while k < n:
            if chars_with_lines[k][0] != "`":
                k += 1
                continue
            m = k
            while m < n and chars_with_lines[m][0] == "`":
                m += 1
            if (m - k) == delim_len:
                raw_content = "".join(c for c, _ in chars_with_lines[j:k])
                content = normalize_code_span_content(raw_content, delim_len)
                if has_odd_trailing_backslashes(content):
                    span_text = ("`" * delim_len) + raw_content + ("`" * delim_len)
                    issues.append(Issue(line_number=start_line, code_span=span_text))
                i = m
                found_close = True
                break
            k = m

        if not found_close:
            i = j

    return issues


def scan_text(text):
    """C/C++ ソース文字列を走査し、検出した問題のリストを返します。"""
    issues = []
    for block in extract_doxygen_blocks(text):
        prose_lines = filter_non_prose_lines(block)
        paragraph_chars = []

        def flush_paragraph():
            nonlocal paragraph_chars
            if paragraph_chars:
                issues.extend(scan_paragraph(paragraph_chars))
                paragraph_chars = []

        for line_no, line_text in prose_lines:
            stripped = line_text.strip()
            if stripped == "":
                flush_paragraph()
                continue
            if paragraph_chars:
                paragraph_chars.append((" ", line_no))
            for ch in line_text:
                paragraph_chars.append((ch, line_no))

        flush_paragraph()

    return issues


def read_text(path):
    """UTF-8 テキストとしてファイルを読み込みます。"""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"警告: ファイルを読み込めません: {path} ({error})", file=sys.stderr)
        return None


def parse_args():
    """コマンド ライン引数を解析します。"""
    parser = argparse.ArgumentParser(
        description="Doxygen コメント内で末尾のバックスラッシュが奇数個のコード スパンを検出します。"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="チェックのみ行います (既定)。",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="チェック対象のファイルまたはディレクトリ。",
    )
    return parser.parse_args()


def main():
    """エントリー ポイント。"""
    args = parse_args()
    missing = [path for path in args.paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"エラー: 対象が見つかりません: {path}", file=sys.stderr)
        return 1

    files = collect_files(args.paths)
    if not files:
        print("対象ファイルはありません。")
        return 0

    total = 0
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        issues = scan_text(text)
        for issue in issues:
            print(
                f"{path}:{issue.line_number}: 検出: "
                f"コード スパンの末尾のバックスラッシュが奇数個です ({issue.code_span})"
            )
            total += 1

    if total == 0:
        print(
            f"OK: {len(files)} ファイルを検査し、末尾のバックスラッシュが奇数個のコード スパンはありません。"
        )
        return 0

    print(f"NG: {total} 件の該当コード スパンを検出しました。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
