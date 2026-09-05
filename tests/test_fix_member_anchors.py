#!/usr/bin/env python3

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


DOXYFW_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = DOXYFW_ROOT / "templates" / "fix-member-anchors.py"


class FixMemberAnchorsTest(unittest.TestCase):
    def run_script(self, markdown_dir: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(markdown_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_anchor_is_rewritten_when_heading_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            markdown_dir = Path(temp_dir_text)
            (markdown_dir / "Modules").mkdir()
            (markdown_dir / "Classes").mkdir()

            (markdown_dir / "Modules" / "group__API.md").write_text(
                "# API\n\n#### cplat_memory_lock_self\n\n本文です。\n",
                encoding="utf-8",
            )
            target = markdown_dir / "Classes" / "README.md"
            target.write_text(
                "# クラス\n\n"
                "[cplat_memory_lock_self()]"
                "(../Modules/group__API.md#function-cplat-memory-lock-self) を参照。\n",
                encoding="utf-8",
            )

            result = self.run_script(markdown_dir)
            self.assertEqual(result.returncode, 0, result.stderr)

            content = target.read_text(encoding="utf-8")
            self.assertIn("(../Modules/group__API.md#cplat_memory_lock_self)", content)
            self.assertNotIn("#function-", content)

    def test_anchor_is_dropped_when_heading_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            markdown_dir = Path(temp_dir_text)
            (markdown_dir / "Modules").mkdir()

            (markdown_dir / "Modules" / "group__API.md").write_text(
                "# API\n\n本文です。\n", encoding="utf-8"
            )
            target = markdown_dir / "README.md"
            target.write_text(
                "[missing](Modules/group__API.md#function-not-here) を参照。\n",
                encoding="utf-8",
            )

            result = self.run_script(markdown_dir)
            self.assertEqual(result.returncode, 0, result.stderr)

            content = target.read_text(encoding="utf-8")
            self.assertIn("[missing](Modules/group__API.md)", content)
            self.assertNotIn("#function-", content)

    def test_same_page_anchor_and_variable_kind(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            markdown_dir = Path(temp_dir_text)
            target = markdown_dir / "struct.md"
            target.write_text(
                "# 構造体\n\n[key](#variable-key) と [value](#variable-value)\n\n"
                "### key\n\n### value\n",
                encoding="utf-8",
            )

            result = self.run_script(markdown_dir)
            self.assertEqual(result.returncode, 0, result.stderr)

            content = target.read_text(encoding="utf-8")
            self.assertIn("[key](#key)", content)
            self.assertIn("[value](#value)", content)

    def test_file_kind_is_left_untouched(self):
        """#file-xxx.h は patch-index-files.py の担当であり、対象外とする。"""
        with tempfile.TemporaryDirectory() as temp_dir_text:
            markdown_dir = Path(temp_dir_text)
            target = markdown_dir / "index_files.md"
            target.write_text("[add.c](Files/add_8c.md#file-add.c)\n", encoding="utf-8")

            result = self.run_script(markdown_dir)
            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertIn(
                "[add.c](Files/add_8c.md#file-add.c)",
                target.read_text(encoding="utf-8"),
            )

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            markdown_dir = Path(temp_dir_text)
            target = markdown_dir / "page.md"
            target.write_text(
                "[f](#function-my-func)\n\n### my_func\n", encoding="utf-8"
            )

            self.assertEqual(self.run_script(markdown_dir).returncode, 0)
            first = target.read_text(encoding="utf-8")
            self.assertEqual(self.run_script(markdown_dir).returncode, 0)
            self.assertEqual(first, target.read_text(encoding="utf-8"))

    def test_headings_in_code_blocks_are_not_collected(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            markdown_dir = Path(temp_dir_text)
            target = markdown_dir / "page.md"
            target.write_text(
                "[f](#function-my-func)\n\n```c\n### my_func\n```\n",
                encoding="utf-8",
            )

            self.assertEqual(self.run_script(markdown_dir).returncode, 0)
            self.assertIn("[f]()", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
