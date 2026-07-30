#!/usr/bin/env python3

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


DOXYFW_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = DOXYFW_ROOT.parents[1]
POSTPROCESS_SCRIPT = DOXYFW_ROOT / "templates" / "postprocess.sh"


class PostprocessTest(unittest.TestCase):
    def test_backslash_escapes_are_preserved_when_xpg_echo_is_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            markdown_dir = temp_dir / "markdown"
            doxygen_rundir = temp_dir / "input"
            markdown_dir.mkdir()
            doxygen_rundir.mkdir()

            markdown_path = markdown_dir / "sample.md"
            markdown_path.write_text(
                r"""# Escape preservation

```plantuml
rectangle "main\n(calc.c)" as n1
```

```c
printf("value=%d\n", value);
const char *escapes = "\t\c\\";
```

!include missing\n.md
""",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "BASHOPTS": "xpg_echo",
                    "WORKSPACE_DIR": str(WORKSPACE_ROOT),
                    "DOXYGEN_RUNDIR": str(doxygen_rundir),
                    "DOXYFILE_PART_PATH": "",
                    "CATEGORY": "",
                    "CATEGORY_ID": "",
                    "DOXYFW_TAGFILE": "",
                }
            )

            subprocess.run(
                [str(POSTPROCESS_SCRIPT), str(markdown_dir)],
                cwd=DOXYFW_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            transformed = markdown_path.read_text(encoding="utf-8")
            self.assertIn(r'rectangle "main\n(calc.c)" as n1', transformed)
            self.assertIn(r'printf("value=%d\n", value);', transformed)
            self.assertIn(r'const char *escapes = "\t\c\\";', transformed)
            self.assertIn(r"!include missing\n.md", transformed)


if __name__ == "__main__":
    unittest.main()
