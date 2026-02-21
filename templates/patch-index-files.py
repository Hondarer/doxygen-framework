#!/usr/bin/env python3
"""patch-index-files.py - index_files.md の表示名からパスプレフィックスを除去

Doxybook2 が生成する index_files.md では、ディレクトリ名やファイル名に
Doxygen INPUT ルートからの相対パス (例: calc/include, calc/src/add/add.c) が付与される。
merge-index-files.py でのマージ時に index_pages.md のローカル名と対応付けるため、
各表示名を末尾コンポーネントのみに変換する。

変換例:
    📁 calc/include         → 📁 include
    📁 calc/src/add         → 📁 add
    [calc/src/add/add.c]    → [add.c]
"""

import sys
import re
from typing import Match


def patch_index_files(path: str) -> None:
    """index_files.md の表示名をローカル名に変換する。

    バイナリモードで読み書きすることで、元の改行コード (CRLF/LF) を保持する。
    """
    with open(path, 'rb') as f:
        data = f.read()

    text = data.decode('utf-8')

    def strip_dir(m: Match[str]) -> str:
        """📁 path/to/dir → 📁 dir"""
        return '📁 ' + m.group(1).rsplit('/', 1)[-1]

    def strip_file(m: Match[str]) -> str:
        """[path/to/file](Files/...) → [file](Files/...)"""
        return '[' + m.group(1).rsplit('/', 1)[-1] + '](' + m.group(2) + ')'

    # ディレクトリ表示名: 📁 path/to/dir → 📁 dir
    # スラッシュを含まない名前はそのまま (ルートエントリ等)
    text = re.sub(r'📁 ([^\s\[<\r\n]+)', strip_dir, text)

    # ファイルリンク表示名: [path/to/file](Files/...) → [file](Files/...)
    # index_files.md 内のファイルリンクは必ず Files/ で始まる
    text = re.sub(r'\[([^\]]+)\]\((Files/[^)]+)\)', strip_file, text)

    with open(path, 'wb') as f:
        f.write(text.encode('utf-8'))


def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: patch-index-files.py <index_files.md>', file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    patch_index_files(path)
    print(f'Patched: {path}')


if __name__ == '__main__':
    main()
