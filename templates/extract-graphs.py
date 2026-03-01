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


def collect_function_ids(xml_dir):
    """全 XML ファイルから function の id セットを収集する。

    コールグラフ/呼び出し元グラフで関数のみを対象にするために使用する。

    Args:
        xml_dir: XML ファイルが存在するディレクトリ

    Returns:
        set of str: function の id 文字列セット
    """
    function_ids = set()
    memberdef_pattern = re.compile(
        r'<memberdef\s+kind="function"\s+id="([^"]*)"'
    )
    for xml_path in glob.glob(os.path.join(xml_dir, '*.xml')):
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, UnicodeDecodeError):
            continue
        for match in memberdef_pattern.finditer(content):
            function_ids.add(match.group(1))
    return function_ids


def collect_compound_file_map(xml_dir):
    """全 XML ファイルから compound id → ファイルベース名マップを収集する。

    呼び出し関係グラフで static 関数のファイル名を特定するために使用する。

    Args:
        xml_dir: XML ファイルが存在するディレクトリ

    Returns:
        dict: {compound_id: file_basename}
    """
    compound_file_map = {}
    # compounddef の id 属性と compoundname を取得する
    pattern = re.compile(
        r'<compounddef\b([^>]*)>.*?<compoundname>([^<]*)</compoundname>',
        re.DOTALL
    )
    id_re = re.compile(r'\bid="([^"]*)"')
    kind_re = re.compile(r'\bkind="file"')
    for xml_path in glob.glob(os.path.join(xml_dir, '*.xml')):
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, UnicodeDecodeError):
            continue
        for match in pattern.finditer(content):
            attrs = match.group(1)
            compound_name = match.group(2)
            if kind_re.search(attrs):
                id_match = id_re.search(attrs)
                if id_match:
                    compound_file_map[id_match.group(1)] = os.path.basename(compound_name)
    return compound_file_map


def collect_static_function_ids(xml_dir):
    """全 XML ファイルから static 関数の id セットを収集する。

    呼び出し関係グラフで static 関数にファイル名を付加するために使用する。
    属性順序に依存しないよう、opening タグの属性文字列を個別に検索する。

    .. deprecated::
        compoundref ベースのファイル名付加に移行したため不要。
        後方互換のために残しているが、呼び出し元はない。

    Args:
        xml_dir: XML ファイルが存在するディレクトリ

    Returns:
        set of str: static="yes" な function の id 文字列セット
    """
    static_ids = set()
    memberdef_open_re = re.compile(r'<memberdef\b([^>]*)>')
    id_re = re.compile(r'\bid="([^"]*)"')
    kind_re = re.compile(r'\bkind="function"')
    static_re = re.compile(r'\bstatic="yes"')
    for xml_path in glob.glob(os.path.join(xml_dir, '*.xml')):
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, UnicodeDecodeError):
            continue
        for match in memberdef_open_re.finditer(content):
            attrs = match.group(1)
            if kind_re.search(attrs) and static_re.search(attrs):
                id_match = id_re.search(attrs)
                if id_match:
                    static_ids.add(id_match.group(1))
    return static_ids


def _qualified_func_name(name, extra_attrs, compound_file_map, self_compound_id=None):
    """compoundref が非ヘッダのソースファイルを指す場合にファイル名を付加した関数名を返す。

    <references>/<referencedby> タグの compoundref 属性が
    .h 以外のソースファイル (.c, .cc, .cpp など) にマップされる場合、
    'funcname\n(filename.c)' 形式で返す。
    compoundref が self_compound_id と一致する場合 (自ファイル内の関数) は
    ファイル名を付加せず name をそのまま返す。
    それ以外の場合も name をそのまま返す。

    Args:
        name: 関数名
        extra_attrs: <references>/<referencedby> 開始タグの属性文字列
        compound_file_map: compound id → ファイルベース名 マップ (None の場合は付加しない)
        self_compound_id: 処理中ファイル自身の compound id。
                          compoundref がこの値と一致する場合はファイル名を付加しない。

    Returns:
        表示用の関数名文字列
    """
    if compound_file_map:
        compoundref_match = re.search(r'\bcompoundref="([^"]*)"', extra_attrs)
        if compoundref_match:
            compoundref = compoundref_match.group(1)
            # 自ファイル内の関数はファイル名を付加しない
            if self_compound_id and compoundref == self_compound_id:
                return name
            file_name = compound_file_map.get(compoundref, '')
            if file_name and not file_name.lower().endswith('.h'):
                return f'{name}\\n({file_name})'
    return name


