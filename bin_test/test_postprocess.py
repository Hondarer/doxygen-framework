#!/usr/bin/env python3

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import shutil

# Windows の subprocess は System32 を PATH より先に探すため、名前だけで起動すると
# WSL の bash.exe を選ぶことがある。PATH 上の bash (Git Bash など) を明示して使う。
# see: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw
BASH = shutil.which("bash") or "bash"


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
                [BASH, str(POSTPROCESS_SCRIPT), str(markdown_dir)],
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

    def _run_postprocess(self, markdown_text):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            markdown_dir = temp_dir / "markdown"
            doxygen_rundir = temp_dir / "input"
            markdown_dir.mkdir()
            doxygen_rundir.mkdir()

            markdown_path = markdown_dir / "sample.md"
            markdown_path.write_text(markdown_text, encoding="utf-8", newline="\n")

            env = os.environ.copy()
            env.update(
                {
                    "WORKSPACE_DIR": str(WORKSPACE_ROOT),
                    "DOXYGEN_RUNDIR": str(doxygen_rundir),
                    "DOXYFILE_PART_PATH": "",
                    "CATEGORY": "",
                    "CATEGORY_ID": "",
                    "DOXYFW_TAGFILE": "",
                }
            )

            subprocess.run(
                [BASH, str(POSTPROCESS_SCRIPT), str(markdown_dir)],
                cwd=DOXYFW_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            return markdown_path.read_text(encoding="utf-8")

    def test_mermaid_fence_content_is_not_rewritten(self):
        transformed = self._run_postprocess(
            """# Mermaid

```mermaid
sequenceDiagram
    A->>B: __flag__ a* b
    A->>B: int * value
    n0["__x__ c* d"] --> n1
```

Figure: __init__ の図

```c
int * value;
```
"""
        )

        # Mermaid のコード フェンス内は __ もポインターの空白も変更しない
        self.assertIn("    A->>B: __flag__ a* b\n", transformed)
        self.assertIn("    A->>B: int * value\n", transformed)
        self.assertIn('    n0["__x__ c* d"] --> n1\n', transformed)
        # コード フェンス外の Figure: 行は本文として __ をエスケープする
        self.assertIn("Figure: &#95;&#95;init&#95;&#95; の図\n", transformed)
        # Mermaid 以外のコード フェンスではポインターの空白の正規化を維持する
        self.assertIn("int *value;\n", transformed)

    def test_plantuml_fence_keeps_underscore_escape(self):
        transformed = self._run_postprocess(
            """# PlantUML

```plantuml
@startuml
rectangle "__attribute__" as n1
@enduml
```
"""
        )

        self.assertIn('rectangle "~_~_attribute~_~_" as n1\n', transformed)

    def test_details_only_graph_is_closed_after_figure_line(self):
        transformed = self._run_postprocess(
            """# Details

#### DOXYFW_DETAILS_ONLY 呼び出し先

```mermaid
flowchart TD
    n0["divide"] --> n1["check_zero"]
```

Figure: divide の呼び出し先

次の段落です。
"""
        )

        self.assertNotIn("DOXYFW_DETAILS_ONLY", transformed)
        self.assertIn(
            "<!--details:-->\n"
            "\n"
            "**呼び出し先**\n"
            "\n"
            "```mermaid\n"
            "flowchart TD\n"
            '    n0["divide"] --> n1["check_zero"]\n'
            "```\n"
            "\n"
            "Figure: divide の呼び出し先\n"
            "\n"
            "<!--:details-->\n"
            "\n"
            "次の段落です。\n",
            transformed,
        )

    def test_details_only_graph_without_figure_line_is_closed_after_fence(self):
        transformed = self._run_postprocess(
            """# Details

#### DOXYFW_DETAILS_ONLY 呼び出し先

```plantuml
@startuml
A --> B
@enduml
```

次の段落です。
"""
        )

        self.assertIn(
            "@enduml\n"
            "```\n"
            "\n"
            "<!--:details-->\n"
            "\n"
            "次の段落です。\n",
            transformed,
        )

    def test_details_only_graph_at_end_of_file_is_closed(self):
        transformed = self._run_postprocess(
            """# Details

#### DOXYFW_DETAILS_ONLY 呼び出し先

```mermaid
flowchart TD
    n0 --> n1
```
"""
        )

        self.assertEqual(transformed.count("<!--details:-->"), 1)
        self.assertEqual(transformed.count("<!--:details-->"), 1)
        self.assertIn("    n0 --> n1\n```\n\n<!--:details-->\n", transformed)

    def test_consecutive_details_only_graphs_are_closed_separately(self):
        transformed = self._run_postprocess(
            """# Details

#### DOXYFW_DETAILS_ONLY 呼び出し元

```mermaid
flowchart TD
    n1 --> n0
```

Figure: f の呼び出し元

#### DOXYFW_DETAILS_ONLY 呼び出し先

```mermaid
flowchart TD
    n0 --> n2
```

Figure: f の呼び出し先
"""
        )

        self.assertEqual(transformed.count("<!--details:-->"), 2)
        self.assertEqual(transformed.count("<!--:details-->"), 2)
        self.assertIn(
            "Figure: f の呼び出し元\n\n<!--:details-->\n\n<!--details:-->\n\n**呼び出し先**\n",
            transformed,
        )
        self.assertIn("Figure: f の呼び出し先\n\n<!--:details-->\n", transformed)


if __name__ == "__main__":
    unittest.main()
