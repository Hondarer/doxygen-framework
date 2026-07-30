#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


FRAMEWORK_DIR = Path(__file__).resolve().parents[1]


class Doxybook2TemplatesTest(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("doxygen") and shutil.which("doxybook2"),
        "doxygen and doxybook2 are required",
    )
    def test_type_headings_use_only_language_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            c_header = work_dir / "sample.h"
            c_header.write_text(
                r"""/**
 * @defgroup SAMPLE_GROUP Sample group
 * @{
 */
/** Sample handle. */
typedef struct sample_handle sample_handle;
/** Sample kind. */
typedef enum sample_kind {
    SAMPLE_KIND_ONE = 1
} sample_kind;
/** @} */
""",
                encoding="utf-8",
            )
            cs_source = work_dir / "SampleKind.cs"
            cs_source.write_text(
                """namespace Sample
{
    public enum SampleKind
    {
        One = 1
    }
}
""",
                encoding="utf-8",
            )
            doxyfile = work_dir / "Doxyfile"
            doxyfile.write_text(
                """PROJECT_NAME = sample
OUTPUT_DIRECTORY = {output}
INPUT = {c_header} {cs_source}
FILE_PATTERNS = *.h *.cs
EXTENSION_MAPPING = cs=C#
RECURSIVE = NO
QUIET = YES
WARNINGS = YES
EXTRACT_ALL = YES
GENERATE_HTML = NO
GENERATE_LATEX = NO
GENERATE_XML = YES
XML_OUTPUT = xml
""".format(
                    output=work_dir,
                    c_header=c_header,
                    cs_source=cs_source,
                ),
                encoding="utf-8",
            )
            subprocess.run(
                ["doxygen", str(doxyfile)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            docs_dir = work_dir / "docs"
            docs_dir.mkdir()
            subprocess.run(
                [
                    "doxybook2",
                    "-i",
                    str(work_dir / "xml"),
                    "-o",
                    str(docs_dir),
                    "--config",
                    str(FRAMEWORK_DIR / "doxybook2-config.json"),
                    "--templates",
                    str(FRAMEWORK_DIR / "templates"),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            group_md = (
                docs_dir / "Modules" / "group__SAMPLE__GROUP.md"
            ).read_text(encoding="utf-8")
            namespace_md = (
                docs_dir / "Namespaces" / "namespaceSample.md"
            ).read_text(encoding="utf-8")

            self.assertIn("### sample_handle", group_md)
            self.assertIn("### sample_kind", group_md)
            self.assertNotIn("SAMPLE_GROUP::", group_md)
            self.assertIn("### Sample::SampleKind", namespace_md)


if __name__ == "__main__":
    unittest.main()
