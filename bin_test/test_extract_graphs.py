#!/usr/bin/env python3

import importlib.util
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


DOXYFW_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = DOXYFW_ROOT / "templates" / "extract-graphs.py"


def load_module():
    # ファイル名にハイフンを含むため、通常の import ではなくパス指定で読み込む
    spec = importlib.util.spec_from_file_location("extract_graphs_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


eg = load_module()


def edge_lines(text):
    # 矢印を含む行だけを取り出す
    return [line.strip() for line in text.splitlines() if "-->" in line or "-.->" in line]


class GraphToMermaidTest(unittest.TestCase):
    def test_flowchart_td_declaration_and_sequential_node_ids(self):
        nodes = {"a": "A", "b": "B", "c": "C"}
        edges = [("a", "b", "include"), ("b", "c", "include")]
        text = eg.graph_to_mermaid(nodes, edges)
        lines = text.splitlines()
        self.assertEqual(lines[0], "flowchart TD")
        self.assertIn('    n0["A"]', lines)
        self.assertIn('    n1["B"]', lines)
        self.assertIn('    n2["C"]', lines)
        self.assertEqual(edge_lines(text), ["n0 --> n1", "n1 --> n2"])

    def test_usage_relation_uses_dotted_arrow(self):
        nodes = {"a": "A", "b": "B", "c": "C"}
        edges = [("a", "b", "usage"), ("a", "c", "public-inheritance")]
        text = eg.graph_to_mermaid(nodes, edges)
        self.assertEqual(edge_lines(text), ["n0 -.-> n1", "n0 --> n2"])

    def test_reverse_edges_flips_direction(self):
        nodes = {"a": "A", "b": "B"}
        text = eg.graph_to_mermaid(nodes, [("a", "b", "include")], reverse_edges=True)
        self.assertEqual(edge_lines(text), ["n1 --> n0"])

    def test_direction_bt_is_declared(self):
        nodes = {"a": "A", "b": "B"}
        text = eg.graph_to_mermaid(nodes, [("a", "b", "x")], direction="BT")
        self.assertEqual(text.splitlines()[0], "flowchart BT")

    def test_first_node_is_highlighted_with_style(self):
        nodes = {"a": "A", "b": "B"}
        text = eg.graph_to_mermaid(nodes, [("a", "b", "x")], first_node_id="b")
        self.assertIn("    style n1 fill:#ADD8E6,stroke:#333,font-weight:bold", text.splitlines())
        self.assertEqual(text.count("style "), 1)

    def test_no_style_when_first_node_is_not_given(self):
        nodes = {"a": "A", "b": "B"}
        text = eg.graph_to_mermaid(nodes, [("a", "b", "x")])
        self.assertNotIn("style ", text)

    def test_returns_none_when_node_count_exceeds_limit(self):
        limit = eg.DOT_GRAPH_MAX_NODES
        nodes = {f"id{i}": f"N{i}" for i in range(limit + 1)}
        edges = [("id0", "id1", "x")]
        self.assertIsNone(eg.graph_to_mermaid(nodes, edges))

    def test_returns_text_when_node_count_equals_limit(self):
        limit = eg.DOT_GRAPH_MAX_NODES
        nodes = {f"id{i}": f"N{i}" for i in range(limit)}
        edges = [("id0", "id1", "x")]
        self.assertIsNotNone(eg.graph_to_mermaid(nodes, edges))

    def test_returns_none_when_no_valid_edge(self):
        nodes = {"a": "A", "b": "B"}
        self.assertIsNone(eg.graph_to_mermaid(nodes, []))
        # 存在しないノードを指すエッジだけの場合も有効なエッジがない
        self.assertIsNone(eg.graph_to_mermaid(nodes, [("a", "zzz", "x")]))

    def test_returns_none_when_nodes_are_empty(self):
        self.assertIsNone(eg.graph_to_mermaid({}, [("a", "b", "x")]))


class LabelEscapeTest(unittest.TestCase):
    def render_label(self, label):
        text = eg.graph_to_mermaid({"a": label, "b": "B"}, [("a", "b", "x")])
        return text.splitlines()[1]

    def test_xml_entities_become_mermaid_entities(self):
        line = self.render_label("List&lt;int&gt; &amp; &quot;x&quot;")
        self.assertEqual(line, '    n0["List&lt;int&gt; &amp; #quot;x#quot;"]')

    def test_raw_characters_are_escaped_the_same_way(self):
        line = self.render_label('a<b>&"c')
        self.assertEqual(line, '    n0["a&lt;b&gt;&amp;#quot;c"]')

    def test_literal_backslash_n_becomes_line_break(self):
        # バックスラッシュと n の 2 文字
        line = self.render_label("func\\n(file.c)")
        self.assertEqual(line, '    n0["func<br/>(file.c)"]')

    def test_real_newline_becomes_line_break(self):
        line = self.render_label("func\n(file.c)")
        self.assertEqual(line, '    n0["func<br/>(file.c)"]')


class CallGraphTest(unittest.TestCase):
    def test_callgraph_removes_duplicates_and_points_to_callees(self):
        text = eg.callgraph_to_mermaid("main", ["foo", "bar", "foo"])
        lines = text.splitlines()
        self.assertEqual(lines[0], "flowchart TD")
        self.assertEqual(text.count('["foo"]'), 1)
        self.assertEqual(text.count('["bar"]'), 1)
        self.assertEqual(edge_lines(text), ["n0 --> n1", "n0 --> n2"])
        self.assertIn('    n0["main"]', lines)
        self.assertIn("    style n0 fill:#ADD8E6,stroke:#333,font-weight:bold", lines)

    def test_callergraph_removes_duplicates_and_points_to_target(self):
        text = eg.callergraph_to_mermaid("target", ["foo", "bar", "foo"])
        lines = text.splitlines()
        self.assertEqual(text.count('["foo"]'), 1)
        self.assertEqual(edge_lines(text), ["n1 --> n0", "n2 --> n0"])
        self.assertIn('    n0["target"]', lines)
        self.assertIn("    style n0 fill:#ADD8E6,stroke:#333,font-weight:bold", lines)

    def test_callgraph_returns_none_for_empty_or_over_limit(self):
        limit = eg.DOT_GRAPH_MAX_NODES
        self.assertIsNone(eg.callgraph_to_mermaid("main", []))
        self.assertIsNone(eg.callergraph_to_mermaid("main", []))
        over = [f"f{i}" for i in range(limit)]  # 起点を足すと limit + 1
        self.assertIsNone(eg.callgraph_to_mermaid("main", over))
        self.assertIsNone(eg.callergraph_to_mermaid("main", over))
        ok = [f"f{i}" for i in range(limit - 1)]
        self.assertIsNotNone(eg.callgraph_to_mermaid("main", ok))
        self.assertIsNotNone(eg.callergraph_to_mermaid("main", ok))


class RecursiveGraphTest(unittest.TestCase):
    NODES = {"f1": "root", "f2": "mid", "f3": "leaf"}
    EDGES = [("f1", "f2"), ("f2", "f3")]

    def test_callgraph_graph_renders_multi_level_edges(self):
        text = eg.callgraph_to_mermaid_graph("f2", self.NODES, self.EDGES)
        self.assertEqual(text.splitlines()[0], "flowchart TD")
        self.assertEqual(edge_lines(text), ["n0 --> n1", "n1 --> n2"])
        self.assertIn("    style n1 fill:#ADD8E6,stroke:#333,font-weight:bold", text.splitlines())

    def test_callergraph_graph_renders_multi_level_edges(self):
        text = eg.callergraph_to_mermaid_graph("f3", self.NODES, self.EDGES)
        self.assertEqual(edge_lines(text), ["n0 --> n1", "n1 --> n2"])
        self.assertIn("    style n2 fill:#ADD8E6,stroke:#333,font-weight:bold", text.splitlines())

    def test_graph_variants_return_none_without_edges(self):
        self.assertIsNone(eg.callgraph_to_mermaid_graph("f1", {"f1": "root"}, []))
        self.assertIsNone(eg.callergraph_to_mermaid_graph("f1", {"f1": "root"}, []))

    def test_graph_variants_return_none_over_node_limit(self):
        nodes = {f"f{i}": f"N{i}" for i in range(eg.DOT_GRAPH_MAX_NODES + 1)}
        edges = [("f0", "f1")]
        self.assertIsNone(eg.callgraph_to_mermaid_graph("f0", nodes, edges))
        self.assertIsNone(eg.callergraph_to_mermaid_graph("f0", nodes, edges))


class BuildMermaidTagTest(unittest.TestCase):
    def parse(self, tag):
        # 整形式であることを、ラッパー要素に入れたパースで確認する
        return ET.fromstring(f"<root>{tag}</root>")

    def test_title_is_placed_in_simplesect_par(self):
        tag = eg.build_mermaid_tag("flowchart TD", "呼び出し先", "f の呼び出し先")
        root = self.parse(tag)
        sect = root.find("./para/simplesect")
        self.assertEqual(sect.get("kind"), "par")
        self.assertEqual(sect.findtext("title"), "呼び出し先")
        self.assertEqual(sect.find("./para/mermaid").get("caption"), "f の呼び出し先")

    def test_details_only_adds_marker_prefix(self):
        tag = eg.build_mermaid_tag("flowchart TD", "呼び出し先", "c", details_only=True)
        self.assertIn("<title>DOXYFW_DETAILS_ONLY 呼び出し先</title>", tag)
        plain = eg.build_mermaid_tag("flowchart TD", "呼び出し先", "c")
        self.assertIn("<title>呼び出し先</title>", plain)
        self.assertNotIn("DOXYFW_DETAILS_ONLY", plain)

    def test_caption_attribute_is_xml_escaped(self):
        tag = eg.build_mermaid_tag("flowchart TD", "t", 'a<b>&"c')
        self.assertIn('caption="a&lt;b&gt;&amp;&quot;c"', tag)
        root = self.parse(tag)
        self.assertEqual(root.find(".//mermaid").get("caption"), 'a<b>&"c')

    def test_caption_from_xml_is_not_double_escaped(self):
        tag = eg.build_mermaid_tag("flowchart TD", "t", "List&lt;int&gt; の呼び出し先")
        self.assertIn('caption="List&lt;int&gt; の呼び出し先"', tag)
        self.assertNotIn("&amp;lt;", tag)

    def test_body_is_xml_escaped(self):
        body = eg.graph_to_mermaid(
            {"a": "Foo&lt;int&gt;", "b": "B"}, [("a", "b", "x")])
        tag = eg.build_mermaid_tag(body, "t", "c")
        self.assertIn("n0 --&gt; n1", tag)
        self.assertNotIn("-->", tag)
        self.assertIn('n0["Foo&amp;lt;int&amp;gt;"]', tag)
        # パース後は Mermaid のラベルが復元される
        mermaid = self.parse(tag).find(".//mermaid").text
        self.assertIn('n0["Foo&lt;int&gt;"]', mermaid)
        self.assertIn("n0 --> n1", mermaid)

    def test_output_is_well_formed_with_special_characters(self):
        body = eg.graph_to_mermaid(
            {"a": 'x<y>&"z"\\nw', "b": "B"}, [("a", "b", "usage")])
        tag = eg.build_mermaid_tag(body, "t", 'c<d>&"e"')
        root = self.parse(tag)
        self.assertEqual(root.find(".//mermaid").get("caption"), 'c<d>&"e"')
        self.assertIn("-.->", root.find(".//mermaid").text)


def file_compound_xml(compound_id, name, graph_xml="", members_xml=""):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<doxygen>\n'
        f'<compounddef id="{compound_id}" kind="file" language="C">\n'
        f'<compoundname>{name}</compoundname>\n'
        f'{graph_xml}'
        f'{members_xml}'
        '<detaileddescription></detaileddescription>\n'
        f'<location file="{name}"/>\n'
        '</compounddef>\n'
        '</doxygen>\n'
    )


