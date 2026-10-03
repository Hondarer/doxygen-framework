"""空白を含むワークスペースで Doxygen と Markdown の実生成を検証する。"""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import shutil

# Windows の subprocess は System32 を PATH より先に探すため、名前だけで起動すると
# WSL の bash.exe を選ぶことがある。PATH 上の bash (Git Bash など) を明示して使う。
# see: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw
BASH = shutil.which("bash") or "bash"


DOXYFW = Path(__file__).resolve().parents[1]


class PathSpacesTest(unittest.TestCase):
    def test_warning_extraction_preserves_absolute_paths(self):
        with tempfile.TemporaryDirectory(prefix="doxyfw warnings space ") as temp:
            root = Path(temp)
            log = root / "input log.txt"
            warn = root / "output warnings.txt"
            expected = [
                "D:/workspace space/prod/sample.h:12: warning: mixed path",
                "D:\\workspace space\\prod\\sample.h:13: warning: native path",
                "/workspace space/prod/sample.h:14: warning: posix path",
                "D:/workspace space/prod/sample.h: warning: no line number",
                "relative.h:15: warning: relative path",
            ]
            with open(log, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("\x1b[33m" + expected[0] + "\x1b[0m\r\n"
                    + "\n".join(expected[1:3]) + "\n"
                    + "prefix " + expected[3] + "\n" + expected[4] + "\n"
                    + "Warning: doxygen command not found. Skipping generation.\n"
                    + "ordinary output\n")
            result = subprocess.run(
                [BASH, str(DOXYFW / "bin_internal/extract_doxy_warnings.sh"), str(log), str(warn)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(warn.read_text(encoding="utf-8").splitlines(), expected)

    def test_generate_in_workspace_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="doxyfw space ") as temp:
            root = Path(temp)
            prod = root / "prod"
            prod.mkdir()
            (prod / "src").mkdir()
            (prod / "include").mkdir()
            (prod / "README.md").write_text("# Sample\n", encoding="utf-8")
            (root / ".workspaceRoot").touch()
            (prod / "sample.h").write_text(
                "/** @brief Return a sample value. */\nint sample(void);\n",
                encoding="utf-8",
            )
            (root / "Doxyfile.part").write_text(
                'INPUT = "' + (prod / "sample.h").as_posix() + '" "'
                + (prod / "README.md").as_posix() + '"\n'
                "EXTRACT_ALL = YES\nHAVE_DOT = NO\n",
                encoding="utf-8",
            )
            tmpdir = root / "system tmp space"
            tmpdir.mkdir()
            env = dict(os.environ, DOXYFW_HOME=DOXYFW.as_posix(), TMPDIR=tmpdir.as_posix())
            result = subprocess.run(
                ["make", "--no-print-directory", "-C", str(DOXYFW),
                 "WORKSPACE_DIR=" + root.as_posix(),
                 "DOXYFW_TMP_ROOT=" + (root / "tmp space").as_posix(),
                 "DOXYFW_LOCK_ROOT=" + (root / "lock space").as_posix()],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((root / "pages/doxygen/index.html").is_file(), result.stdout)
            markdown = list((root / "docs/doxybook2").rglob("*.md"))
            self.assertTrue(markdown, result.stdout)
            self.assertTrue(
                any("sample" in path.read_text(encoding="utf-8") for path in markdown),
                result.stdout,
            )
            self.assertTrue(
                any("# Sample" in path.read_text(encoding="utf-8") for path in markdown),
                result.stdout,
            )
            self.assertNotIn("Warning: INPUT path not found", result.stdout)
            self.assertEqual(list(tmpdir.iterdir()), [], result.stdout)
            warn = root / "prod/doxy.warn"
            if warn.exists():
                self.assertEqual(warn.read_text(encoding="utf-8"), "", result.stdout)


if __name__ == "__main__":
    unittest.main()
