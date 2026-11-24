#!/usr/bin/env python3

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


DOXYFW_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = DOXYFW_ROOT / "bin" / "check-doxygen-code-span-backslash.py"


class CheckDoxygenCodeSpanBackslashTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def write_file(self, rel_path, text):
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def run_script(self, *targets) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *(str(t) for t in targets)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_detects_odd_trailing_backslashes_in_block_comment(self):
        header = self.write_file(
            "sample.h",
            "\n".join([
                "/**",
                " *  Windows では、`\\\\?\\` または `\\\\.\\` で始まるパスを扱います。",
                " *  最短の例は `a\\`、3 つ連続は `\\\\\\` です。",
                " */",
                "void sample(void);",
                "",
            ]),
        )

        result = self.run_script(header)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"{header}:2:", result.stdout)
        self.assertIn("`\\\\?\\`", result.stdout)
        self.assertIn("`\\\\.\\`", result.stdout)
        self.assertIn(f"{header}:3:", result.stdout)
        self.assertIn("`a\\`", result.stdout)
        self.assertIn("`\\\\\\`", result.stdout)
        self.assertIn("4 件", result.stdout)

    def test_detects_odd_trailing_backslashes_in_line_and_inline_comments(self):
        header = self.write_file(
            "inline.h",
            "\n".join([
                "/// `\\\\?\\` を含む行コメントです。",
                "void fn1(void);",
                "//! `a\\` を含む行コメントです。",
                "void fn2(void);",
                "int x; /**< 末尾コメントの `b\\` です。 */",
                "",
            ]),
        )

        result = self.run_script(header)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"{header}:1:", result.stdout)
        self.assertIn(f"{header}:3:", result.stdout)
        self.assertIn(f"{header}:5:", result.stdout)
        self.assertIn("3 件", result.stdout)

    def test_detects_multi_backtick_code_span_with_odd_backslash(self):
        header = self.write_file(
            "multi.h",
            "\n".join([
                "/**",
                " *  `` a\\ `` や `` `a\\ `` も検出します。",
                " */",
                "void multi(void);",
                "",
            ]),
        )

        result = self.run_script(header)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"{header}:2:", result.stdout)
        self.assertIn("2 件", result.stdout)

    def test_allows_even_trailing_backslashes_and_non_backslash_endings(self):
        header = self.write_file(
            "clean.h",
            "\n".join([
                "/**",
                " *  `\\\\` と `\\\\\\\\` は偶数個のため許可します。",
                " *  `/` と `\\\\` を区切りとします。",
                " *  `\\\\?\\C:\\...` と `\\\\?\\x` はバックスラッシュで終わりません。",
                " *  `\\\\.\\pipe\\name` も許可します。",
                " */",
                "void clean(void);",
                "",
            ]),
        )

        result = self.run_script(header)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK:", result.stdout)

    def test_ignores_non_doxygen_comments_strings_and_verbatim_blocks(self):
        source = self.write_file(
            "ignored.c",
            "\n".join([
                "/* 通常コメントの `\\\\?\\` は対象外です。 */",
                "// 行コメントの `a\\` も対象外です。",
                "const char *s = \"/** `\\\\?\\` */\";",
                "/**",
                " *  エスケープされた \\`a\\` はコード スパンではありません。",
                " *  @code{.unparsed}",
                " *  `\\\\?\\`",
                " *  @endcode",
                " *  @verbatim",
                " *  `a\\`",
                " *  @endverbatim",
                " */",
                "void ignored(void) {}",
                "",
            ]),
        )

        result = self.run_script(source)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK:", result.stdout)

    def test_directory_scan_skips_generated_doxybook2_and_obj_dirs(self):
        self.write_file("prod/include/ok.h", "/** `\\\\?\\C:\\...` */\nvoid ok(void);\n")
        self.write_file("docs/doxybook2_public/skip.h", "/** `\\\\?\\` */\nvoid skip1(void);\n")
        self.write_file("prod/obj/skip.c", "/** `\\\\?\\` */\nvoid skip2(void) {}\n")

        result = self.run_script(self.root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: 1 ファイルを検査", result.stdout)


if __name__ == "__main__":
    unittest.main()
