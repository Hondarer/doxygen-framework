#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import contextlib
import io
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
                "api_8h.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api_8h" kind="file">
    <compoundname>api.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="api_export" static="no">
        <name>api_export</name>
        <location file="include/api.h" line="10" bodyfile="include/api.h" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="api_to_lib" static="no">
        <name>api_to_lib</name>
        <references refid="c_leaf" compoundref="file__c_8c">lib_leaf</references>
        <location file="include/api.h" line="20" bodyfile="include/api.h" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "internal_8h.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="internal_8h" kind="file">
    <compoundname>internal.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="internal_to_lib" static="no">
        <name>internal_to_lib</name>
        <references refid="c_leaf" compoundref="file__c_8c">lib_leaf</references>
        <location file="include_internal/internal.h" line="10" bodyfile="include_internal/internal.h" bodystart="10"/>
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

            self.assertEqual(by_id["a_leaf"]["dependencyLevel"], 1)
            self.assertEqual(by_id["a_leaf"]["dependencyClass"], "leaf-static")
            self.assertEqual(by_id["b_leaf"]["dependencyLevel"], 1001)
            self.assertEqual(by_id["b_leaf"]["dependencyRank"], 1)
            self.assertEqual(by_id["b_leaf"]["dependencyClass"], "leaf-global")
            self.assertEqual(by_id["c_leaf"]["dependencyLevel"], 1003)
            self.assertEqual(by_id["a_local"]["dependencyLevel"], 2001)
            self.assertEqual(by_id["a_local"]["dependencyRank"], 2)
            self.assertEqual(by_id["a_local"]["dependencyDepth"], 1)
            self.assertEqual(by_id["a_local"]["dependencyClass"], "file-local")
            self.assertEqual(by_id["c_user"]["dependencyLevel"], 3001)
            self.assertEqual(by_id["c_user"]["dependencyClass"], "libsrc-file-caller")
            self.assertEqual(by_id["a_cross"]["dependencyLevel"], 4001)
            self.assertEqual(by_id["a_cross"]["dependencyClass"], "src-file-caller")
            self.assertEqual(by_id["a_to_lib"]["dependencyLevel"], 5001)
            self.assertEqual(by_id["a_to_lib"]["dependencyClass"], "other-to-libsrc-caller")
            self.assertEqual(by_id["a_to_lib"]["sourceArea"], "src")
            self.assertEqual(by_id["a_to_lib"]["maxCalleeArea"], "libsrc")
            self.assertEqual(by_id["a_to_lib"]["dominantCallKind"], "other-to-libsrc-caller")
            self.assertEqual(by_id["api_to_lib"]["dependencyClass"], "other-to-libsrc-caller")
            self.assertEqual(by_id["api_to_lib"]["sourceArea"], "include")
            self.assertEqual(by_id["api_to_lib"]["dominantCallKind"], "other-to-libsrc-caller")
            self.assertTrue(by_id["api_to_lib"]["isExported"])
            self.assertEqual(by_id["internal_to_lib"]["dependencyClass"], "other-to-libsrc-caller")
            self.assertEqual(by_id["internal_to_lib"]["sourceArea"], "include_internal")
            self.assertEqual(by_id["internal_to_lib"]["dominantCallKind"], "other-to-libsrc-caller")
            self.assertFalse(by_id["internal_to_lib"]["isExported"])
            self.assertEqual(by_id["a_cross"]["crossFileCalleeCount"], 1)
            self.assertTrue(by_id["api_export"]["isExported"])
            self.assertFalse(by_id["d_leaf"]["isExported"])
            self.assertEqual(data["summary"]["exportCount"], 2)
            file_by_path = {row["path"]: row for row in data["files"]}
            self.assertEqual(file_by_path["include/api.h"]["exportCount"], 2)
            self.assertEqual(file_by_path["include_internal/internal.h"]["exportCount"], 0)
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
            self.assertIn("exportCount", fieldnames)
            with (output_dir / "dependency-functions.csv").open(encoding="utf-8", newline="") as f:
                fieldnames = csv.DictReader(f).fieldnames
            self.assertIn("isExported", fieldnames)

            data_js = (output_dir / "dependency-data.js").read_text(encoding="utf-8")
            self.assertTrue(data_js.startswith("window.DoxyfwDependencyData = "))
            payload = data_js.removeprefix("window.DoxyfwDependencyData = ").rstrip(";\n")
            self.assertEqual(json.loads(payload)["summary"]["functionCount"], 11)

            index_html = (output_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn('id="overviewGraphMenu"', index_html)
            self.assertIn('data-svg-scope="viewport"', index_html)
            self.assertIn('data-svg-scope="full"', index_html)
            self.assertIn('data-action="fit"', index_html)
            self.assertIn('data-action="relayout"', index_html)
            self.assertIn('data-action="reset"', index_html)
            self.assertIn('role="separator"', index_html)
            self.assertIn("function buildOverviewSvg(scope)", index_html)
            self.assertIn("function downloadOverviewSvg(scope)", index_html)
            self.assertIn("function fitOverviewGraph()", index_html)
            self.assertIn("function handleOverviewGraphMenuAction(action)", index_html)
            self.assertIn("function overviewFileEdgeLength(edge, maxLength, minLength)", index_html)
            self.assertIn('edgeLength: function (edge) { return overviewFileEdgeLength(edge, 140, 128); }', index_html)
            self.assertIn('idealEdgeLength: function (edge) { return overviewFileEdgeLength(edge, 128, 116); }', index_html)
            self.assertIn("function overviewSelectionState(edgeMap)", index_html)
            self.assertIn("dep-file-node-muted", index_html)
            self.assertIn("scrollbar-color:", index_html)
            self.assertIn('overviewGraph.addEventListener("auxclick"', index_html)
            self.assertIn('id="themeToggle"', index_html)
            self.assertIn("function applyTheme(theme, persist)", index_html)

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

    def test_include_definition_prefers_libsrc_and_ignores_src_call(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "api.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api_8h" kind="file">
    <compoundname>api.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="api_decl" static="no">
        <name>api_func</name>
        <location file="include/api.h" line="10" bodyfile="include/api.h" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "api_linux.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api__linux_8c" kind="file">
    <compoundname>api_linux.c</compoundname>
    <location file="libsrc/api_linux.c"/>
    <programlisting>
      <codeline lineno="80"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="api_decl">api_func</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "api_windows.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api__windows_8c" kind="file">
    <compoundname>api_windows.c</compoundname>
    <location file="libsrc/api_windows.c"/>
    <programlisting>
      <codeline lineno="40"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="api_decl">api_func</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "tool.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="tool_8c" kind="file">
    <compoundname>tool.c</compoundname>
    <location file="src/tool.c"/>
    <sectiondef>
      <memberdef kind="function" id="tool_user" static="no">
        <name>tool_user</name>
        <references refid="api_decl" compoundref="api_8h">api_func</references>
        <location file="src/tool.c" line="20" bodyfile="src/tool.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
    <programlisting>
      <codeline lineno="20"><highlight class="normal">if (</highlight><ref refid="api_decl">api_func</ref><highlight class="normal">() == 0)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}
            edges = {(row["caller"], row["callee"]): row for row in data["edges"]}

            self.assertEqual(by_id["api_decl"]["file"], "libsrc/api_linux.c")
            self.assertEqual(by_id["api_decl"]["line"], 80)
            self.assertTrue(by_id["api_decl"]["isExported"])
            self.assertEqual(edges[("tool_user", "api_decl")]["calleeFile"], "libsrc/api_linux.c")
            self.assertNotIn("include function definition fallback to src", stderr.getvalue())

    def test_include_definition_src_fallback_warns(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "api.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api_8h" kind="file">
    <compoundname>api.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="tool_api" static="no">
        <name>tool_api</name>
        <location file="include/api.h" line="10" bodyfile="include/api.h" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "tool.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="tool_8c" kind="file">
    <compoundname>tool.c</compoundname>
    <location file="src/tool.c"/>
    <programlisting>
      <codeline lineno="30"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="tool_api">tool_api</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(by_id["tool_api"]["file"], "src/tool.c")
            self.assertEqual(by_id["tool_api"]["line"], 30)
            self.assertIn("Warning: include function definition fallback to src", stderr.getvalue())
            self.assertIn("tool_api", stderr.getvalue())

    def test_src_header_definition_src_fallback_does_not_warn(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "svc_8h.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="svc_8h" kind="file">
    <compoundname>svc.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="svc_api" static="no">
        <name>svc_api</name>
        <location file="src/svc.h" line="10" bodyfile="src/svc.h" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "svc.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="svc_8c" kind="file">
    <compoundname>svc.c</compoundname>
    <location file="src/svc.c"/>
    <programlisting>
      <codeline lineno="30"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="svc_api">svc_api</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "tool.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="tool_8c" kind="file">
    <compoundname>tool.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="tool_user" static="no">
        <name>tool_user</name>
        <references refid="svc_api" compoundref="svc_8h">svc_api</references>
        <location file="src/tool.c" line="20" bodyfile="src/tool.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}
            edges = {(row["caller"], row["callee"]): row for row in data["edges"]}

            self.assertEqual(by_id["svc_api"]["file"], "src/svc.c")
            self.assertEqual(by_id["svc_api"]["line"], 30)
            self.assertEqual(by_id["tool_user"]["dependencyClass"], "src-file-caller")
            self.assertEqual(by_id["tool_user"]["dominantCallKind"], "src-file-caller")
            self.assertEqual(edges[("tool_user", "svc_api")]["calleeFile"], "src/svc.c")
            self.assertNotIn("include function definition fallback to src", stderr.getvalue())

    def test_reverse_boundary_call_warns_and_uses_cross_area(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "lib.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="lib_8c" kind="file">
    <compoundname>lib.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="lib_to_src" static="no">
        <name>lib_to_src</name>
        <references refid="src_leaf" compoundref="src_8c">src_leaf</references>
        <location file="libsrc/lib.c" line="10" bodyfile="libsrc/lib.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "src.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="src_8c" kind="file">
    <compoundname>src.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="src_leaf" static="no">
        <name>src_leaf</name>
        <location file="src/src.c" line="20" bodyfile="src/src.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(by_id["lib_to_src"]["dependencyClass"], "cross-area-caller")
            self.assertEqual(by_id["lib_to_src"]["dominantCallKind"], "cross-area-caller")
            self.assertIn("Warning: reverse-boundary-caller detected", stderr.getvalue())
            self.assertIn("lib_to_src", stderr.getvalue())
            self.assertIn("src_leaf", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
