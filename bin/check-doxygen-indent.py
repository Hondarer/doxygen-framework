#!/usr/bin/env python3
"""
Doxygen コメント字下げレベル統一チェック・修正ツール

機能：
  - /** の字下げレベルから */ までの間で、すべての行の字下げレベルが統一されているかチェック
  - 不統一な場合、修正オプションで自動修正
  - --dry-run オプションで修正内容を表示（実際には修正しない）
  - 行頭に * を置かずに記述した図ブロック (@mermaid 〜 @endmermaid、@startuml 〜 @enduml) の
    字下げをチェック（開始行と終了行はコメント本文の桁、図の本文は開始行以上の深さ）
    図ブロックは修正せず、どのモードでも指摘として表示する

使用例：
  check-doxygen-indent.py --check <file>           # チェック モード (既定)
  check-doxygen-indent.py --dry-run <file>         # 修正プレビュー (修正なし)
  check-doxygen-indent.py --fix <file>             # 実際に修正
  check-doxygen-indent.py --check <dir>            # ディレクトリ内の .h ファイルをチェック
"""

import sys
import os
import re
import argparse
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def get_indent_level(line):
    """行の字下げレベルを取得（スペース数）"""
    match = re.match(r'^( *)', line)
    return len(match.group(1)) if match else 0


def is_inline_doxygen_comment_start(line):
    """メンバーやマクロの横に書くインライン Doxygen コメントかどうかを返す"""
    return re.search(r'/\*\*<', line) is not None


def skip_to_comment_end(lines, index):
    """コメント終了行の次の行インデックスを返す"""
    while index < len(lines):
        if re.search(r'\*/', lines[index]):
            return index + 1
        index += 1

    return index


def scan_file(filepath, skip_single_line_comments=True):
    """
    ファイルを走査し、字下げレベルの不一致を検出
    
    Args:
        filepath: 対象ファイルパス
        skip_single_line_comments: True の場合、末尾コメント（/** ... */ が同一行）は除外
    
    Returns:
        list: 不一致が見つかったコメントブロックのリスト
    """
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError) as e:
        print(f"⚠️  ファイルが読み込めません: {filepath} ({e})", file=sys.stderr)
        return issues
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Doxygen コメント開始行を見つけた場合
        if re.search(r'/\*\*', line):
            # メンバーやマクロの横に書く /**< ... */ は字下げ基準が異なるため対象外
            if is_inline_doxygen_comment_start(line):
                i = skip_to_comment_end(lines, i)
                continue

            # 末尾コメント (/** ... */ が同一行) の場合はスキップ (オプション)
            if skip_single_line_comments and re.search(r'/\*\*.*\*/', line):
                i += 1
                continue
            
            doc_start_indent = get_indent_level(line)
            expected_indent = doc_start_indent + 1  # 標準的には /** の深さ + 1
            line_num = i + 1
            
            # 直後の連続するコメント行をチェック
            j = i + 1
            has_mismatch = False
            mismatch_details = []
            
            while j < len(lines):
                next_line = lines[j]
                
                # コメント終了行か?
                if re.search(r'\*/', next_line):
                    # 終了行も字下げレベルをチェック
                    end_indent = get_indent_level(next_line)
                    if end_indent != expected_indent:
                        has_mismatch = True
                        mismatch_details.append({
                            'line_num': j + 1,
                            'actual_indent': end_indent,
                            'expected_indent': expected_indent,
                            'snippet': next_line.rstrip(),
                            'is_closing': True
                        })
                    break
                
                # コメント内容行か? (* で始まる行)
                if re.match(r'^\s*\*', next_line):
                    next_indent = get_indent_level(next_line)
                    
                    # 期待値と異なるかつ、スキップすべき空行でない場合
                    if next_indent != expected_indent and next_line.strip() != '*':
                        has_mismatch = True
                        mismatch_details.append({
                            'line_num': j + 1,
                            'actual_indent': next_indent,
                            'expected_indent': expected_indent,
                            'snippet': next_line.rstrip(),
                            'is_closing': False
                        })
                
                j += 1
            
            if has_mismatch:
                issues.append({
                    'file': filepath,
                    'doc_start_line': line_num,
                    'doc_start_indent': doc_start_indent,
                    'expected_indent': expected_indent,
                    'mismatches': mismatch_details
                })
            
            i = j + 1
        else:
            i += 1
    
    return issues


# 行頭に * を置かずに記述した図ブロックの開始行と終了行
DIAGRAM_START_PATTERN = re.compile(r'^[ \t]*([@\\](?:mermaid|startuml))(?![A-Za-z0-9_])')
DIAGRAM_END_PATTERN = re.compile(r'^[ \t]*([@\\](?:endmermaid|enduml))(?![A-Za-z0-9_])')