def class_compound_xml(kind, name, graph_xml):
    return (
        '<doxygen>\n'
        f'<compounddef id="c1" kind="{kind}" language="C++">\n'
        f'<compoundname>{name}</compoundname>\n'
        f'{graph_xml}'
        '<detaileddescription></detaileddescription>\n'
        '</compounddef>\n'
        '</doxygen>\n'
    )


def graph_xml(tag, nodes):
    # nodes: [(id, label, [(child_id, relation)])]
    parts = [f"<{tag}>"]
    for node_id, label, children in nodes:
        parts.append(f'<node id="{node_id}"><label>{label}</label>')
        for child_id, relation in children:
            parts.append(f'<childnode refid="{child_id}" relation="{relation}"></childnode>')
        parts.append("</node>")
    parts.append(f"</{tag}>")
    return "".join(parts) + "\n"


def member_xml(func_id, name, body_file, references=(), referencedby=()):
    parts = [
        f'<memberdef kind="function" id="{func_id}" prot="public" static="no">\n',
        f"<name>{name}</name>\n",
        "<detaileddescription></detaileddescription>\n",
    ]
    for ref_id, ref_name in references:
        parts.append(f'<references refid="{ref_id}" compoundref="{ref_id}c">{ref_name}</references>\n')
    for ref_id, ref_name in referencedby:
        parts.append(f'<referencedby refid="{ref_id}" compoundref="{ref_id}c">{ref_name}</referencedby>\n')
    parts.append(f'<location file="{body_file}" bodyfile="{body_file}"/>\n')
    parts.append("</memberdef>\n")
    return "".join(parts)


