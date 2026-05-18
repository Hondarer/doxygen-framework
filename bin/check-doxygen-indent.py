#!/usr/bin/env python3
"""
Doxygen コメント字下げレベル統一チェック・修正ツール

機能：
  - /** の字下げレベルから */ までの間で、すべての行の字下げレベルが統一されているかチェック
  - 不統一な場合、修正オプションで自動修正
  - --dry-run オプションで修正内容を表示（実際には修正しない）

使用例：
  check-doxygen-indent.py --check <file>           # チェックモード（既定）
  check-doxygen-indent.py --dry-run <file>         # 修正プレビュー（修正なし）
  check-doxygen-indent.py --fix <file>             # 実際に修正
  check-doxygen-indent.py --check <dir>            # ディレクトリ内の .h ファイルをチェック
"""

import sys
import os
import re
import argparse
from pathlib import Path


def get_indent_level(line):
    """行の字下げレベルを取得（スペース数）"""
    match = re.match(r'^( *)', line)
    return len(match.group(1)) if match else 0


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
            # 末尾コメント（/** ... */ が同一行）の場合はスキップ（オプション）
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
                
                # コメント終了行か？
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
                
                # コメント内容行か？（* で始まる行）
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
            # 末尾コメント（/** ... */ が同一行）の場合はスキップ（オプション）
            if skip_single_line_comments and re.search(r'/\*\*.*\*/', line):
                i += 1
                continue
            
            doc_start_indent = get_indent_level(line)
            target_indent = doc_start_indent + 1  # 目標インデント
            
            # 直後の連続するコメント行を修正
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                
                # コメント終了行か？
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
                
                # コメント内容行か？（* で始まる行）
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
    
    # 修正が必要な場合は、ファイルに書き込み（dry_run でない場合）
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


def print_check_results(all_issues, filepath_list):
    """チェック結果を表示"""
    if all_issues:
        print("\n❌ Doxygen コメント字下げレベルの不一致が検出されました\n")
        
        issue_count = 0
        for issue in all_issues:
            filename = issue['file']
            print(f"📄 {format_rel_path(filename)}")
            print(f"  L{issue['doc_start_line']}: /** (indent={issue['doc_start_indent']})")
            print(f"  期待される後続行のインデント: {issue['expected_indent']}")
            
            for mismatch in issue['mismatches'][:5]:  # 最初の5件表示
                marker = "━" if mismatch['is_closing'] else "✗"
                print(f"    {marker} L{mismatch['line_num']}: indent={mismatch['actual_indent']} "
                      f"(expected={mismatch['expected_indent']})")
                print(f"       {repr(mismatch['snippet'][:60])}")
            
            if len(issue['mismatches']) > 5:
                print(f"    ... ほか {len(issue['mismatches']) - 5} 件")
            
            issue_count += len(issue['mismatches'])
            print()
        
        print(f"📊 合計: {len(filepath_list)} ファイルをスキャン")
        print(f"   {len(all_issues)} 個のコメントブロックで不一致を検出")
        print(f"   {issue_count} 行の詳細な不一致")
        return 1
    else:
        print(f"✅ {len(filepath_list)} ファイルをスキャン: 問題なし")
        return 0


def print_fix_preview(all_files_with_mods):
    """修正プレビューを表示"""
    total_mods = 0
    modified_files = 0
    
    for filepath, modifications in all_files_with_mods:
        if modifications:
            modified_files += 1
            print(f"\n📄 {format_rel_path(filepath)}")
            print(f"  修正対象: {len(modifications)} 行\n")
            
            for mod in modifications[:10]:  # 最初の10件表示
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
  check-doxygen-indent.py --check app/com_util/prod/include
  check-doxygen-indent.py --dry-run app/com_util/prod/include
  check-doxygen-indent.py --fix app/com_util/prod/include
  check-doxygen-indent.py --check app/com_util/prod/include/com_util/sync/sync.h
  
  # ブロックコメント以外にマクロの末尾コメント（/** ... */）も処理する場合:
  check-doxygen-indent.py --check --include-single-line app/com_util/prod/include
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
        
        for header in header_files:
            modified, modifications = fix_file(str(header), dry_run=False, skip_single_line_comments=skip_single_line)
            if modified:
                fixed_count += 1
                total_mods += len(modifications)
                all_files_with_mods.append((str(header), modifications))
        
        if fixed_count:
            print(f"✅ {fixed_count} ファイルを修正しました ({total_mods} 行)")
            for filepath, mods in all_files_with_mods:
                print(f"  {format_rel_path(filepath)}: {len(mods)} 行修正")
            return 0
        else:
            print("✅ 修正対象のファイルはありません")
            return 0
    
    elif args.dry_run:
        # 修正プレビューモード
        print(f"🔍 修正プレビューモード: {len(header_files)} ファイルを処理中...\n")
        
        all_files_with_mods = []
        
        for header in header_files:
            modified, modifications = fix_file(str(header), dry_run=True, skip_single_line_comments=skip_single_line)
            if modified:
                all_files_with_mods.append((str(header), modifications))
        
        return print_fix_preview(all_files_with_mods)
    
    else:
        # チェックモード（既定）
        print(f"🔍 チェックモード: {len(header_files)} ファイルをスキャン中...\n")
        
        all_issues = []
        for header in header_files:
            issues = scan_file(str(header), skip_single_line_comments=skip_single_line)
            all_issues.extend(issues)
        
        return print_check_results(all_issues, header_files)


if __name__ == '__main__':
    sys.exit(main())