# * を持つ行で、* と後続の空白の次に来る本文 (*/ は本文として扱わない)
STAR_BODY_PATTERN = re.compile(r'^([ \t]*\*)(?!/)([ \t]*)\S')

# /** の行に続けて書いた本文
OPEN_BODY_PATTERN = re.compile(r'^([ \t]*/\*\*)([ \t]*)(?!\*/)\S')


def get_star_body_column(line):
    """* を持つ行の本文の桁を返す (本文がなければ None)"""
    match = STAR_BODY_PATTERN.match(line)
    if match:
        return len(match.group(1)) + len(match.group(2))
    return None


def get_open_body_column(line):
    """/** の行に続けて書いた本文の桁を返す (本文がなければ None)"""
    match = OPEN_BODY_PATTERN.match(line)
    if match:
        return len(match.group(1)) + len(match.group(2))
    return None


def get_diagram_body_indent(line):
    """図の本文の行の字下げを返す (空行は None)

    行頭に * を持つ行は、* と後続の空白の次に来る文字の位置を字下げとします。
    """
    if line.strip() == '':
        return None
    if re.match(r'^[ \t]*\*', line):
        return get_star_body_column(line)
    return get_indent_level(line)


def scan_diagram_lines(lines, skip_single_line_comments=True):
    """
    行の並びを走査し、行頭に * を置かずに記述した図ブロックの字下げの不一致を検出

    Args:
        lines: 対象ファイルの行のリスト
        skip_single_line_comments: True の場合、末尾コメント（/** ... */ が同一行）は除外

    Returns:
        list: 不一致が見つかった図ブロックのリスト
    """
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if not re.search(r'/\*\*', line):
            i += 1
            continue

        # メンバーやマクロの横に書く /**< ... */ は図ブロックを持たないため対象外
        if is_inline_doxygen_comment_start(line):
            i = skip_to_comment_end(lines, i)
            continue

        # 末尾コメント (/** ... */ が同一行) の場合はスキップ (オプション)
        if skip_single_line_comments and re.search(r'/\*\*.*\*/', line):
            i += 1
            continue

        # コメント本文の桁 (図ブロックより前にある、* を持ち本文のある最も近い行から求める)
        body_column = get_open_body_column(line)

        j = i + 1
        while j < len(lines):
            next_line = lines[j]

            start_match = DIAGRAM_START_PATTERN.match(next_line)
            if start_match:
                j = check_diagram_block(lines, j, start_match.group(1), body_column, blocks)
                continue

            if re.search(r'\*/', next_line):
                break

            column = get_star_body_column(next_line)
            if column is not None:
                body_column = column

            j += 1

        i = j + 1

    return blocks


def check_diagram_block(lines, start_index, keyword, body_column, blocks):
    """
    図ブロック 1 個の字下げを検査し、不一致があれば blocks へ追加

    Returns:
        int: 図ブロックの終了行の次の行インデックス
             (終了行より前にコメントが終わる場合は、コメント終了行のインデックス)
    """
    start_line = lines[start_index]
    start_indent = get_indent_level(start_line)
    mismatches = []

    if body_column is not None and start_indent != body_column:
        mismatches.append({
            'line_num': start_index + 1,
            'kind': 'start',
            'actual_indent': start_indent,
            'expected_indent': body_column,
            'snippet': start_line.rstrip(),
        })

    k = start_index + 1
    next_index = k
    while k < len(lines):
        current = lines[k]

        if DIAGRAM_END_PATTERN.match(current):
            end_indent = get_indent_level(current)
            if body_column is not None and end_indent != body_column:
                mismatches.append({
                    'line_num': k + 1,
                    'kind': 'end',
                    'actual_indent': end_indent,
                    'expected_indent': body_column,
                    'snippet': current.rstrip(),
                })
            next_index = k + 1
            break

        if re.search(r'\*/', current):
            # 終了行のないまま、コメントが終わった
            next_index = k
            break

        indent = get_diagram_body_indent(current)
        if indent is not None and indent < start_indent:
            mismatches.append({
                'line_num': k + 1,
                'kind': 'body',
                'actual_indent': indent,
                'expected_indent': start_indent,
                'snippet': current.rstrip(),
            })

        k += 1
    else:
        next_index = k

    if mismatches:
        blocks.append({
            'start_line': start_index + 1,
            'keyword': keyword,
            'body_column': body_column,
            'mismatches': sorted(mismatches, key=lambda item: item['line_num']),
        })

    return next_index


