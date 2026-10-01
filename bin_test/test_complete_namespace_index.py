#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "complete-namespace-index.py"
)
SPEC = importlib.util.spec_from_file_location("complete_namespace_index", SCRIPT_PATH)
complete_namespace_index = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = complete_namespace_index
SPEC.loader.exec_module(complete_namespace_index)


HEADER = """---
author: doxygen and doxybook2
---

# 名前空間の一覧

::: {.collapsible-list open-level=-1}
"""

FOOTER = ":::\n"


class CompleteNamespaceIndexTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.markdown_dir = Path(self.temp_dir.name)
        self.index_path = self.markdown_dir / "index_namespaces.md"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_index(self, entry_lines):
        self.index_path.write_text(
            HEADER + "".join(line + "\n" for line in entry_lines) + FOOTER,
            encoding="utf-8",
        )

    def _entry_lines(self):
        lines = self.index_path.read_text(encoding="utf-8").split("\n")

        return [
            line for line in lines
            if complete_namespace_index.parse_entry(line) is not None
        ]

    def test_missing_parent_entry_is_completed_without_link(self):
        self._write_index([
            "    - 📄 [cplat::regex_detail](Namespaces/namespacecplat_1_1regex__detail.md)",
        ])

        inserted = complete_namespace_index.complete_namespace_index(self.index_path)

        self.assertEqual(inserted, 1)
        self.assertEqual(
            self._entry_lines(),
            [
                "- 📄 cplat",
                "    - 📄 [cplat::regex_detail](Namespaces/namespacecplat_1_1regex__detail.md)",
            ],
        )

    def test_multiple_missing_ancestors_are_completed_from_shallowest(self):
        self._write_index([
            "        - 📄 [a::b::c](Namespaces/namespacea_1_1b_1_1c.md)",
        ])

        inserted = complete_namespace_index.complete_namespace_index(self.index_path)

        self.assertEqual(inserted, 2)
        self.assertEqual(
            self._entry_lines(),
            [
                "- 📄 a",
                "    - 📄 a::b",
                "        - 📄 [a::b::c](Namespaces/namespacea_1_1b_1_1c.md)",
            ],
        )

    def test_existing_parent_entry_is_left_untouched(self):
        entry_lines = [
            "- 📄 [cplat](Namespaces/namespacecplat.md)",
            "    - 📄 [cplat::regex_detail](Namespaces/namespacecplat_1_1regex__detail.md)",
        ]
        self._write_index(entry_lines)
        original = self.index_path.read_text(encoding="utf-8")

        inserted = complete_namespace_index.complete_namespace_index(self.index_path)

        self.assertEqual(inserted, 0)
        self.assertEqual(self.index_path.read_text(encoding="utf-8"), original)

    def test_sibling_entries_share_a_single_completed_parent(self):
        self._write_index([
            "    - 📄 [cplat::regex_detail](Namespaces/namespacecplat_1_1regex__detail.md)",
            "    - 📄 [cplat::text_detail](Namespaces/namespacecplat_1_1text__detail.md)",
        ])

        inserted = complete_namespace_index.complete_namespace_index(self.index_path)

        self.assertEqual(inserted, 1)
        self.assertEqual(
            self._entry_lines(),
            [
                "- 📄 cplat",
                "    - 📄 [cplat::regex_detail](Namespaces/namespacecplat_1_1regex__detail.md)",
                "    - 📄 [cplat::text_detail](Namespaces/namespacecplat_1_1text__detail.md)",
            ],
        )

    def test_completion_is_idempotent(self):
        self._write_index([
            "    - 📄 [cplat::regex_detail](Namespaces/namespacecplat_1_1regex__detail.md)",
        ])

        complete_namespace_index.complete_namespace_index(self.index_path)
        first_result = self.index_path.read_text(encoding="utf-8")
        inserted = complete_namespace_index.complete_namespace_index(self.index_path)

        self.assertEqual(inserted, 0)
        self.assertEqual(self.index_path.read_text(encoding="utf-8"), first_result)


if __name__ == "__main__":
    unittest.main()