def parse_references(memberdef_block, function_ids=None, compound_file_map=None,
                     self_compound_id=None):
    """memberdef ブロックから references 要素を抽出する。

    compoundref が非ヘッダのソースファイルを指す場合は
    'funcname\n(filename.c)' 形式の名前を返す。
    self_compound_id と一致する場合 (自ファイル内) はファイル名を付加しない。

    Args:
        memberdef_block: <memberdef>...</memberdef> の XML テキスト
        function_ids: 関数として許可する id セット。None の場合は制限しない。
        compound_file_map: compound id → ファイルベース名 マップ。
        self_compound_id: 処理中ファイル自身の compound id。

    Returns:
        list of str: 呼び出し先の関数名リスト
    """
    refs = []
    pattern = re.compile(r'<references\s+refid="([^"]*)"([^>]*)>([^<]*)</references>')
    for match in pattern.finditer(memberdef_block):
        refid = match.group(1)
        extra_attrs = match.group(2)
        name = match.group(3).strip()
        if function_ids is not None and refid not in function_ids:
            continue
        if name:
            name = _qualified_func_name(name, extra_attrs, compound_file_map, self_compound_id)
            refs.append(name)
    return refs


def parse_referencedby(memberdef_block, function_ids=None, compound_file_map=None,
                       self_compound_id=None):
    """memberdef ブロックから referencedby 要素を抽出する。

    compoundref が非ヘッダのソースファイルを指す場合は
    'funcname\n(filename.c)' 形式の名前を返す。
    self_compound_id と一致する場合 (自ファイル内) はファイル名を付加しない。

    Args:
        memberdef_block: <memberdef>...</memberdef> の XML テキスト
        function_ids: 関数として許可する id セット。None の場合は制限しない。
        compound_file_map: compound id → ファイルベース名 マップ。
        self_compound_id: 処理中ファイル自身の compound id。

    Returns:
        list of str: 呼び出し元の関数名リスト
    """
    refs = []
    pattern = re.compile(r'<referencedby\s+refid="([^"]*)"([^>]*)>([^<]*)</referencedby>')
    for match in pattern.finditer(memberdef_block):
        refid = match.group(1)
        extra_attrs = match.group(2)
        name = match.group(3).strip()
        if function_ids is not None and refid not in function_ids:
            continue
        if name:
            name = _qualified_func_name(name, extra_attrs, compound_file_map, self_compound_id)
            refs.append(name)
    return refs


def graph_to_plantuml(nodes, edges, title, first_node_id=None, reverse_edges=False):
    """graphType のノードとエッジから PlantUML テキストを生成する。

    Args:
        nodes: {node_id: label} のノード辞書
        edges: [(from_id, to_id, relation)] のエッジリスト
        title: 図のキャプション
        first_node_id: 強調表示するノードの ID (対象要素自身)
        reverse_edges: True の場合、エッジを dst --> src と出力する。
                       エッジ方向を逆にすることで「依存ヘッダ → 対象」の矢印方向となり、
                       対象が PlantUML レイアウトの末尾 (下) に配置される。

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
            # -u--|> で矢印を上向きにし、自クラス (子) を下、継承元 (親) を上に配置する
            arrow = '-u-|>'
        elif relation == 'usage':
            arrow = '..>'
        else:
            arrow = '-->'

        if reverse_edges:
            # エッジ方向を逆にする (dst --> src) ことで対象を末尾に配置する
            lines.append(f'{safe_dst} {arrow} {safe_src}')
        else:
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

    .NET クラスは Doxygen XML では '::' 区切り (例: CalcLib::CalcException) だが、
    グラフノードのラベルでは '.' 区切り (例: CalcLib.CalcException) になる場合があるため、
    '::' を '.' に変換した形でも比較する。

    Args:
        nodes: {node_id: label} のノード辞書
        compound_name: compounddef の名前 (例: 'calc/src/calc/calc.c', 'UserInfo')

    Returns:
        一致するノードの ID。見つからない場合は None。
    """
    compound_name_dot = compound_name.replace('::', '.')
    basename = os.path.basename(compound_name)
    for node_id, label in nodes.items():
        if label == compound_name or label == compound_name_dot or os.path.basename(label) == basename:
            return node_id
    return None


