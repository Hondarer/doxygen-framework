#!/usr/bin/env python3

import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


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
                [str(PREPROCESS_SCRIPT), str(xml_dir)],
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
            [str(PREPROCESS_SCRIPT), str(xml_dir)],
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


if __name__ == "__main__":
    unittest.main()
