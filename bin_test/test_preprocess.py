#!/usr/bin/env python3

import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil

# Windows の subprocess は System32 を PATH より先に探すため、名前だけで起動すると
# WSL の bash.exe を選ぶことがある。PATH 上の bash (Git Bash など) を明示して使う。
# see: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw
BASH = shutil.which("bash") or "bash"


PREPROCESS_SCRIPT = Path(__file__).resolve().parents[1] / "templates" / "preprocess.sh"


class PreprocessTest(unittest.TestCase):
    def test_parblock_wrapper_is_removed_without_changing_paragraphs(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            xml_dir = Path(temp_dir_text)
            xml_path = xml_dir / "sample.xml"
            xml_path.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <simplesect kind="note">
    <para>
      <parblock>
        <para>first paragraph</para>
        <para>second paragraph</para>
      </parblock>
    </para>
  </simplesect>
</doxygen>
""",
                encoding="utf-8",
            )

            subprocess.run(
                [BASH, str(PREPROCESS_SCRIPT), str(xml_dir)],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            transformed = xml_path.read_text(encoding="utf-8")
            self.assertNotIn("<parblock>", transformed)
            self.assertNotIn("</parblock>", transformed)

            root = ET.fromstring(transformed)
            simplesect = root.find("simplesect")
            self.assertIsNotNone(simplesect)
            self.assertEqual(simplesect.attrib["kind"], "par")
            self.assertEqual(simplesect.findtext("title"), "!doxyfw-admonition NOTE")

            container = simplesect.find("para")
            paragraphs = list(container)
            self.assertEqual([paragraph.tag for paragraph in paragraphs], ["para", "para"])
            self.assertEqual(
                ["".join(paragraph.itertext()) for paragraph in paragraphs],
                ["first paragraph", "second paragraph"],
            )


ANON_FILE_SCOPE_REFID = "namespace_0d0250021603150113202762263663111643702522"
ANON_NESTED_REFID = "namespacesample_1_1detail_1_1_0d3641261771023030113170651721160400"

# Doxygen が EXTRACT_ANON_NSPACES = NO で出力する index.xml の再現。
# 無名名前空間は <name> が @<8 進数字列> 形式になる。
INDEX_XML = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex version="1.15.0">
  <compound refid="{anon_file}" kind="namespace"><name>@0250021603150113202762263663111643702522</name>
    <member refid="{anon_file}_1a1afec94df0dc36ac869a13a7f7047c1c" kind="enum"><name>char_class_bit</name></member>
  </compound>
  <compound refid="namespacesample" kind="namespace"><name>sample</name>
  </compound>
  <compound refid="namespacesample_1_1detail" kind="namespace"><name>sample::detail</name>
    <member refid="namespacesample_1_1detail_1a6d6ff91eae85abbe1f12c8746c01c6d9" kind="function"><name>helper</name></member>
  </compound>
  <compound refid="{anon_nested}" kind="namespace"><name>sample::detail::@3641261771023030113170651721160400</name>
  </compound>
  <compound refid="sample_8cc" kind="file"><name>sample.cc</name>
  </compound>
</doxygenindex>
"""

# ファイル スコープの無名名前空間。compoundname が空要素になり Doxybook2 がクラッシュする。
ANON_FILE_SCOPE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen version="1.15.0">
  <compounddef id="{anon_file}" kind="namespace" language="C++">
    <compoundname></compoundname>
    <location file="sample.cc" line="52" column="1"/>
  </compounddef>
</doxygen>
"""

# 入れ子の無名名前空間。compoundname は親名前空間名で出力される。
ANON_NESTED_XML = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen version="1.15.0">
  <compounddef id="{anon_nested}" kind="namespace" language="C++">
    <compoundname>sample::detail</compoundname>
    <location file="sample.cc" line="29" column="1"/>
  </compounddef>
</doxygen>
"""

NAMED_NAMESPACE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen version="1.15.0">
  <compounddef id="namespacesample_1_1detail" kind="namespace" language="C++">
    <compoundname>sample::detail</compoundname>
    <innernamespace refid="{anon_nested}"></innernamespace>
    <location file="sample.cc" line="20" column="1"/>
  </compounddef>
</doxygen>
"""

FILE_COMPOUND_XML = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen version="1.15.0">
  <compounddef id="sample_8cc" kind="file" language="C++">
    <compoundname>sample.cc</compoundname>
    <innernamespace refid="{anon_file}"></innernamespace>
    <detaileddescription>
      <para>see <ref refid="{anon_file}_1a1afec94df0dc36ac869a13a7f7047c1c" kindref="member">char_class_bit</ref> for details</para>
    </detaileddescription>
  </compounddef>
</doxygen>
"""


class StripAnonymousNamespacesTest(unittest.TestCase):
    def _build_xml_dir(self, xml_dir):
        """無名名前空間を含む Doxygen XML 一式をテンポラリ ディレクトリへ書き出す。"""
        refids = {"anon_file": ANON_FILE_SCOPE_REFID, "anon_nested": ANON_NESTED_REFID}
        contents = {
            "index.xml": INDEX_XML,
            "{0}.xml".format(ANON_FILE_SCOPE_REFID): ANON_FILE_SCOPE_XML,
            "{0}.xml".format(ANON_NESTED_REFID): ANON_NESTED_XML,
            "namespacesample_1_1detail.xml": NAMED_NAMESPACE_XML,
            "sample_8cc.xml": FILE_COMPOUND_XML,
        }
        for name, template in contents.items():
            (xml_dir / name).write_text(template.format(**refids), encoding="utf-8")

    def _run_preprocess(self, xml_dir):
        subprocess.run(
            [BASH, str(PREPROCESS_SCRIPT), str(xml_dir)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_anonymous_namespace_compounds_are_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            xml_dir = Path(temp_dir_text)
            self._build_xml_dir(xml_dir)

            self._run_preprocess(xml_dir)

            self.assertFalse((xml_dir / "{0}.xml".format(ANON_FILE_SCOPE_REFID)).exists())
            self.assertFalse((xml_dir / "{0}.xml".format(ANON_NESTED_REFID)).exists())

    def test_named_namespace_compound_is_kept(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            xml_dir = Path(temp_dir_text)
            self._build_xml_dir(xml_dir)

            self._run_preprocess(xml_dir)

            named_path = xml_dir / "namespacesample_1_1detail.xml"
            self.assertTrue(named_path.exists())
            root = ET.fromstring(named_path.read_text(encoding="utf-8"))
            compounddef = root.find("compounddef")
            self.assertEqual(compounddef.findtext("compoundname"), "sample::detail")

    def test_index_entries_of_anonymous_namespaces_are_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            xml_dir = Path(temp_dir_text)
            self._build_xml_dir(xml_dir)

            self._run_preprocess(xml_dir)

            index_path = xml_dir / "index.xml"
            transformed = index_path.read_text(encoding="utf-8")
            self.assertNotIn(ANON_FILE_SCOPE_REFID, transformed)
            self.assertNotIn(ANON_NESTED_REFID, transformed)
            # 無名名前空間配下のメンバー エントリも compound ごと除去される
            self.assertNotIn("char_class_bit", transformed)

            root = ET.fromstring(transformed)
            refids = [compound.attrib["refid"] for compound in root.findall("compound")]
            self.assertEqual(
                refids,
                [
                    "namespacesample",
                    "namespacesample_1_1detail",
                    "sample_8cc",
                ],
            )

    def test_references_to_anonymous_namespaces_are_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            xml_dir = Path(temp_dir_text)
            self._build_xml_dir(xml_dir)

            self._run_preprocess(xml_dir)

            file_compound = (xml_dir / "sample_8cc.xml").read_text(encoding="utf-8")
            self.assertNotIn(ANON_FILE_SCOPE_REFID, file_compound)
            self.assertNotIn("<innernamespace", file_compound)
            # <ref> はタグのみを外し、表示テキストは残す
            self.assertIn("see char_class_bit for details", file_compound)

            named_namespace = (xml_dir / "namespacesample_1_1detail.xml").read_text(
                encoding="utf-8"
            )
            self.assertNotIn(ANON_NESTED_REFID, named_namespace)
            self.assertNotIn("<innernamespace", named_namespace)


class MermaidTagConversionTest(unittest.TestCase):
    """<mermaid> タグをコード フェンスと Figure: 行へ変換する処理を確認する。"""

    def _convert(self, body):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            xml_dir = Path(temp_dir_text)
            xml_path = xml_dir / "sample.xml"
            xml_path.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<doxygen><detaileddescription>\n"
                f"{body}\n"
                "</detaileddescription></doxygen>\n",
                encoding="utf-8",
                newline="\n",
            )
            subprocess.run(
                [BASH, str(PREPROCESS_SCRIPT), str(xml_dir)],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            transformed = xml_path.read_text(encoding="utf-8")
        # 変換後も XML として整形式であること
        root = ET.fromstring(transformed)
        return transformed, "".join(root.itertext())

    def test_mermaid_tag_with_caption_becomes_fence_and_figure_line(self):
        transformed, text = self._convert(
            '<para><mermaid caption="lock の取得">    sequenceDiagram\n'
            "        A-&gt;&gt;B: options, &amp;scope_out\n"
            "        opt n &gt; 0\n"
            "            B-&gt;&gt;B: __flag__ a* b\n"
            "        end</mermaid>\n"
            "</para>"
        )

        self.assertNotIn("<mermaid", transformed)
        self.assertNotIn("</mermaid>", transformed)
        # 本文の XML 実体参照は復号せずに保持する (Doxybook2 が復号する)
        self.assertIn("A-&gt;&gt;B: options, &amp;scope_out", transformed)
        # 共通の字下げを除き、相対的な字下げは保つ
        self.assertIn(
            "\n\n```mermaid\n"
            "sequenceDiagram\n"
            "    A->>B: options, &scope_out\n"
            "    opt n > 0\n"
            "        B->>B: __flag__ a* b\n"
            "    end\n"
            "```\n\n"
            "Figure: lock の取得\n\n",
            text,
        )

    def test_mermaid_tag_without_caption_becomes_fence_only(self):
        # 入力 Markdown の ```mermaid は caption 属性のない <mermaid> になり、
        # Figure: 行は後続の段落として出力される。
        transformed, text = self._convert(
            "<para><mermaid>flowchart LR\n"
            "    A --&gt; B</mermaid>\n"
            "</para>\n"
            "<para>Figure: ページの図 </para>"
        )

        self.assertNotIn("<mermaid", transformed)
        self.assertIn("\n\n```mermaid\nflowchart LR\n    A --> B\n```\n\n", text)
        self.assertEqual(text.count("Figure:"), 1)
        self.assertIn("Figure: ページの図", text)

    def test_empty_caption_is_treated_as_no_caption(self):
        _, text = self._convert(
            '<para><mermaid caption="">flowchart LR\n    A --&gt; B</mermaid></para>'
        )

        self.assertIn("```mermaid\nflowchart LR\n    A --> B\n```", text)
        self.assertNotIn("Figure:", text)

    def test_caption_symbols_become_numeric_character_references(self):
        transformed, text = self._convert(
            '<para><mermaid caption="Foo&lt;T&gt;::operator* の図 operator[] ~Foo `q` C:\\dir '
            '__init__ a_b $x &amp; &quot;s&quot;">flowchart TD\n'
            "    n0 --&gt; n1</mermaid></para>"
        )

        # Doxybook2 が復号した後の Markdown では、記号が数値文字参照になる
        self.assertIn(
            "Figure: Foo&#60;T&#62;::operator&#42; の図 operator&#91;&#93; &#126;Foo "
            "&#96;q&#96; C:&#92;dir __init__ a_b $x & \"s\"\n",
            text,
        )
        # XML 上では数値文字参照の & をエスケープする
        self.assertIn("operator&amp;#42;", transformed)

    def test_plantuml_and_mermaid_tags_are_both_converted(self):
        transformed, text = self._convert(
            "<para><plantuml>\ncaption uml\nA -&gt; B\n</plantuml></para>\n"
            '<para><mermaid caption="mmd">flowchart TD\n    n0 --&gt; n1</mermaid></para>'
        )

        self.assertNotIn("<plantuml", transformed)
        self.assertNotIn("<mermaid", transformed)
        self.assertIn("```plantuml\n@startuml\n", text)
        self.assertIn("\n@enduml\n```", text)
        self.assertIn("```mermaid\nflowchart TD\n    n0 --> n1\n```\n\nFigure: mmd\n", text)

    def test_multiple_mermaid_tags_in_one_file_are_converted_separately(self):
        _, text = self._convert(
            '<para><mermaid caption="first">flowchart TD\n    a --&gt; b</mermaid></para>\n'
            '<para><mermaid caption="second">flowchart BT\n    c --&gt; d</mermaid></para>'
        )

        self.assertIn("```mermaid\nflowchart TD\n    a --> b\n```\n\nFigure: first\n", text)
        self.assertIn("```mermaid\nflowchart BT\n    c --> d\n```\n\nFigure: second\n", text)


if __name__ == "__main__":
    unittest.main()