class InjectCompoundGraphsTest(unittest.TestCase):
    def test_incdepgraph_inserts_include_source_section(self):
        graph = graph_xml("incdepgraph", [
            ("1", "inc/a.h", [("2", "include")]),
            ("2", "inc/b.h", []),
        ])
        out = eg.inject_compound_graphs(file_compound_xml("a_8h", "inc/a.h", graph))
        self.assertIn("<title>DOXYFW_DETAILS_ONLY インクルード元</title>", out)
        self.assertIn('caption="a.h のインクルード元"', out)
        self.assertIn("flowchart TD", out)
        # 逆向きのエッジで、対象 (n0) が下流になる
        self.assertIn("n1 --&gt; n0", out)
        self.assertIn("style n0 ", out)
        self.assertNotIn("<plantuml", out)

    def test_invincdepgraph_inserts_include_destination_section(self):
        # invincdepgraph はエッジの向きを保つ (a.h を include する側が子)
        graph = graph_xml("invincdepgraph", [
            ("1", "inc/a.h", []),
            ("2", "inc/user.h", [("1", "include")]),
        ])
        out = eg.inject_compound_graphs(file_compound_xml("a_8h", "inc/a.h", graph))
        self.assertIn("<title>DOXYFW_DETAILS_ONLY インクルード先</title>", out)
        self.assertIn('caption="a.h のインクルード先"', out)
        self.assertIn("n1 --&gt; n0", out)
        self.assertNotIn("<plantuml", out)

    def test_inheritancegraph_inserts_bt_flowchart(self):
        graph = graph_xml("inheritancegraph", [
            ("1", "Derived", [("2", "public-inheritance")]),
            ("2", "Base", []),
        ])
        out = eg.inject_compound_graphs(class_compound_xml("class", "Derived", graph))
        self.assertIn("<title>DOXYFW_DETAILS_ONLY 継承関係</title>", out)
        self.assertIn('caption="Derived の継承関係"', out)
        self.assertIn("flowchart BT", out)
        self.assertIn("n0 --&gt; n1", out)
        self.assertIn("style n0 ", out)
        self.assertNotIn("<plantuml", out)

    def test_collaborationgraph_inserts_section_with_usage_arrow(self):
        graph = graph_xml("collaborationgraph", [
            ("1", "Owner", [("2", "usage")]),
            ("2", "Part", []),
        ])
        out = eg.inject_compound_graphs(class_compound_xml("struct", "Owner", graph))
        self.assertIn("<title>DOXYFW_DETAILS_ONLY コラボレーション図</title>", out)
        self.assertIn('caption="Owner のコラボレーション図"', out)
        self.assertIn("flowchart TD", out)
        self.assertIn("n0 -.-&gt; n1", out)
        self.assertNotIn("<plantuml", out)

    def test_injected_section_is_inside_detaileddescription_and_well_formed(self):
        graph = graph_xml("inheritancegraph", [
            ("1", "Derived&lt;T&gt;", [("2", "public-inheritance")]),
            ("2", "Base", []),
        ])
        out = eg.inject_compound_graphs(class_compound_xml("class", "Derived", graph))
        root = ET.fromstring(out)
        mermaid = root.find(".//detaileddescription//mermaid")
        self.assertIsNotNone(mermaid)
        self.assertIn('n0["Derived&lt;T&gt;"]', mermaid.text)

    def test_no_injection_when_graph_has_no_edges(self):
        graph = graph_xml("inheritancegraph", [("1", "Alone", [])])
        xml = class_compound_xml("class", "Alone", graph)
        self.assertEqual(eg.inject_compound_graphs(xml), xml)


