#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
extract-graphs.py - Doxygen XML からグラフ情報を抽出し PlantUML として挿入する

Doxygen が生成した XML ファイルを解析し、以下のグラフ情報を PlantUML 形式に変換して
XML の detaileddescription セクションに <plantuml> タグとして挿入する。

- インクルード依存グラフ (incdepgraph)
- 逆インクルード依存グラフ (invincdepgraph)
- 継承グラフ (inheritancegraph)
- コラボレーション図 (collaborationgraph)
- コールグラフ (references)
- 呼び出し元グラフ (referencedby)

挿入された <plantuml> タグは、後続の preprocess.sh により Markdown コードフェンスに
変換される。

使用方法: python3 extract-graphs.py <xml_directory>
"""

import sys
import os
import glob
import re

# グラフあたりの最大ノード数 (これを超えるグラフは生成しない)
# Doxygen の DOT_GRAPH_MAX_NODES (デフォルト 50) に合わせた値
DOT_GRAPH_MAX_NODES = 50

# インクルード依存グラフ・被インクルード関係グラフのノードラベルをファイル名のみにするフラグ
# True : ファイル名のみ表示 (別フォルダに同名ファイルがない前提)
# False: フルパスをそのまま表示
INC_GRAPH_LABEL_BASENAME_ONLY = True


def parse_graph_nodes(xml_text, graph_tag):
    """XML テキストから graphType 要素のノードとエッジを抽出する。

    ElementTree を使わず、正規表現で必要な情報を抽出することで
    XML の書式を完全に保持する。

    Args:
        xml_text: XML ファイルの全文
        graph_tag: 抽出対象のグラフタグ名 (例: 'incdepgraph')

    Returns:
        list of (nodes_dict, edges_list) タプル。
        nodes_dict: {node_id: label}
        edges_list: [(from_id, to_id, relation)]
        グラフが見つからない場合は空リストを返す。
    """
    results = []

    # グラフブロックを抽出
    pattern = re.compile(
        rf'<{graph_tag}>(.*?)</{graph_tag}>',
        re.DOTALL
    )

    for match in pattern.finditer(xml_text):
        graph_block = match.group(1)
        nodes = {}
        edges = []

        # ノードを抽出
        node_pattern = re.compile(
            r'<node\s+id="([^"]*)">(.*?)</node>',
            re.DOTALL
        )
        for node_match in node_pattern.finditer(graph_block):
            node_id = node_match.group(1)
            node_content = node_match.group(2)

            # ラベルを抽出
            label_match = re.search(r'<label>([^<]*)</label>', node_content)
            if label_match:
                nodes[node_id] = label_match.group(1)

            # 子ノード (エッジ) を抽出
            child_pattern = re.compile(
                r'<childnode\s+refid="([^"]*)"\s+relation="([^"]*)"'
            )
            for child_match in child_pattern.finditer(node_content):
                child_refid = child_match.group(1)
                relation = child_match.group(2)
                edges.append((node_id, child_refid, relation))

        if nodes:
            results.append((nodes, edges))

    return results


def parse_references(memberdef_block):
    """memberdef ブロックから references 要素を抽出する。

    Args:
        memberdef_block: <memberdef>...</memberdef> の XML テキスト

    Returns:
        list of str: 呼び出し先の関数名リスト
    """
    refs = []
    pattern = re.compile(r'<references[^>]*>([^<]*)</references>')
    for match in pattern.finditer(memberdef_block):
        name = match.group(1).strip()
        if name:
            refs.append(name)
    return refs


def parse_referencedby(memberdef_block):
    """memberdef ブロックから referencedby 要素を抽出する。

    Args:
        memberdef_block: <memberdef>...</memberdef> の XML テキスト

    Returns:
        list of str: 呼び出し元の関数名リスト
    """
    refs = []
    pattern = re.compile(r'<referencedby[^>]*>([^<]*)</referencedby>')
    for match in pattern.finditer(memberdef_block):
        name = match.group(1).strip()
        if name:
            refs.append(name)
    return refs


def graph_to_plantuml(nodes, edges, title, first_node_id=None):
    """graphType のノードとエッジから PlantUML テキストを生成する。

    Args:
        nodes: {node_id: label} のノード辞書
        edges: [(from_id, to_id, relation)] のエッジリスト
        title: 図のキャプション
        first_node_id: 強調表示するノードの ID (対象要素自身)

    Returns:
        PlantUML テキスト (caption 行を含む、@startuml/@enduml は含まない)。
        ノードが DOT_GRAPH_MAX_NODES を超える場合は None を返す。
    """
    if not nodes or len(nodes) > DOT_GRAPH_MAX_NODES:
        return None

    # エッジがない場合はグラフを生成しない
    valid_edges = [
        (s, d, r) for s, d, r in edges if s in nodes and d in nodes
    ]
    if not valid_edges:
        return None

    lines = []
    lines.append(f'caption {title}')

    for node_id, label in nodes.items():
        safe_id = f'n{node_id}'
        escaped = label.replace('"', '\\"')
        if node_id == first_node_id:
            lines.append(f'rectangle "**{escaped}**" as {safe_id} #LightBlue')
        else:
            lines.append(f'rectangle "{escaped}" as {safe_id}')

    for src_id, dst_id, relation in edges:
        if src_id not in nodes or dst_id not in nodes:
            continue
        safe_src = f'n{src_id}'
        safe_dst = f'n{dst_id}'

        if relation in (
            'public-inheritance',
            'protected-inheritance',
            'private-inheritance'
        ):
            arrow = '--|>'
        elif relation == 'usage':
            arrow = '..>'
        else:
            arrow = '-->'

        lines.append(f'{safe_src} {arrow} {safe_dst}')

    return '\n'.join(lines)


def callgraph_to_plantuml(func_name, called_funcs, title):
    """コールグラフの PlantUML テキストを生成する。

    Args:
        func_name: 対象関数名
        called_funcs: 呼び出し先関数名のリスト
        title: 図のキャプション

    Returns:
        PlantUML テキスト。ノードが DOT_GRAPH_MAX_NODES を超える場合は None を返す。
    """
    if not called_funcs or len(called_funcs) + 1 > DOT_GRAPH_MAX_NODES:
        return None

    # 重複を除去 (順序は保持)
    seen = set()
    unique_funcs = []
    for f in called_funcs:
        if f not in seen:
            seen.add(f)
            unique_funcs.append(f)

    lines = []
    lines.append(f'caption {title}')

    escaped_name = func_name.replace('"', '\\"')
    lines.append(f'rectangle "**{escaped_name}**" as current #LightBlue')

    for i, ref_name in enumerate(unique_funcs):
        escaped = ref_name.replace('"', '\\"')
        lines.append(f'rectangle "{escaped}" as r{i}')

    for i in range(len(unique_funcs)):
        lines.append(f'current --> r{i}')

    return '\n'.join(lines)


def callergraph_to_plantuml(func_name, caller_funcs, title):
    """呼び出し元グラフの PlantUML テキストを生成する。

    Args:
        func_name: 対象関数名
        caller_funcs: 呼び出し元関数名のリスト
        title: 図のキャプション

    Returns:
        PlantUML テキスト。ノードが DOT_GRAPH_MAX_NODES を超える場合は None を返す。
    """
    if not caller_funcs or len(caller_funcs) + 1 > DOT_GRAPH_MAX_NODES:
        return None

    # 重複を除去 (順序は保持)
    seen = set()
    unique_funcs = []
    for f in caller_funcs:
        if f not in seen:
            seen.add(f)
            unique_funcs.append(f)

    lines = []
    lines.append(f'caption {title}')

    escaped_name = func_name.replace('"', '\\"')
    lines.append(f'rectangle "**{escaped_name}**" as current #LightBlue')

    for i, ref_name in enumerate(unique_funcs):
        escaped = ref_name.replace('"', '\\"')
        lines.append(f'rectangle "{escaped}" as c{i}')

    for i in range(len(unique_funcs)):
        lines.append(f'c{i} --> current')

    return '\n'.join(lines)


def build_plantuml_tag(plantuml_body, title):
    """PlantUML テキストを <simplesect kind="par"> タグで囲む。

    Doxybook2 の details.tmpl で par セクションとして処理され、
    #### 見出し付きの独立セクションとして出力される。

    Args:
        plantuml_body: PlantUML テキスト (@startuml/@enduml は含まない)
        title: セクションの見出しタイトル

    Returns:
        挿入用の XML 文字列
    """
    return (
        f'<para><simplesect kind="par"><title>{title}</title>'
        f'<para><plantuml>\n{plantuml_body}\n</plantuml></para>'
        f'</simplesect></para>\n'
    )


def find_self_node(nodes, compound_name):
    """ノード辞書から自身 (対象要素) のノード ID を検索する。

    ラベルが compound_name と完全一致、または basename が一致するノードを返す。
    一致するノードがない場合は None を返す。

    Args:
        nodes: {node_id: label} のノード辞書
        compound_name: compounddef の名前 (例: 'calc/src/calc/calc.c', 'UserInfo')

    Returns:
        一致するノードの ID。見つからない場合は None。
    """
    basename = os.path.basename(compound_name)
    for node_id, label in nodes.items():
        if label == compound_name or os.path.basename(label) == basename:
            return node_id
    return None


def inject_compound_graphs(xml_text):
    """compounddef レベルのグラフ (インクルード依存、継承、コラボレーション) を挿入する。

    Args:
        xml_text: XML ファイルの全文

    Returns:
        修正後の XML テキスト
    """
    # 各 compounddef を処理
    compounddef_pattern = re.compile(
        r'(<compounddef\s[^>]*kind="(\w+)"[^>]*>)(.*?)(</compounddef>)',
        re.DOTALL
    )

    def process_compound(match):
        opening_tag = match.group(1)
        kind = match.group(2)
        content = match.group(3)
        closing_tag = match.group(4)

        injections = []

        if kind == 'file':
            # コンパウンド名を取得 (ファイル名)
            name_match = re.search(
                r'<compoundname>([^<]*)</compoundname>', content
            )
            compound_fullname = 'unknown'
            display_name = 'unknown'
            if name_match:
                compound_fullname = name_match.group(1)
                display_name = os.path.basename(compound_fullname)

            # インクルード依存グラフ
            graphs = parse_graph_nodes(content, 'incdepgraph')
            for nodes, edges in graphs:
                self_id = find_self_node(nodes, compound_fullname)
                # INC_GRAPH_LABEL_BASENAME_ONLY が True の場合、
                # find_self_node() 呼び出し後にラベルをファイル名のみに変換する
                display_nodes = nodes
                if INC_GRAPH_LABEL_BASENAME_ONLY:
                    display_nodes = {
                        k: os.path.basename(v) for k, v in nodes.items()
                    }
                title = f'{display_name} のインクルード依存'
                puml = graph_to_plantuml(
                    display_nodes, edges,
                    title,
                    first_node_id=self_id
                )
                if puml:
                    injections.append((title, puml))

            # 逆インクルード依存グラフ
            graphs = parse_graph_nodes(content, 'invincdepgraph')
            for nodes, edges in graphs:
                self_id = find_self_node(nodes, compound_fullname)
                # INC_GRAPH_LABEL_BASENAME_ONLY が True の場合、
                # find_self_node() 呼び出し後にラベルをファイル名のみに変換する
                display_nodes = nodes
                if INC_GRAPH_LABEL_BASENAME_ONLY:
                    display_nodes = {
                        k: os.path.basename(v) for k, v in nodes.items()
                    }
                title = f'{display_name} の被インクルード関係'
                puml = graph_to_plantuml(
                    display_nodes, edges,
                    title,
                    first_node_id=self_id
                )
                if puml:
                    injections.append((title, puml))

        elif kind in ('class', 'struct'):
            # コンパウンド名を取得
            name_match = re.search(
                r'<compoundname>([^<]*)</compoundname>', content
            )
            compound_name = 'unknown'
            if name_match:
                compound_name = name_match.group(1)

            # 継承グラフ
            graphs = parse_graph_nodes(content, 'inheritancegraph')
            for nodes, edges in graphs:
                self_id = find_self_node(nodes, compound_name)
                title = f'{compound_name} の継承関係'
                puml = graph_to_plantuml(
                    nodes, edges,
                    title,
                    first_node_id=self_id
                )
                if puml:
                    injections.append((title, puml))

            # コラボレーション図
            graphs = parse_graph_nodes(content, 'collaborationgraph')
            for nodes, edges in graphs:
                self_id = find_self_node(nodes, compound_name)
                title = f'{compound_name} のコラボレーション図'
                puml = graph_to_plantuml(
                    nodes, edges,
                    title,
                    first_node_id=self_id
                )
                if puml:
                    injections.append((title, puml))

        if not injections:
            return match.group(0)

        # detaileddescription の閉じタグの直前に挿入
        injection_text = ''.join(
            build_plantuml_tag(puml, title) for title, puml in injections
        )

        # detaileddescription が存在する場合、その閉じタグの前に挿入
        # rfind で最後の </detaileddescription> を検索する。
        # Doxygen XML では compounddef の detaileddescription が
        # sectiondef/memberdef の後に出力されるため、最後のものが
        # compounddef 自身のものとなる。
        desc_close = '</detaileddescription>'
        pos = content.rfind(desc_close)
        if pos != -1:
            content = (
                content[:pos] + injection_text + content[pos:]
            )
        else:
            # detaileddescription が存在しない場合、新規作成
            # compounddef の閉じタグの直前に追加
            content = (
                content
                + f'<detaileddescription>{injection_text}</detaileddescription>\n'
            )

        return opening_tag + content + closing_tag

    return compounddef_pattern.sub(process_compound, xml_text)


def inject_member_graphs(xml_text):
    """memberdef レベルのグラフ (コールグラフ、呼び出し元グラフ) を挿入する。

    Args:
        xml_text: XML ファイルの全文

    Returns:
        修正後の XML テキスト
    """
    memberdef_pattern = re.compile(
        r'(<memberdef\s[^>]*kind="function"[^>]*>)(.*?)(</memberdef>)',
        re.DOTALL
    )

    def process_member(match):
        opening_tag = match.group(1)
        content = match.group(2)
        closing_tag = match.group(3)

        # 関数名を取得
        name_match = re.search(r'<name>([^<]*)</name>', content)
        if not name_match:
            return match.group(0)
        func_name = name_match.group(1)

        injections = []

        # コールグラフ (references)
        called = parse_references(content)
        if called:
            title = f'{func_name} のコールグラフ'
            puml = callgraph_to_plantuml(
                func_name, called,
                title
            )
            if puml:
                injections.append((title, puml))

        # 呼び出し元グラフ (referencedby)
        callers = parse_referencedby(content)
        if callers:
            title = f'{func_name} の呼び出し元'
            puml = callergraph_to_plantuml(
                func_name, callers,
                title
            )
            if puml:
                injections.append((title, puml))

        if not injections:
            return match.group(0)

        injection_text = ''.join(
            build_plantuml_tag(puml, title) for title, puml in injections
        )

        # detaileddescription の閉じタグの直前に挿入
        desc_close = '</detaileddescription>'
        pos = content.find(desc_close)
        if pos != -1:
            content = (
                content[:pos] + injection_text + content[pos:]
            )
        else:
            # detaileddescription が存在しない場合、inbodydescription の前に追加
            inbody_pos = content.find('<inbodydescription')
            if inbody_pos != -1:
                content = (
                    content[:inbody_pos]
                    + f'<detaileddescription>{injection_text}</detaileddescription>\n'
                    + content[inbody_pos:]
                )

        return opening_tag + content + closing_tag

    return memberdef_pattern.sub(process_member, xml_text)


def process_xml_file(xml_path):
    """XML ファイルを処理してグラフ情報を PlantUML として挿入する。

    Args:
        xml_path: XML ファイルのパス

    Returns:
        True: ファイルが更新された場合
        False: 更新がなかった場合
    """
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            original = f.read()
    except (IOError, UnicodeDecodeError) as e:
        print(f"  警告: ファイル読み込みエラー: {xml_path}: {e}")
        return False

    # compound レベルのグラフを挿入
    modified = inject_compound_graphs(original)

    # member レベルのグラフを挿入
    modified = inject_member_graphs(modified)

    if modified == original:
        return False

    try:
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(modified)
    except IOError as e:
        print(f"  エラー: ファイル書き込みエラー: {xml_path}: {e}")
        return False

    return True


def main():
    if len(sys.argv) != 2:
        print("使用方法: python3 extract-graphs.py <xml_directory>")
        sys.exit(1)

    xml_dir = sys.argv[1]

    if not os.path.isdir(xml_dir):
        print(f"エラー: ディレクトリが存在しません: {xml_dir}")
        sys.exit(1)

    xml_files = sorted(glob.glob(os.path.join(xml_dir, '*.xml')))

    if not xml_files:
        print(f"警告: XML ファイルが見つかりません: {xml_dir}")
        sys.exit(0)

    modified_count = 0
    skipped_count = 0

    for xml_file in xml_files:
        basename = os.path.basename(xml_file)
        # index.xml 等のインデックスファイルはスキップ
        if basename.startswith('index') or basename == 'combine.xslt':
            skipped_count += 1
            continue

        if process_xml_file(xml_file):
            modified_count += 1

    total = len(xml_files) - skipped_count
    print(f"グラフ抽出完了: {modified_count}/{total} ファイルを更新")


if __name__ == '__main__':
    main()