def scan_diagram_file(filepath, skip_single_line_comments=True, lines=None):
    """
    ファイルを走査し、行頭に * を置かずに記述した図ブロックの字下げの不一致を検出

    Args:
        filepath: 対象ファイルパス
        skip_single_line_comments: True の場合、末尾コメント（/** ... */ が同一行）は除外
        lines: 走査する行のリスト (None の場合はファイルから読み込む)

    Returns:
        list: 不一致が見つかった図ブロックのリスト
    """
    if lines is None:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except (IOError, UnicodeDecodeError):
            # 読み込めない旨は字下げレベルの検査と修正の側で表示済み
            return []

    blocks = scan_diagram_lines(lines, skip_single_line_comments=skip_single_line_comments)
    for block in blocks:
        block['file'] = filepath
    return blocks


def apply_modifications(filepath, modifications):
    """修正プレビューの内容を反映した行のリストを返す (ファイルは変更しない)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError):
        return None

    for mod in modifications:
        lines[mod['line_num'] - 1] = mod['after']
    return lines


def fix_file(filepath, dry_run=False, skip_single_line_comments=True):
    """
    ファイルの字下げを修正
    
    Args:
        filepath: 対象ファイルパス
        dry_run: True の場合は修正プレビューのみ（実際には修正しない）
        skip_single_line_comments: True の場合、末尾コメント（/** ... */ が同一行）は除外
    
    Returns:
        tuple: (修正が必要だったか, 修正内容のリスト)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError) as e:
        print(f"⚠️  ファイルが読み込めません: {filepath} ({e})", file=sys.stderr)
        return False, []
    
    modified = False
    modifications = []
    original_lines = lines.copy()
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Doxygen コメント開始行を見つけた場合
        if re.search(r'/\*\*', line):
            # メンバーやマクロの横に書く /**< ... */ は字下げ基準が異なるため対象外
            if is_inline_doxygen_comment_start(line):
                i = skip_to_comment_end(lines, i)
                continue

            # 末尾コメント (/** ... */ が同一行) の場合はスキップ (オプション)
            if skip_single_line_comments and re.search(r'/\*\*.*\*/', line):
                i += 1
                continue
            
            doc_start_indent = get_indent_level(line)
            target_indent = doc_start_indent + 1  # 目標インデント
            
            # 直後の連続するコメント行を修正
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                
                # コメント終了行か?
                if re.search(r'\*/', next_line):
                    # 終了行も字下げレベルを修正
                    current_indent = get_indent_level(next_line)
                    if current_indent != target_indent:
                        # 行末の改行記号を抽出
                        has_newline = next_line.endswith('\n')
                        line_without_newline = next_line.rstrip('\n')
                        
                        # 先頭のスペースを削除してから、目標インデントを追加
                        content_match = re.match(r'^ *(\*.*)$', line_without_newline)
                        if content_match:
                            content = content_match.group(1)
                            fixed_line = ' ' * target_indent + content
                            if has_newline:
                                fixed_line += '\n'
                            
                            if not dry_run:
                                lines[j] = fixed_line
                            
                            modified = True
                            modifications.append({
                                'line_num': j + 1,
                                'before': next_line,
                                'after': fixed_line
                            })
                    break
                
                # コメント内容行か? (* で始まる行)
                if re.match(r'^\s*\*', next_line):
                    current_indent = get_indent_level(next_line)
                    
                    # インデントが異なる場合は修正
                    if current_indent != target_indent:
                        # 行末の改行記号を抽出
                        has_newline = next_line.endswith('\n')
                        line_without_newline = next_line.rstrip('\n')
                        
                        # 先頭のスペースを削除してから、目標インデントを追加
                        content_match = re.match(r'^ *(\*.*)$', line_without_newline)
                        if content_match:
                            content = content_match.group(1)
                            fixed_line = ' ' * target_indent + content
                            if has_newline:
                                fixed_line += '\n'
                            
                            if not dry_run:
                                lines[j] = fixed_line
                            
                            modified = True
                            modifications.append({
                                'line_num': j + 1,
                                'before': next_line,
                                'after': fixed_line
                            })
                
                j += 1
            
            i = j + 1
        else:
            i += 1
    
    # 修正が必要な場合は、ファイルに書き込み (dry_run でない場合)
    if modified and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    
    return modified, modifications


def format_rel_path(filepath, base_dir=None):
    """ファイルパスを相対パスで表示"""
    if base_dir:
        try:
            return str(Path(filepath).relative_to(base_dir))
        except ValueError:
            return filepath
    return filepath