def filter_header_only_graph(nodes, edges, self_id=None):
    """インクルード系グラフを .h ノードを中心に構成する。

    ノードラベルが .h で終わるノードを残す。
    self_id が指定された場合は、そのノードもラベルに関わらず残す。
    (親ファイルがヘッダ以外のソースファイルである場合に自身を含めるために使用する。)
    エッジも残存ノード間のものだけに絞り込む。

    Args:
        nodes: {node_id: label} のノード辞書
        edges: [(from_id, to_id, relation)] のエッジリスト
        self_id: 常に含めるノードの ID。None の場合は .h ノードのみを残す。

    Returns:
        (filtered_nodes, filtered_edges)
    """
    header_nodes = {
        node_id: label
        for node_id, label in nodes.items()
        if label.lower().endswith('.h') or node_id == self_id
    }

    filtered_edges = [
        (s, d, r)
        for s, d, r in edges
        if s in header_nodes and d in header_nodes
    ]

    return header_nodes, filtered_edges


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
            # reverse_edges=True により以下を実現する。
            # - エッジを dst --> src と出力し「依存ヘッダ → 対象」の矢印方向にする
            # - 対象が PlantUML レイアウトの末尾 (下) に配置される
            graphs = parse_graph_nodes(content, 'incdepgraph')
            for nodes, edges in graphs:
                self_id = find_self_node(nodes, compound_fullname)
                # 親ファイルがヘッダ以外 (.c, .cc, .cpp 等) の場合は自身ノードも含める
                # (.h の場合は .h フィルタで自然に含まれるため self_id 指定不要)
                inc_self_id = self_id if not display_name.lower().endswith('.h') else None
                nodes, edges = filter_header_only_graph(nodes, edges, self_id=inc_self_id)
                # INC_GRAPH_LABEL_BASENAME_ONLY が True の場合、
                # find_self_node() 呼び出し後にラベルをファイル名のみに変換する
                display_nodes = nodes
                if INC_GRAPH_LABEL_BASENAME_ONLY:
                    display_nodes = {
                        k: os.path.basename(v) for k, v in nodes.items()
                    }
                heading = 'インクルード元'
                caption = f'{display_name} の{heading}'
                puml = graph_to_plantuml(
                    display_nodes, edges,
                    caption,
                    first_node_id=self_id,
                    reverse_edges=True
                )
                if puml:
                    injections.append((heading, puml))

            # 逆インクルード依存グラフ
            graphs = parse_graph_nodes(content, 'invincdepgraph')
            for nodes, edges in graphs:
                self_id = find_self_node(nodes, compound_fullname)
                nodes, edges = filter_header_only_graph(nodes, edges)
                # INC_GRAPH_LABEL_BASENAME_ONLY が True の場合、
                # find_self_node() 呼び出し後にラベルをファイル名のみに変換する
                display_nodes = nodes
                if INC_GRAPH_LABEL_BASENAME_ONLY:
                    display_nodes = {
                        k: os.path.basename(v) for k, v in nodes.items()
                    }
                heading = 'インクルード先'
                caption = f'{display_name} の{heading}'
                puml = graph_to_plantuml(
                    display_nodes, edges,
                    caption,
                    first_node_id=self_id
                )
                if puml:
                    injections.append((heading, puml))

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
                heading = '継承関係'
                caption = f'{compound_name} の{heading}'
                puml = graph_to_plantuml(
                    nodes, edges,
                    caption,
                    first_node_id=self_id
                )
                if puml:
                    injections.append((heading, puml))

            # コラボレーション図
            graphs = parse_graph_nodes(content, 'collaborationgraph')
            for nodes, edges in graphs:
                self_id = find_self_node(nodes, compound_name)
                heading = 'コラボレーション図'
                caption = f'{compound_name} の{heading}'
                puml = graph_to_plantuml(
                    nodes, edges,
                    caption,
                    first_node_id=self_id
                )
                if puml:
                    injections.append((heading, puml))

        if not injections:
            return match.group(0)

        # detaileddescription の閉じタグの直前に挿入
        injection_text = ''.join(
            build_plantuml_tag(puml, heading) for heading, puml in injections
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


def inject_member_graphs(xml_text, function_ids=None, compound_file_map=None):
    """memberdef レベルのグラフ (コールグラフ、呼び出し元グラフ) を挿入する。

    Args:
        xml_text: XML ファイルの全文
        function_ids: コールグラフ/呼び出し元グラフの対象とする function の id セット
        compound_file_map: compound id → ファイルベース名マップ。

    Returns:
        修正後の XML テキスト
    """
    # 本 XML ファイル自身の compound id を取得 (自ファイル内関数のファイル名付加スキップに使用)
    self_compound_id_match = re.search(
        r'<compounddef\b[^>]*\bid="([^"]*)"', xml_text
    )
    self_compound_id = self_compound_id_match.group(1) if self_compound_id_match else None

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

        # 呼び出し元グラフ (referencedby)
        callers = parse_referencedby(content, function_ids, compound_file_map, self_compound_id)
        if callers:
            heading = '呼び出し元'
            caption = f'{func_name} の{heading}'
            puml = callergraph_to_plantuml(
                func_name, callers,
                caption
            )
            if puml:
                injections.append((heading, puml))

        # 呼び出し先グラフ (references)
        called = parse_references(content, function_ids, compound_file_map, self_compound_id)
        if called:
            heading = '呼び出し先'
            caption = f'{func_name} の{heading}'
            puml = callgraph_to_plantuml(
                func_name, called,
                caption
            )
            if puml:
                injections.append((heading, puml))

        if not injections:
            return match.group(0)

        injection_text = ''.join(
            build_plantuml_tag(puml, heading) for heading, puml in injections
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


def is_header_file_xml(xml_text):
    """XML テキストが .h ファイルの compounddef を含むかどうかを判定する。

    Doxygen XML の compounddef kind="file" の compoundname が
    '.h' で終わる場合に True を返す。

    Args:
        xml_text: XML ファイルの全文

    Returns:
        True: .h ファイルに対応する XML の場合
        False: それ以外の場合
    """
    pattern = re.compile(
        r'<compounddef\s[^>]*kind="file"[^>]*>.*?<compoundname>([^<]*)</compoundname>',
        re.DOTALL
    )
    match = pattern.search(xml_text)
    if match:
        compound_name = match.group(1)
        return compound_name.lower().endswith('.h')
    return False


def process_xml_file(xml_path, function_ids=None, compound_file_map=None):
    """XML ファイルを処理してグラフ情報を PlantUML として挿入する。

    Args:
        xml_path: XML ファイルのパス
        function_ids: コールグラフ/呼び出し元グラフの対象とする function の id セット
        compound_file_map: compound id → ファイルベース名マップ。

    Returns:
        True: ファイルが更新された場合
        False: 更新がなかった場合
    """
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            original = f.read()
    except (IOError, UnicodeDecodeError) as e:
        print(f"  Warning: file read error: {xml_path}: {e}")
        return False

    # compound レベルのグラフを挿入
    modified = inject_compound_graphs(original)

    # member レベルのグラフを挿入
    # .h ファイルの場合は呼び出し関係マップ (コールグラフ/呼び出し元グラフ) を生成しない
    if not is_header_file_xml(modified):
        modified = inject_member_graphs(modified, function_ids, compound_file_map)

    if modified == original:
        return False

    try:
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(modified)
    except IOError as e:
        print(f"  Error: file write error: {xml_path}: {e}")
        return False

    return True


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 extract-graphs.py <xml_directory>")
        sys.exit(1)

    xml_dir = sys.argv[1]

    if not os.path.isdir(xml_dir):
        print(f"Error: directory does not exist: {xml_dir}")
        sys.exit(1)

    xml_files = sorted(glob.glob(os.path.join(xml_dir, '*.xml')))

    if not xml_files:
        print(f"Warning: no XML files found: {xml_dir}")
        sys.exit(0)

    # 全 XML から function の id を収集
    # (コールグラフ/呼び出し元グラフを関数のみにするため)
    function_ids = collect_function_ids(xml_dir)

    # compound id → ファイル名マップを収集
    # (呼び出し関係グラフでソースファイル関数にファイル名を付加するため)
    compound_file_map = collect_compound_file_map(xml_dir)

    modified_count = 0
    skipped_count = 0

    for xml_file in xml_files:
        basename = os.path.basename(xml_file)
        # index.xml 等のインデックスファイルはスキップ
        if basename.startswith('index') or basename == 'combine.xslt':
            skipped_count += 1
            continue

        if process_xml_file(xml_file, function_ids, compound_file_map):
            modified_count += 1

    total = len(xml_files) - skipped_count
    print(f"Graph extraction complete: updated {modified_count}/{total} files")


if __name__ == '__main__':
    main()
