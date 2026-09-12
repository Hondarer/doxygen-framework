#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "templates" / "inject-groups.py"
SPEC = importlib.util.spec_from_file_location("inject_groups", SCRIPT_PATH)
inject_groups = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inject_groups
SPEC.loader.exec_module(inject_groups)


GROUP_MD = """---
summary: Sample group.
---

<!-- generated -->

# Sample group

## 概要

グループの概要です。

### 概要内の小見出し

概要の詳細です。

## 関数

### sample_a

```cpp
int sample_a(void)
```

sample_a の説明です。

### sample_b

```cpp
int sample_b(void)
```

sample_b の説明です。
"""


class InjectGroupsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.modules_dir = self.root / "Modules"
        self.files_dir = self.root / "Files"
        self.modules_dir.mkdir()
        self.files_dir.mkdir()
        self.group_md = self.modules_dir / "group__SAMPLE.md"
        self.group_md.write_text(GROUP_MD, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_group_md_keeps_overview_separate_from_members(self):
        overview_lines, sections = inject_groups.parse_group_md(self.group_md)

        self.assertEqual(overview_lines[0], "## 概要")
        self.assertIn("### 概要内の小見出し", overview_lines)
        self.assertEqual([name for name, _ in sections[0][1]], ["sample_a", "sample_b"])

    def test_filtered_md_includes_overview_and_selected_members(self):
        overview_lines, sections = inject_groups.parse_group_md(self.group_md)

        result = inject_groups.generate_filtered_md(
            "Sample group", overview_lines, sections, {"sample_a"})

        self.assertIn("## 概要\n\nグループの概要です。", result)
        self.assertIn("### 概要内の小見出し", result)
        self.assertIn("### sample_a", result)
        self.assertNotIn("### sample_b", result)

    def test_embedded_group_shifts_overview_below_group_title(self):
        overview_lines, sections = inject_groups.parse_group_md(self.group_md)

        result = inject_groups.build_embedded_group_section(
            "Sample group", overview_lines, sections, {"sample_a"})

        self.assertIn("!doxyfw-structure-title!## Sample group", result)
        self.assertIn("### 概要", result)
        self.assertIn("#### 概要内の小見出し", result)
        self.assertIn("#### sample_a", result)

    def test_filtered_md_does_not_add_an_empty_overview(self):
        overview_lines, sections = inject_groups.parse_group_md(self.group_md)

        result = inject_groups.generate_filtered_md(
            "Sample group", [], sections, {"sample_a"})

        self.assertNotIn("## 概要", result)
        self.assertIn("### sample_a", result)


if __name__ == "__main__":
    unittest.main()
