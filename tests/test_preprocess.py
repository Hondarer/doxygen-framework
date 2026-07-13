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


if __name__ == "__main__":
    unittest.main()
