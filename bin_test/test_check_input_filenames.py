"""check-input-filenames.py が Doxygen の入力範囲にある非 ASCII のパスを検出することを検証する。"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "bin_internal" / "check-input-filenames.py"


class CheckInputFilenamesTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(prefix="doxyfw-input-names-")
        self.root = Path(self._temp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (self.root / "README.md").write_text("# Sample\n", encoding="utf-8")

    def tearDown(self):
        self._temp.cleanup()

    def write_doxyfile(self, text):
        path = self.root / "Doxyfile"
        path.write_text(text, encoding="utf-8")
        return path

    def run_checker(self, doxyfile, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(doxyfile), str(self.root)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", timeout=30, env=env,
        )

    def base_config(self, extra=""):
        return (
            "# INPUT = ignored.md\n"
            "INPUT = ./README.md \\\n"
            "        ./src\n"
            "FILE_PATTERNS = *.c \\\n"
            "                *.md\n"
            "RECURSIVE = YES\n"
            "EXCLUDE_PATTERNS = */obj/*\n"
            + extra
        )

    def test_ascii_only_inputs_pass(self):
        result = self.run_checker(self.write_doxyfile(self.base_config()))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_detects_non_ascii_file_name(self):
        # CP932 として不正なバイト列になる名前と、解釈できてしまう名前の双方を検出する
        (self.root / "src" / "機能仕様表.md").write_text("# 表\n", encoding="utf-8")
        (self.root / "src" / "表.md").write_text("# 表\n", encoding="utf-8")
        result = self.run_checker(self.write_doxyfile(self.base_config()))
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: Doxygen input paths must contain only ASCII characters.", result.stderr)
        self.assertIn("/src/機能仕様表.md", result.stderr)
        self.assertIn("/src/表.md", result.stderr)

    def test_detects_non_ascii_directory_name(self):
        (self.root / "src" / "資料").mkdir()
        (self.root / "src" / "資料" / "page.md").write_text("# Page\n", encoding="utf-8")
        result = self.run_checker(self.write_doxyfile(self.base_config()))
        self.assertEqual(result.returncode, 1)
        self.assertIn("/src/資料/page.md", result.stderr)

    def test_ignores_files_outside_doxygen_input(self):
        # FILE_PATTERNS 外、EXCLUDE_PATTERNS、EXCLUDE、INPUT 外は Doxygen が読まないため対象外とする
        (self.root / "src" / "画像.png").write_bytes(b"\x89PNG")
        (self.root / "src" / "obj").mkdir()
        (self.root / "src" / "obj" / "生成.c").write_text("\n", encoding="utf-8")
        (self.root / "src" / "除外").mkdir()
        (self.root / "src" / "除外" / "page.md").write_text("\n", encoding="utf-8")
        (self.root / "外部.md").write_text("\n", encoding="utf-8")
        result = self.run_checker(self.write_doxyfile(self.base_config('EXCLUDE = "./src/除外"\n')))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_recursive_skips_subdirectories(self):
        (self.root / "src" / "sub").mkdir()
        (self.root / "src" / "sub" / "仕様.md").write_text("\n", encoding="utf-8")
        result = self.run_checker(self.write_doxyfile(self.base_config("RECURSIVE = NO\n")))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_later_assignment_and_append_are_applied(self):
        # 基本 Doxyfile の後に Doxyfile.part を結合するため、後の代入と += を反映する
        (self.root / "include").mkdir()
        (self.root / "include" / "ヘッダー.h").write_text("\n", encoding="utf-8")
        (self.root / "src" / "仕様.md").write_text("\n", encoding="utf-8")
        config = self.base_config("INPUT = ./README.md\nINPUT += $(DOXYFW_TEST_DIR)\nFILE_PATTERNS += *.h\n")
        env = dict(os.environ, DOXYFW_TEST_DIR="include")
        result = self.run_checker(self.write_doxyfile(config), env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("/include/ヘッダー.h", result.stderr)
        self.assertNotIn("仕様.md", result.stderr)


if __name__ == "__main__":
    unittest.main()
