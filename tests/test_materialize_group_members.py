#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "materialize-group-members.py"
)
SPEC = importlib.util.spec_from_file_location("materialize_group_members", SCRIPT_PATH)
materialize_group_members = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = materialize_group_members
SPEC.loader.exec_module(materialize_group_members)


class MaterializeGroupMembersTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.xml_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_fixture(self, source_name="src/sample.c", index_ref_override=None):
        members = [
            ("define", "SAMPLE_DEFINE", "1" * 32, ""),
            ("enum", "SAMPLE_ENUM", "2" * 32, ""),
            ("typedef", "sample_type", "3" * 32, ""),
            ("variable", "sample_value", "4" * 32, ""),
            (
                "function",
                "sample_function",
                "5" * 32,
                ' bodyfile="src/sample.c" bodystart="42" bodyend="45"'
                ' declfile="include/sample.h" declline="12" declcolumn="5"',
            ),
        ]
        group_blocks = []
        file_refs = []
        index_refs = []
        for kind, name, digest, extra_location in members:
            member_id = "group__SAMPLE_1a{}".format(digest)
            location_file = source_name
            location_line = "10"
            if kind == "function":
                location_file = "include/sample.h"
                location_line = "12"
            group_blocks.append(
                """
    <memberdef kind="{kind}" id="{member_id}" prot="public" static="no">
      <type>int</type>
      <definition>int {name}</definition>
      <argsstring>()</argsstring>
      <name>{name}</name>
      <briefdescription><para>{name} brief</para></briefdescription>
      <detaileddescription><para>{name} detail</para></detaileddescription>
      <inbodydescription/>
      <location file="{location_file}" line="{location_line}" column="3"{extra_location}/>
    </memberdef>""".format(
                    kind=kind,
                    member_id=member_id,
                    name=name,
                    location_file=location_file,
                    location_line=location_line,
                    extra_location=extra_location,
                )
            )
            file_refs.append(
                '    <member refid="{}" kind="{}"><name>{}</name></member>'.format(
                    member_id, kind, name
                )
            )
            index_id = member_id
            if index_ref_override is not None and kind == "function":
                index_id = index_ref_override
            index_refs.append(
                '  <member refid="{}" kind="{}"><name>{}</name></member>'.format(
                    index_id, kind, name
                )
            )

        (self.xml_dir / "group__SAMPLE.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
<compounddef id="group__SAMPLE" kind="group">
  <compoundname>SAMPLE</compoundname>
  <sectiondef kind="func">
{members}
  </sectiondef>
</compounddef>
</doxygen>
""".format(members="\n".join(group_blocks)),
            encoding="utf-8",
        )
        (self.xml_dir / "sample_8c.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
<compounddef id="sample_8c" kind="file" language="C++">
  <compoundname>{source_name}</compoundname>
  <sectiondef kind="func">
{refs}
  </sectiondef>
  <innerclass refid="structSAMPLE" prot="public">SAMPLE</innerclass>
  <location file="{source_name}"/>
</compounddef>
</doxygen>
""".format(source_name=source_name, refs="\n".join(file_refs)),
            encoding="utf-8",
        )
        (self.xml_dir / "structSAMPLE.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
<compounddef id="structSAMPLE" kind="struct">
  <compoundname>SAMPLE</compoundname>
  <location file="src/sample.c" line="3"/>
</compounddef>
</doxygen>
""",
            encoding="utf-8",
        )
        (self.xml_dir / "index.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<doxygenindex>
<compound refid="sample_8c" kind="file">
  <name>{source_name}</name>
{refs}
</compound>
<compound refid="group__SAMPLE" kind="group"><name>SAMPLE</name></compound>
<compound refid="structSAMPLE" kind="struct"><name>SAMPLE</name></compound>
</doxygenindex>
""".format(source_name=source_name, refs="\n".join(index_refs)),
            encoding="utf-8",
        )
        return members

    def test_materializes_every_memberdef_kind_and_updates_index(self):
        members = self.write_fixture()

        materialized, skipped = materialize_group_members.materialize(self.xml_dir)

        self.assertEqual(materialized, 5)
        self.assertEqual(skipped, 0)
        source_xml = (self.xml_dir / "sample_8c.xml").read_text(encoding="utf-8")
        index_xml = (self.xml_dir / "index.xml").read_text(encoding="utf-8")
        for kind, name, digest, _ in members:
            clone_id = "sample_8c_1a{}".format(digest)
            self.assertIn('<memberdef kind="{}" id="{}"'.format(kind, clone_id), source_xml)
            self.assertIn('refid="{}" kind="{}"'.format(clone_id, kind), index_xml)
            self.assertIn("<name>{}</name>".format(name), source_xml)
        self.assertIn('<innerclass refid="structSAMPLE"', source_xml)
        self.assertIn(
            '<location file="src/sample.c" line="42"'
            ' bodyfile="src/sample.c" bodystart="42" bodyend="45"',
            source_xml,
        )
        self.assertNotIn('line="42" column=', source_xml)
        self.assertIn('declfile="include/sample.h"', source_xml)

    def test_second_run_is_idempotent(self):
        self.write_fixture()
        materialize_group_members.materialize(self.xml_dir)
        before = {
            path.name: path.read_bytes() for path in sorted(self.xml_dir.glob("*.xml"))
        }

        materialized, skipped = materialize_group_members.materialize(self.xml_dir)

        after = {
            path.name: path.read_bytes() for path in sorted(self.xml_dir.glob("*.xml"))
        }
        self.assertEqual(materialized, 0)
        self.assertEqual(skipped, 5)
        self.assertEqual(after, before)

    def test_path_mismatch_fails_without_writing(self):
        self.write_fixture(source_name="src/other.c")
        source_path = self.xml_dir / "sample_8c.xml"
        index_path = self.xml_dir / "index.xml"
        before_source = source_path.read_bytes()
        before_index = index_path.read_bytes()

        with self.assertRaises(materialize_group_members.MaterializeError):
            materialize_group_members.materialize(self.xml_dir)

        self.assertEqual(source_path.read_bytes(), before_source)
        self.assertEqual(index_path.read_bytes(), before_index)

    def test_missing_index_reference_fails_without_writing(self):
        self.write_fixture(index_ref_override="group__UNKNOWN_1a" + "f" * 32)
        source_path = self.xml_dir / "sample_8c.xml"
        index_path = self.xml_dir / "index.xml"
        before_source = source_path.read_bytes()
        before_index = index_path.read_bytes()

        with self.assertRaises(materialize_group_members.MaterializeError):
            materialize_group_members.materialize(self.xml_dir)

        self.assertEqual(source_path.read_bytes(), before_source)
        self.assertEqual(index_path.read_bytes(), before_index)

    def test_generated_id_collision_fails_without_writing(self):
        self.write_fixture()
        source_path = self.xml_dir / "sample_8c.xml"
        source_xml = source_path.read_text(encoding="utf-8")
        collision = """
    <memberdef kind="variable" id="sample_8c_1a11111111111111111111111111111111">
      <name>collision</name>
      <location file="src/sample.c" line="90"/>
    </memberdef>
"""
        source_xml = source_xml.replace("  </sectiondef>", collision + "  </sectiondef>")
        source_path.write_text(source_xml, encoding="utf-8")
        before_source = source_path.read_bytes()
        before_index = (self.xml_dir / "index.xml").read_bytes()

        with self.assertRaises(materialize_group_members.MaterializeError):
            materialize_group_members.materialize(self.xml_dir)

        self.assertEqual(source_path.read_bytes(), before_source)
        self.assertEqual((self.xml_dir / "index.xml").read_bytes(), before_index)

    @unittest.skipUnless(
        shutil.which("doxygen") and shutil.which("doxybook2"),
        "doxygen and doxybook2 are required",
    )
    def test_doxybook2_renders_all_kinds_as_regular_file_members(self):
        source_path = self.xml_dir / "sample.c"
        source_path.write_text(
            r"""/**
 * @defgroup SAMPLE Sample group
 * @{
 */
/** Sample macro. */
#define SAMPLE_MACRO 1
/** Sample typedef. */
typedef int sample_type;
/** Sample enum. */
enum sample_enum {
    SAMPLE_ENUM_VALUE = 1
};
/** Sample variable. */
int sample_variable = 1;
/** Sample structure. */
struct sample_struct {
    int value;
};
/** Sample function. */
int sample_function(void)
{
    return SAMPLE_MACRO;
}
/** @} */
""",
            encoding="utf-8",
        )
        doxyfile_path = self.xml_dir / "Doxyfile"
        doxyfile_path.write_text(
            """PROJECT_NAME = sample
OUTPUT_DIRECTORY = {output}
INPUT = {source}
FILE_PATTERNS = *.c
RECURSIVE = NO
QUIET = YES
WARNINGS = YES
EXTRACT_ALL = YES
OPTIMIZE_OUTPUT_FOR_C = YES
GENERATE_HTML = NO
GENERATE_LATEX = NO
GENERATE_XML = YES
XML_OUTPUT = xml
""".format(output=self.xml_dir, source=source_path),
            encoding="utf-8",
        )
        subprocess.run(
            ["doxygen", str(doxyfile_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        generated_xml_dir = self.xml_dir / "xml"

        materialized, _ = materialize_group_members.materialize(generated_xml_dir)

        self.assertEqual(materialized, 5)
        docs_dir = self.xml_dir / "docs"
        docs_dir.mkdir()
        framework_dir = SCRIPT_PATH.parents[1]
        subprocess.run(
            [
                "doxybook2",
                "-i",
                str(generated_xml_dir),
                "-o",
                str(docs_dir),
                "--config",
                str(framework_dir / "doxybook2-config.json"),
                "--templates",
                str(framework_dir / "templates"),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        file_md = (docs_dir / "Files" / "sample_8c.md").read_text(encoding="utf-8")
        self.assertIn("### SAMPLE_MACRO", file_md)
        self.assertIn("### sample_type", file_md)
        self.assertIn("### sample_enum", file_md)
        self.assertIn("### sample_variable", file_md)
        self.assertIn("### sample_function", file_md)
        self.assertIn("structsample__struct.md", file_md)


if __name__ == "__main__":
    unittest.main()