DIAGRAM_MISMATCH_LABELS = {
    'start': ('✗', '開始行'),
    'end': ('━', '終了行'),
    'body': ('✗', '図の本文'),
}


def print_diagram_issues(diagram_issues):
    """図ブロックの字下げの不一致を表示し、不一致の行数を返す"""
    print("\n❌ Doxygen コメントの図ブロックの字下げの不一致が検出されました\n")

    mismatch_count = 0
    for block in diagram_issues:
        print(f"📄 {format_rel_path(block['file'])}")
        body_column = block['body_column']
        column_text = body_column if body_column is not None else '不明'
        print(f"  L{block['start_line']}: {block['keyword']} (コメント本文の桁: {column_text})")

        for mismatch in block['mismatches'][:5]:  # 最初の 5 件表示
            marker, label = DIAGRAM_MISMATCH_LABELS[mismatch['kind']]
            relation = '>=' if mismatch['kind'] == 'body' else '='
            print(f"    {marker} L{mismatch['line_num']}: {label} indent={mismatch['actual_indent']} "
                  f"(expected{relation}{mismatch['expected_indent']})")
            print(f"       {repr(mismatch['snippet'][:60])}")

        if len(block['mismatches']) > 5:
            print(f"    ... ほか {len(block['mismatches']) - 5} 件")

        mismatch_count += len(block['mismatches'])
        print()

    print("💡 図ブロックは自動修正しません。開始行と終了行をコメント本文の桁に揃え、"
          "図の本文を開始行より浅くしないでください")
    return mismatch_count


def print_check_results(all_issues, filepath_list, diagram_issues=()):
    """チェック結果を表示"""
    if not all_issues and not diagram_issues:
        print(f"✅ {len(filepath_list)} ファイルをスキャン: 問題なし")
        return 0

    issue_count = 0
    if all_issues:
        print("\n❌ Doxygen コメント字下げレベルの不一致が検出されました\n")

        for issue in all_issues:
            filename = issue['file']
            print(f"📄 {format_rel_path(filename)}")
            print(f"  L{issue['doc_start_line']}: /** (indent={issue['doc_start_indent']})")
            print(f"  期待される後続行のインデント: {issue['expected_indent']}")

            for mismatch in issue['mismatches'][:5]:  # 最初の 5 件表示
                marker = "━" if mismatch['is_closing'] else "✗"
                print(f"    {marker} L{mismatch['line_num']}: indent={mismatch['actual_indent']} "
                      f"(expected={mismatch['expected_indent']})")
                print(f"       {repr(mismatch['snippet'][:60])}")

            if len(issue['mismatches']) > 5:
                print(f"    ... ほか {len(issue['mismatches']) - 5} 件")

            issue_count += len(issue['mismatches'])
            print()

    diagram_mismatch_count = 0
    if diagram_issues:
        diagram_mismatch_count = print_diagram_issues(diagram_issues)
        print()

    print(f"📊 合計: {len(filepath_list)} ファイルをスキャン")
    if all_issues:
        print(f"   {len(all_issues)} 個のコメントブロックで不一致を検出")
        print(f"   {issue_count} 行の詳細な不一致")
    if diagram_issues:
        print(f"   {len(diagram_issues)} 個の図ブロックで字下げの不一致を検出")
        print(f"   {diagram_mismatch_count} 行の図ブロックの不一致")
    return 1


def print_fix_preview(all_files_with_mods):
    """修正プレビューを表示"""
    total_mods = 0
    modified_files = 0
    
    for filepath, modifications in all_files_with_mods:
        if modifications:
            modified_files += 1
            print(f"\n📄 {format_rel_path(filepath)}")
            print(f"  修正対象: {len(modifications)} 行\n")
            
            for mod in modifications[:10]:  # 最初の 10 件表示
                before_indent = len(mod['before']) - len(mod['before'].lstrip())
                after_indent = len(mod['after']) - len(mod['after'].lstrip())
                print(f"    L{mod['line_num']}: indent {before_indent} → {after_indent}")
                print(f"      before: {repr(mod['before'].rstrip()[:50])}")
                print(f"      after:  {repr(mod['after'].rstrip()[:50])}")
            
            if len(modifications) > 10:
                print(f"    ... ほか {len(modifications) - 10} 行")
            
            total_mods += len(modifications)
    
    if modified_files:
        print(f"\n📊 修正予定: {modified_files} ファイル, {total_mods} 行")
        print("\n💡 実際に修正するには --fix オプションを使用してください")
        return 0
    else:
        print("✅ 修正対象のファイルはありません")
        return 0


