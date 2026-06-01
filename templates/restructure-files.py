#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
restructure-files.py - Files/ を実フォルダ構造へ再編する

Doxybook2 が生成する Files/*.md はエンコード名でフラットに並んでいる。
各 md の先頭 H1 から元のソースファイルパス (INPUT 相対パス) を取得し、
Files/<path>.md へ移動する。

index_files.md 内の旧ファイル名リンクを新パスへ書き換える。

エンコード名ではなく H1 を情報源とする理由:
  - basename 衝突がない場合、エンコード名にパス情報が含まれない
    (divide_8c.md → libsrc/calcbase/divide.c は名前から復元不可)
  - エンコード表は Doxygen 内部仕様でバージョン依存
  - CASE_SENSE_NAMES が OS 依存でクロスプラットフォーム挙動が変わる
  - H1 は INPUT 相対の完全パスを常に保持し、バージョン/OS 非依存

使用方法:
    python3 restructure-files.py <docs_dir>
例:
    python3 restructure-files.py ../../docs/doxybook2/calc
"""

import sys
import os
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def extract_h1_path(md_path):
    """
    md ファイルの先頭 H1 から INPUT 相対パスを取得する。

    YAML フロントマターと HTML コメントをスキップし、
    最初の '# ' で始まる行からパスを抽出する。
    HTML エンティティ (&#95; -> _) を復元する。

    @param[in] md_path  対象 md ファイルの Path オブジェクト

    @return INPUT 相対パス文字列。取得できなければ None
    """
    in_frontmatter = False
    first_line = True
    with open(str(md_path), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\r\n')
            if first_line:
                first_line = False
                if line.strip() == '---':
                    in_frontmatter = True
                    continue
            if in_frontmatter:
                if line.strip() == '---':
                    in_frontmatter = False
                continue
            # HTML コメント行をスキップ
            if line.startswith('<!--'):
                continue
            if line.startswith('# '):
                path_str = line[2:].strip()
                # HTML エンティティ復元
                path_str = path_str.replace('&#95;', '_')
                # 空パスや単独スラッシュは不正
                if path_str and path_str != '/':
                    return path_str
                return None
    return None


def restructure_files(docs_dir):
    """
    Files/ をフラット構造から実フォルダ構造へ再編し、index_files.md を更新する。

    トップレベルの Files/*.md のみを対象とし、既にサブディレクトリ内に
    ある md はスキップする。

    @param[in] docs_dir  doxybook2 出力ディレクトリ (index_files.md のある場所)
    """
    docs_path = Path(docs_dir)
    files_dir = docs_path / 'Files'
    index_path = docs_path / 'index_files.md'

    if not files_dir.is_dir():
        print('警告: Files/ ディレクトリが見つかりません: {0}'.format(files_dir))
        return

    # トップレベルのフラットな .md のみ対象 (サブディレクトリ内は除外)
    flat_mds = sorted(
        p for p in files_dir.iterdir() if p.is_file() and p.suffix == '.md'
    )

    if not flat_mds:
        print('Files/: 再編対象なし。')
        return

    # 旧ファイル名 -> 新相対パス (Files/ 配下) の対応表
    rename_map = {}

    for md_path in flat_mds:
        src_path = extract_h1_path(md_path)
        if src_path is None:
            print('警告: H1 パスを取得できませんでした。スキップします: {0}'.format(
                md_path.name))
            continue

        # 移動先: Files/<src_path>.md
        # os.path.normpath で余分な ./ や重複スラッシュを除去
        norm_src = os.path.normpath(src_path).replace('\\', '/')
        new_path = files_dir / (norm_src + '.md')

        if new_path == md_path:
            print('  スキップ (変更なし): {0}'.format(md_path.name))
            continue

        # 衝突チェック
        if new_path.exists():
            print('警告: 移動先が既に存在します。スキップします: {0} -> {1}'.format(
                md_path.name,
                str(new_path.relative_to(files_dir)).replace('\\', '/')))
            continue

        # 中間ディレクトリを作成して移動
        new_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.rename(new_path)

        old_name = md_path.name
        new_rel_str = str(new_path.relative_to(files_dir)).replace('\\', '/')
        rename_map[old_name] = new_rel_str
        print('  Restructured: Files/{0} -> Files/{1}'.format(old_name, new_rel_str))

    if not rename_map:
        print('Files/: 移動対象なし (すべてスキップ)。')
        return

    # index_files.md のリンクを更新
    if index_path.is_file():
        with open(str(index_path), 'rb') as f:
            data = f.read()
        text = data.decode('utf-8')

        for old_name, new_rel_str in rename_map.items():
            # ](Files/<旧名>) -> ](Files/<新パス>)
            old_link = '](Files/' + old_name + ')'
            new_link = '](Files/' + new_rel_str + ')'
            text = text.replace(old_link, new_link)

        with open(str(index_path), 'wb') as f:
            f.write(text.encode('utf-8'))
        print('Updated: {0}'.format(index_path.name))
    else:
        print('警告: index_files.md が見つかりません: {0}'.format(index_path))


def main():
    """エントリーポイント。"""
    if len(sys.argv) != 2:
        print('使用方法: restructure-files.py <docs_dir>', file=sys.stderr)
        sys.exit(1)

    docs_dir = sys.argv[1]
    if not os.path.isdir(docs_dir):
        print('エラー: ディレクトリが存在しません: {0}'.format(docs_dir),
              file=sys.stderr)
        sys.exit(1)

    restructure_files(docs_dir)


if __name__ == '__main__':
    main()
