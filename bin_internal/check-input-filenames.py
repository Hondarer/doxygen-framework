#!/usr/bin/env python3
"""Doxygen の入力ファイルのパスが ASCII だけで構成されているかを検査する。

使い方: check-input-filenames.py <Doxyfile> <Doxygen の実行基準ディレクトリ>

Doxygen の制約:
    Doxygen は INPUT_FILTER を起動する際、UTF-8 のファイル パスを連結した
    コマンド文字列を、Windows (MSVC ビルド) ではワイド文字版ではなく ANSI 版の
    _popen へそのまま渡す。C ランタイムはこのバイト列を ANSI コード ページ
    (日本語環境では CP932) として解釈するため、パスに非 ASCII 文字を含むと
    次のいずれかになる。
      - CP932 として不正なバイト列 (例: "あ", "機能仕様表") の場合は、Doxygen が
        0xC0000409 (MSYS の bash では終了コード 127) で強制終了し、
        標準出力のバッファーも失われる。
      - CP932 として解釈できるバイト列 (例: "表" は "陦ｨ" になる) の場合は、
        フィルターが文字化けしたパスを開けずに失敗し、Doxygen は空の入力として
        警告なしに処理を続ける。生成物からそのファイルの内容が欠落する。
    see: https://github.com/doxygen/doxygen/blob/Release_1_18_0/src/util.cpp#L5622-L5624
    see: https://github.com/doxygen/doxygen/blob/Release_1_18_0/src/portable.cpp#L479-L486
    see: https://learn.microsoft.com/cpp/c-runtime-library/reference/popen-wpopen

    Linux では発生しないが、Linux で通る入力が Windows で失敗しないよう、
    OS を問わず同じ条件で検査する。

入力ファイルの列挙は Doxygen の INPUT、FILE_PATTERNS、RECURSIVE、EXCLUDE、
EXCLUDE_PATTERNS の解釈に合わせる。
see: https://www.doxygen.nl/manual/config.html#cfg_input
"""

import fnmatch
import os
import re
import sys

LIST_KEYS = ("INPUT", "FILE_PATTERNS", "RECURSIVE", "EXCLUDE", "EXCLUDE_PATTERNS")


def reconfigure_stream(stream):
    # Windows の標準エラー出力は ANSI になるため、日本語のパスで UnicodeEncodeError にならないよう固定する
    try:
        stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def expand_env(value):
    # Doxyfile の $(NAME) は環境変数で置き換えられる
    return re.sub(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)", lambda m: os.environ.get(m.group(1), ""), value)


def split_values(value):
    # 二重引用符で囲まれた値は空白を含められる。それ以外は空白またはカンマで区切る
    tokens = []
    for quoted, plain in re.findall(r'"((?:[^"\\]|\\.)*)"|([^\s,"]+)', value):
        token = quoted if quoted else plain
        if token:
            tokens.append(expand_env(token))
    return tokens


def parse_doxyfile(path):
    """後勝ちで評価した LIST_KEYS の値を返す。"""
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    logical = []
    buffer = ""
    for line in lines:
        if not buffer and line.lstrip().startswith("#"):
            continue
        if line.rstrip().endswith("\\"):
            buffer += line.rstrip()[:-1] + " "
            continue
        logical.append(buffer + line)
        buffer = ""
    if buffer:
        logical.append(buffer)

    values = {key: [] for key in LIST_KEYS}
    for line in logical:
        match = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*(\+?=)(.*)$", line)
        if not match or match.group(1) not in values:
            continue
        key, operator, value = match.groups()
        tokens = split_values(value)
        if operator == "+=":
            values[key].extend(tokens)
        else:
            values[key] = tokens
    return values


def pattern_match(file_path, patterns):
    # Doxygen はファイル名、指定どおりのパス、絶対パスのいずれかが一致すれば一致とみなす。
    # fnmatch.fnmatch は Windows で大文字小文字と区切り文字を正規化するため、
    # Doxygen の CASE_SENSE_NAMES の既定 (Windows では区別しない) と一致する。
    candidates = (os.path.basename(file_path), file_path, os.path.abspath(file_path))
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns for name in candidates)


def list_input_files(values):
    recursive = (values["RECURSIVE"] or ["NO"])[0].upper() == "YES"
    file_patterns = values["FILE_PATTERNS"]
    exclude_patterns = values["EXCLUDE_PATTERNS"]
    excludes = {os.path.normcase(os.path.realpath(entry)) for entry in values["EXCLUDE"]}

    def is_excluded(path):
        return os.path.normcase(os.path.realpath(path)) in excludes

    files = []
    for entry in values["INPUT"]:
        if is_excluded(entry):
            continue
        if os.path.isfile(entry):
            files.append(entry)
            continue
        if not os.path.isdir(entry):
            continue
        for dir_path, dir_names, file_names in os.walk(entry):
            if recursive:
                dir_names[:] = [
                    name for name in dir_names
                    if not is_excluded(os.path.join(dir_path, name))
                    and not pattern_match(os.path.join(dir_path, name).replace("\\", "/"), exclude_patterns)
                ]
            else:
                dir_names[:] = []
            for name in file_names:
                path = os.path.join(dir_path, name).replace("\\", "/")
                if file_patterns and not pattern_match(path, file_patterns):
                    continue
                if pattern_match(path, exclude_patterns) or is_excluded(path):
                    continue
                files.append(path)
    return files


def main(argv):
    reconfigure_stream(sys.stdout)
    reconfigure_stream(sys.stderr)
    if len(argv) != 3:
        print("usage: check-input-filenames.py <Doxyfile> <run-dir>", file=sys.stderr)
        return 2

    values = parse_doxyfile(argv[1])
    os.chdir(argv[2])

    # Doxygen はフィルターへ絶対パスを渡すため、実行基準ディレクトリ側の非 ASCII も対象とする。
    # 8.3 形式の短い名前では非 ASCII が隠れるため、realpath で長い形式にそろえて判定する。
    offending = sorted({
        os.path.realpath(path).replace("\\", "/")
        for path in list_input_files(values)
        if not os.path.realpath(path).isascii()
    })
    if not offending:
        return 0

    print("ERROR: Doxygen input paths must contain only ASCII characters.", file=sys.stderr)
    print("Doxygen passes input paths to INPUT_FILTER through the ANSI code page on Windows,", file=sys.stderr)
    print("so a non-ASCII path crashes Doxygen or silently drops the file content.", file=sys.stderr)
    print("Rename or exclude the following files:", file=sys.stderr)
    for path in offending:
        print("  " + path, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
