#!/usr/bin/env python3
# merge-index-files.py - index_files.md と index_pages.md の階層構造をマージ

import sys
import re
from typing import Dict, List, Optional, Tuple

class Node:
    """ツリー構造のノードを表すクラス"""
    def __init__(self, name: str, indent: int, icon: str, link: str = "", description: str = ""):
        self.name = name
        self.indent = indent
        self.icon = icon
        self.link = link
        self.description = description
        self.children: List[Node] = []
        self.is_file = icon == "📄"

    def __repr__(self):
        return f"Node({self.name}, indent={self.indent}, icon={self.icon}, link={self.link})"

def parse_line(line: str) -> Optional[Tuple[int, str, str, str, str]]:
    """Markdown行を解析して (インデント, アイコン, 名前, リンク, 説明) を返す"""
    # インデントを計算（4スペース = 1レベル）
    stripped = line.lstrip()
    if not stripped or not stripped.startswith('*'):
        return None

    indent_count = (len(line) - len(stripped)) // 4

    # アイコンと残りの部分を抽出
    match = re.match(r'\* (📁|📄) (.+)', stripped)
    if not match:
        return None

    icon = match.group(1)
    rest = match.group(2)

    # リンクと説明を抽出
    # パターン: [name](link) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;description
    # または: [name](link)
    # または: name <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;description
    # または: name
    link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)(.*)', rest)
    if link_match:
        name = link_match.group(1)
        link = link_match.group(2)
        desc_part = link_match.group(3)
    else:
        # リンクなし
        name_match = re.match(r'([^<]+)(.*)', rest)
        if name_match:
            name = name_match.group(1).strip()
            link = ""
            desc_part = name_match.group(2)
        else:
            return None

    # 説明部分を抽出
    desc_match = re.search(r'<br/>(&nbsp;)*(.+)', desc_part)
    description = desc_match.group(2) if desc_match else ""

    return (indent_count, icon, name, link, description)

def build_tree(lines: List[str]) -> List[Node]:
    """Markdown行のリストからツリー構造を構築"""
    root_nodes: List[Node] = []
    stack: List[Node] = []

    for line in lines:
        parsed = parse_line(line)
        if not parsed:
            continue

        indent, icon, name, link, description = parsed
        node = Node(name, indent, icon, link, description)

        # スタックを現在のインデントレベルに調整
        while stack and stack[-1].indent >= indent:
            stack.pop()

        # 親ノードに追加
        if stack:
            stack[-1].children.append(node)
        else:
            root_nodes.append(node)

        # ディレクトリの場合はスタックに追加
        if not node.is_file:
            stack.append(node)

    return root_nodes

def merge_trees(pages_tree: List[Node], files_tree: List[Node]) -> List[Node]:
    """2つのツリーをマージ（ページ版を優先）"""
    def merge_nodes(pages_nodes: List[Node], files_nodes: List[Node]) -> List[Node]:
        # ページノードをベースにする
        result: List[Node] = []
        pages_dict: Dict[str, Node] = {node.name: node for node in pages_nodes}
        files_dict: Dict[str, Node] = {node.name: node for node in files_nodes}

        # 両辞書のキーの和集合を取得（末尾でソートするため挿入順は不問）
        all_names = list(pages_dict.keys() | files_dict.keys())

        for name in all_names:
            pages_node = pages_dict.get(name)
            files_node = files_dict.get(name)

            if pages_node and files_node:
                # 両方にある場合: ページ版を優先し、子をマージ
                merged_node = Node(
                    pages_node.name,
                    pages_node.indent,
                    pages_node.icon,
                    pages_node.link or files_node.link,
                    pages_node.description or files_node.description
                )
                # 子ノードを再帰的にマージ
                merged_node.children = merge_nodes(pages_node.children, files_node.children)
                result.append(merged_node)
            elif pages_node:
                # ページ版のみ: そのまま使用（ファイルツリーから子を追加）
                merged_node = Node(
                    pages_node.name,
                    pages_node.indent,
                    pages_node.icon,
                    pages_node.link,
                    pages_node.description
                )
                # ファイルツリーから対応するディレクトリを探す
                files_match = files_dict.get(name)
                if files_match and not pages_node.is_file:
                    # 子ノードをマージ
                    merged_node.children = merge_nodes(pages_node.children, files_match.children)
                else:
                    merged_node.children = pages_node.children
                result.append(merged_node)
            elif files_node:
                # ファイル版のみ: 追加（特にファイルエントリ）
                result.append(files_node)

        # フォルダ優先・名前順でソート
        result.sort(key=lambda n: (n.is_file, n.name))
        return result

    return merge_nodes(pages_tree, files_tree)

