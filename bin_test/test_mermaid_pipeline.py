#!/usr/bin/env python3

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


FRAMEWORK_DIR = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash") or "bash"


class MermaidPipelineTest(unittest.TestCase):
    def test_markdown_and_comment_diagrams_survive_doxybook2(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.md").write_text(
                "# Mermaid sample\n\n```mermaid\nsequenceDiagram\n"
                "    A->>B: int * pointer, __flag__ & value\n```\n\n"
                "Figure: Markdown の図\n",
                encoding="utf-8",
            )
            (root / "sample.h").write_text(
                '/** @file\n * @brief Sample.\n *\n'
                ' * @mermaid "コメントの図"\n'
                ' * flowchart LR\n *     A --> B\n * @endmermaid\n */\n',
                encoding="utf-8",
            )
            doxyfile = root / "Doxyfile"
            doxyfile.write_text(
                f'OUTPUT_DIRECTORY = "{root}"\n'
                'INPUT = sample.md sample.h\n'
                f'STRIP_FROM_PATH = "{root}"\n'
                'USE_MDFILE_AS_MAINPAGE = sample.md\n'
                "QUIET = YES\nEXTRACT_ALL = YES\nGENERATE_HTML = NO\n"
                "GENERATE_LATEX = NO\nGENERATE_XML = YES\n",
                encoding="utf-8",
            )

            def run(command, **kwargs):
                result = subprocess.run(
                    command, capture_output=True,
                    text=True, encoding="utf-8", **kwargs,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotRegex(
                    result.stdout + result.stderr,
                    r"(?im)(\[warning\]|\bwarning:|警告:)",
                )

            run(["doxygen", str(doxyfile)], cwd=root)
            run([BASH, str(FRAMEWORK_DIR / "templates/preprocess.sh"), str(root / "xml")])
            docs = root / "docs"
            docs.mkdir()
            run([
                "doxybook2", "-i", str(root / "xml"), "-o", str(docs),
                "--config", str(FRAMEWORK_DIR / "doxybook2-config.json"),
                "--templates", str(FRAMEWORK_DIR / "templates"),
            ])
            converted = "\n".join(
                path.read_text(encoding="utf-8") for path in docs.rglob("*.md")
            )
            self.assertIn("```mermaid\nsequenceDiagram", converted)
            self.assertIn("Figure: Markdown の図", converted)
            self.assertIn("```mermaid\nflowchart LR", converted)
            self.assertIn("Figure: コメントの図", converted)
            env = os.environ.copy()
            env.update({
                "WORKSPACE_DIR": str(root), "DOXYGEN_RUNDIR": str(root),
                "DOXYFILE_PART_PATH": str(doxyfile), "CATEGORY": "",
                "CATEGORY_ID": "", "DOXYFW_TAGFILE": "",
            })
            run([BASH, str(FRAMEWORK_DIR / "templates/postprocess.sh"), str(docs)], env=env)
            markdown = "\n".join(
                path.read_text(encoding="utf-8") for path in docs.rglob("*.md")
            )
            self.assertIn("```mermaid\nsequenceDiagram", markdown)
            self.assertIn("A->>B: int * pointer, __flag__ & value", markdown)
            self.assertIn("Figure: Markdown の図", markdown)
            self.assertIn("```mermaid\nflowchart LR", markdown)
            self.assertIn("A --> B", markdown)
            self.assertIn("Figure: コメントの図", markdown)


if __name__ == "__main__":
    unittest.main()
