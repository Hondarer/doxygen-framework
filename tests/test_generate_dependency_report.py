#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "templates" / "generate-dependency-report.py"
SPEC = importlib.util.spec_from_file_location("generate_dependency_report", SCRIPT_PATH)
generate_dependency_report = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generate_dependency_report
SPEC.loader.exec_module(generate_dependency_report)


def write_xml(directory, name, content):
    (directory / name).write_text(content, encoding="utf-8")


class GenerateDependencyReportTest(unittest.TestCase):
    def test_dependency_levels_and_classes(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "file_a.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__a_8c" kind="file">
    <compoundname>file_a.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="a_leaf" static="yes">
        <name>leaf</name>
        <location file="src/file_a.c" line="10" bodyfile="src/file_a.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="a_local" static="yes">
        <name>local_user</name>
        <references refid="a_leaf" compoundref="file__a_8c">leaf</references>
        <location file="src/file_a.c" line="20" bodyfile="src/file_a.c" bodystart="20"/>
      </memberdef>
      <memberdef kind="function" id="a_cross" static="no">
        <name>cross_user</name>
        <references refid="b_leaf" compoundref="file__b_8c">other_leaf</references>
        <location file="src/file_a.c" line="30" bodyfile="src/file_a.c" bodystart="30"/>
      </memberdef>
      <memberdef kind="function" id="a_to_lib" static="no">
        <name>app_user</name>
        <references refid="c_leaf" compoundref="file__c_8c">lib_leaf</references>
        <location file="src/file_a.c" line="40" bodyfile="src/file_a.c" bodystart="40"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "file_b.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__b_8c" kind="file">
    <compoundname>file_b.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="b_leaf" static="no">
        <name>other_leaf</name>
        <location file="src/file_b.c" line="10" bodyfile="src/file_b.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "file_c.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__c_8c" kind="file">
    <compoundname>file_c.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="c_leaf" static="no">
        <name>lib_leaf</name>
        <location file="libsrc/file_c.c" line="10" bodyfile="libsrc/file_c.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="c_user" static="no">
        <name>lib_user</name>
        <references refid="d_leaf" compoundref="file__d_8c">lib_other_leaf</references>
        <location file="libsrc/file_c.c" line="20" bodyfile="libsrc/file_c.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "file_d.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__d_8c" kind="file">
    <compoundname>file_d.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="d_leaf" static="no">
        <name>lib_other_leaf</name>
        <location file="libsrc/file_d.c" line="10" bodyfile="libsrc/file_d.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(by_id["a_leaf"]["dependencyLevel"], 0)
            self.assertEqual(by_id["a_leaf"]["dependencyClass"], "leaf-static")
            self.assertEqual(by_id["b_leaf"]["dependencyLevel"], 1)
            self.assertEqual(by_id["b_leaf"]["dependencyRank"], 1)
            self.assertEqual(by_id["b_leaf"]["dependencyClass"], "leaf-global")
            self.assertEqual(by_id["a_local"]["dependencyLevel"], 2001)
            self.assertEqual(by_id["a_local"]["dependencyRank"], 2)
            self.assertEqual(by_id["a_local"]["dependencyDepth"], 1)
            self.assertEqual(by_id["a_local"]["dependencyClass"], "file-local")
            self.assertEqual(by_id["c_user"]["dependencyLevel"], 3001)
            self.assertEqual(by_id["c_user"]["dependencyClass"], "libsrc-file-caller")
            self.assertEqual(by_id["a_cross"]["dependencyLevel"], 4001)
            self.assertEqual(by_id["a_cross"]["dependencyClass"], "src-file-caller")
            self.assertEqual(by_id["a_to_lib"]["dependencyLevel"], 5001)
            self.assertEqual(by_id["a_to_lib"]["dependencyClass"], "src-to-libsrc-caller")
            self.assertEqual(by_id["a_to_lib"]["sourceArea"], "src")
            self.assertEqual(by_id["a_to_lib"]["maxCalleeArea"], "libsrc")
            self.assertEqual(by_id["a_to_lib"]["dominantCallKind"], "src-to-libsrc-caller")
            self.assertEqual(by_id["a_cross"]["crossFileCalleeCount"], 1)
            self.assertTrue((output_dir / "index.html").is_file())
            self.assertTrue((output_dir / "dependency-data.js").is_file())
            self.assertTrue((output_dir / "dependency-functions.csv").is_file())
            self.assertTrue((output_dir / "dependency-files.csv").is_file())
            self.assertTrue((output_dir / "cytoscape.min.js").is_file())
            self.assertTrue((output_dir / "cytoscape.LICENSE.txt").is_file())
            self.assertTrue((output_dir / "webcola.min.js").is_file())
            self.assertTrue((output_dir / "webcola.LICENSE.txt").is_file())
            self.assertTrue((output_dir / "cytoscape-cola.js").is_file())
            self.assertTrue((output_dir / "cytoscape-cola.LICENSE.txt").is_file())
            for file_row in data["files"]:
                self.assertNotIn("dominantClass", file_row)
                self.assertIn("classes", file_row)
            with (output_dir / "dependency-files.csv").open(encoding="utf-8", newline="") as f:
                fieldnames = csv.DictReader(f).fieldnames
            self.assertNotIn("dominantClass", fieldnames)
            self.assertIn("classes", fieldnames)

            data_js = (output_dir / "dependency-data.js").read_text(encoding="utf-8")
            self.assertTrue(data_js.startswith("window.DoxyfwDependencyData = "))
            payload = data_js.removeprefix("window.DoxyfwDependencyData = ").rstrip(";\n")
            self.assertEqual(json.loads(payload)["summary"]["functionCount"], 8)

    def test_cycle_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "cycle.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="cycle_8c" kind="file">
    <compoundname>cycle.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="cycle_a" static="yes">
        <name>cycle_a</name>
        <references refid="cycle_b" compoundref="cycle_8c">cycle_b</references>
        <location file="src/cycle.c" line="10" bodyfile="src/cycle.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="cycle_b" static="yes">
        <name>cycle_b</name>
        <references refid="cycle_a" compoundref="cycle_8c">cycle_a</references>
        <location file="src/cycle.c" line="20" bodyfile="src/cycle.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(data["summary"]["cycleGroupCount"], 1)
            self.assertIsNone(by_id["cycle_a"]["dependencyLevel"])
            self.assertEqual(by_id["cycle_a"]["dependencyClass"], "cycle")
            self.assertIsNone(by_id["cycle_b"]["dependencyLevel"])
            self.assertEqual(by_id["cycle_b"]["dependencyClass"], "cycle")


if __name__ == "__main__":
    unittest.main()