def tree_to_markdown(nodes: List[Node], base_indent: int = 0) -> List[str]:
    """ツリーをMarkdown行のリストに変換"""
    lines: List[str] = []

    for node in nodes:
        # インデント文字列を生成
        indent_str = "    " * node.indent

        # ノード部分を構築
        if node.link:
            node_str = f"{indent_str}* {node.icon} [{node.name}]({node.link})"
        else:
            node_str = f"{indent_str}* {node.icon} {node.name}"

        # 説明を追加
        if node.description:
            node_str += f" <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{node.description}"

        lines.append(node_str)

        # 子ノードを再帰的に追加
        lines.extend(tree_to_markdown(node.children, node.indent + 1))

    return lines

def merge_index_files(files_path: str, pages_path: str, output_path: str):
    """index_files.md と index_pages.md をマージ"""
    # ファイルを読み込む
    with open(files_path, 'r', encoding='utf-8') as f:
        files_lines = f.readlines()

    with open(pages_path, 'r', encoding='utf-8') as f:
        pages_lines = f.readlines()

    # ヘッダー部分（YAML front matter と見出しまで）を抽出
    header_lines = []
    content_start_idx = 0
    for i, line in enumerate(pages_lines):
        if line.startswith('# '):
            content_start_idx = i + 1
            break
        header_lines.append(line.rstrip())

    # ファイルとページのコンテンツ部分を抽出
    files_content = [line.rstrip() for line in files_lines[content_start_idx:]]
    pages_content = [line.rstrip() for line in pages_lines[content_start_idx:]]

    # ツリーを構築
    files_tree = build_tree(files_content)
    pages_tree = build_tree(pages_content)

    # ツリーをマージ
    merged_tree = merge_trees(pages_tree, files_tree)

    # Markdown に変換
    merged_lines = tree_to_markdown(merged_tree)

    # 出力ファイルを作成
    with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
        # ヘッダーを書き込む
        for line in header_lines:
            f.write(line + '\n')

        # 見出しを変更
        f.write('# ファイルとページの一覧\n')
        f.write('\n')

        # 展開可能リストとしてマージされたコンテンツを書き込む
        f.write('::: {.collapsible-list}\n')
        for line in merged_lines:
            f.write(line + '\n')
        f.write(':::\n')

def main():
    if len(sys.argv) != 2:
        print("Usage: merge-index-files.py <markdown_directory>", file=sys.stderr)
        sys.exit(1)

    markdown_dir = sys.argv[1]
    files_path = f"{markdown_dir}/index_files.md"
    pages_path = f"{markdown_dir}/index_pages.md"
    output_path = f"{markdown_dir}/index_files_and_pages.md"

    import os
    if not os.path.exists(files_path):
        print(f"Warning: {files_path} not found. Skipping merge.", file=sys.stderr)
        sys.exit(0)

    if not os.path.exists(pages_path):
        print(f"Warning: {pages_path} not found. Skipping merge.", file=sys.stderr)
        sys.exit(0)

    print(f"Merging {files_path} and {pages_path} into {output_path}")
    merge_index_files(files_path, pages_path, output_path)
    print(f"Successfully created {output_path}")

if __name__ == "__main__":
    main()