def get_header_files(target):
    """ターゲット（ファイルまたはディレクトリ）から .h ファイルを取得"""
    target_path = Path(target)
    
    if target_path.is_file():
        if target_path.suffix == '.h':
            return [target_path]
        return []
    elif target_path.is_dir():
        return sorted(target_path.glob('**/*.h'))
    
    return []


def main():
    parser = argparse.ArgumentParser(
        description='Doxygen コメント字下げレベルをチェック・修正します',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例：
  check-doxygen-indent.py --check app/cplat/prod/include
  check-doxygen-indent.py --dry-run app/cplat/prod/include
  check-doxygen-indent.py --fix app/cplat/prod/include
  check-doxygen-indent.py --check app/cplat/prod/include/cplat/sync/sync.h
  
  # ブロック コメント以外にマクロの末尾コメント (/** ... */) も処理する場合:
  check-doxygen-indent.py --check --include-single-line app/cplat/prod/include
        """
    )
    
    parser.add_argument(
        'target',
        help='チェック対象（ファイルまたはディレクトリ）'
    )
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--check',
        action='store_true',
        default=True,
        help='チェックモード（既定）：問題を検出して報告'
    )
    mode_group.add_argument(
        '--dry-run',
        action='store_true',
        help='修正プレビューモード：修正内容を表示（実際には修正しない）'
    )
    mode_group.add_argument(
        '--fix',
        action='store_true',
        help='修正モード：字下げレベルを統一する'
    )
    
    parser.add_argument(
        '--include-single-line',
        action='store_true',
        default=False,
        help='末尾コメント（/** ... */ が同一行）も対象に含める（既定: 除外）'
    )
    
    args = parser.parse_args()
    
    # ターゲットの確認
    target_path = Path(args.target)
    if not target_path.exists():
        print(f"❌ エラー: {args.target} が見つかりません", file=sys.stderr)
        return 1
    
    # .h ファイルを取得
    header_files = get_header_files(args.target)
    if not header_files:
        print(f"❌ エラー: .h ファイルが見つかりません", file=sys.stderr)
        return 1
    
    skip_single_line = not args.include_single_line
    
    # モード判定
    if args.fix:
        # 修正モード
        print(f"🔧 修正モード: {len(header_files)} ファイルを処理中...\n")
        
        all_files_with_mods = []
        fixed_count = 0
        total_mods = 0
        
        diagram_issues = []

        for header in header_files:
            modified, modifications = fix_file(str(header), dry_run=False, skip_single_line_comments=skip_single_line)
            if modified:
                fixed_count += 1
                total_mods += len(modifications)
                all_files_with_mods.append((str(header), modifications))
            # 図ブロックは書き換えず、修正後の内容で指摘だけを行う
            diagram_issues.extend(scan_diagram_file(str(header), skip_single_line_comments=skip_single_line))

        if fixed_count:
            print(f"✅ {fixed_count} ファイルを修正しました ({total_mods} 行)")
            for filepath, mods in all_files_with_mods:
                print(f"  {format_rel_path(filepath)}: {len(mods)} 行修正")
        else:
            print("✅ 修正対象のファイルはありません")

        if diagram_issues:
            print_diagram_issues(diagram_issues)
        return 0

    elif args.dry_run:
        # 修正プレビュー モード
        print(f"🔍 修正プレビューモード: {len(header_files)} ファイルを処理中...\n")

        all_files_with_mods = []
        diagram_issues = []

        for header in header_files:
            modified, modifications = fix_file(str(header), dry_run=True, skip_single_line_comments=skip_single_line)
            if modified:
                all_files_with_mods.append((str(header), modifications))
            # 図ブロックは書き換えず、修正を反映した場合の内容で指摘だけを行う
            preview_lines = apply_modifications(str(header), modifications) if modified else None
            diagram_issues.extend(scan_diagram_file(str(header), skip_single_line_comments=skip_single_line,
                                                    lines=preview_lines))

        result = print_fix_preview(all_files_with_mods)
        if diagram_issues:
            print_diagram_issues(diagram_issues)
        return result

    else:
        # チェック モード (既定)
        print(f"🔍 チェックモード: {len(header_files)} ファイルをスキャン中...\n")

        all_issues = []
        diagram_issues = []
        for header in header_files:
            issues = scan_file(str(header), skip_single_line_comments=skip_single_line)
            all_issues.extend(issues)
            diagram_issues.extend(scan_diagram_file(str(header), skip_single_line_comments=skip_single_line))

        return print_check_results(all_issues, header_files, diagram_issues)


if __name__ == '__main__':
    sys.exit(main())