class InjectMemberGraphsTest(unittest.TestCase):
    def build(self):
        members = member_xml(
            "f1", "target", "src/a.c",
            references=[("f2", "callee")],
            referencedby=[("f3", "caller")])
        return file_compound_xml("a_8c", "src/a.c", members_xml=members)

    def test_references_and_referencedby_are_injected_in_fallback_mode(self):
        out = eg.inject_member_graphs(self.build(), function_ids={"f1", "f2", "f3"})
        self.assertIn("<title>DOXYFW_DETAILS_ONLY 呼び出し先</title>", out)
        self.assertIn('caption="target の呼び出し先"', out)
        self.assertIn("<title>DOXYFW_DETAILS_ONLY 呼び出し元</title>", out)
        self.assertIn('caption="target の呼び出し元"', out)
        self.assertNotIn("<plantuml", out)

        root = ET.fromstring(out)
        texts = {m.get("caption"): m.text for m in root.iter("mermaid")}
        self.assertIn("n0 --> n1", texts["target の呼び出し先"])
        self.assertIn('n1["callee"]', texts["target の呼び出し先"])
        # 呼び出し元は caller --> target の向き
        self.assertIn("n1 --> n0", texts["target の呼び出し元"])
        self.assertIn('n1["caller"]', texts["target の呼び出し元"])

    def test_function_ids_filter_excludes_unknown_references(self):
        out = eg.inject_member_graphs(self.build(), function_ids={"f1"})
        self.assertNotIn("<mermaid", out)

    def test_recursive_maps_expand_multi_level_graph(self):
        callees_map = {"f1": [("f2", "")], "f2": [("f4", "")]}
        callers_map = {"f1": [("f3", "")]}
        names = {"f1": "target", "f2": "callee", "f3": "caller", "f4": "leaf"}
        paths = {k: "src/a.c" for k in names}
        out = eg.inject_member_graphs(
            self.build(), function_ids=set(names), callees_map=callees_map,
            callers_map=callers_map, func_name_map=names, func_file_path_map=paths)
        root = ET.fromstring(out)
        texts = {m.get("caption"): m.text for m in root.iter("mermaid")}
        callee_text = texts["target の呼び出し先"]
        self.assertIn('["leaf', callee_text)
        self.assertEqual(len(edge_lines(callee_text)), 2)
        self.assertEqual(len(edge_lines(texts["target の呼び出し元"])), 1)
        self.assertNotIn("<plantuml", out)


class MainIntegrationTest(unittest.TestCase):
    def test_main_inserts_all_graph_kinds_into_files(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            xml_dir = Path(temp_dir_text)

            header_graph = graph_xml("incdepgraph", [
                ("1", "inc/a.h", [("2", "include")]),
                ("2", "inc/b.h", []),
            ])
            (xml_dir / "a_8h.xml").write_text(
                file_compound_xml("a_8h", "inc/a.h", header_graph),
                encoding="utf-8", newline="\n")

            members = member_xml(
                "f1", "target", "src/a.c",
                references=[("f2", "callee")], referencedby=[("f3", "caller")])
            members += member_xml("f2", "callee", "src/a.c")
            members += member_xml("f3", "caller", "src/a.c")
            (xml_dir / "a_8c.xml").write_text(
                file_compound_xml("a_8c", "src/a.c", members_xml=members),
                encoding="utf-8", newline="\n")

            class_graph = (
                graph_xml("inheritancegraph", [
                    ("1", "Derived", [("2", "public-inheritance")]),
                    ("2", "Base", []),
                ])
                + graph_xml("collaborationgraph", [
                    ("1", "Derived", [("2", "usage")]),
                    ("2", "Part", []),
                ])
            )
            (xml_dir / "classDerived.xml").write_text(
                class_compound_xml("class", "Derived", class_graph),
                encoding="utf-8", newline="\n")

            # index.xml は処理対象外
            index_text = "<doxygenindex></doxygenindex>\n"
            (xml_dir / "index.xml").write_text(index_text, encoding="utf-8", newline="\n")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(xml_dir)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("updated 3/3 files", result.stdout)

            header = (xml_dir / "a_8h.xml").read_text(encoding="utf-8")
            source = (xml_dir / "a_8c.xml").read_text(encoding="utf-8")
            klass = (xml_dir / "classDerived.xml").read_text(encoding="utf-8")

            self.assertIn('caption="a.h のインクルード元"', header)
            self.assertIn('caption="target の呼び出し先"', source)
            self.assertIn('caption="target の呼び出し元"', source)
            self.assertIn('caption="Derived の継承関係"', klass)
            self.assertIn("flowchart BT", klass)
            self.assertIn('caption="Derived のコラボレーション図"', klass)
            self.assertIn("-.-&gt;", klass)

            for text in (header, source, klass):
                self.assertNotIn("<plantuml", text)
                ET.fromstring(text)
            self.assertEqual(
                (xml_dir / "index.xml").read_text(encoding="utf-8"), index_text)


if __name__ == "__main__":
    unittest.main()
