#!/usr/bin/env python3

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


DOXYFW_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = DOXYFW_ROOT / "bin" / "check-doxygen-indent.py"

DIAGRAM_HEADING = "図ブロックの字下げの不一致が検出されました"


def make_header(diagram_lines, body_prefix="     *  "):
    """コメント本文が 8 桁目の Doxygen コメントに図ブロックを挟んだヘッダーを返す"""
    lines = [
        "#ifndef SAMPLE_H",
        "#define SAMPLE_H",
        "",
        "    /**",
        f"{body_prefix}@brief          サンプル関数です。",
        "     *",
        f"{body_prefix}@par            呼び出しシーケンス",
        f"{body_prefix}処理の流れを示します。",
        "     *",
        *diagram_lines,
        "     *",
        f"{body_prefix}@par            スレッド セーフティ",
        f"{body_prefix}スレッド セーフです。",
        "     */",
        "    int sample(void);",
        "",
        "#endif",
        "",
    ]
    return "\n".join(lines)


def line_number_of(text, needle):
    """needle を含む最初の行の行番号 (1 始まり) を返す"""
    for index, line in enumerate(text.split("\n")):
        if needle in line:
            return index + 1
    raise AssertionError(f"{needle!r} が見つかりません")


class CheckDoxygenIndentDiagramTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.header = Path(self.temp_dir.name) / "sample.h"

    def write_header(self, text):
        self.header.write_text(text, encoding="utf-8", newline="\n")

    def run_script(self, *options) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *options, str(self.header)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def assert_no_diagram_issue(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(DIAGRAM_HEADING, result.stdout)
        self.assertIn("問題なし", result.stdout)

    def test_start_line_shallower_than_comment_body_is_reported(self):
        text = make_header([
            "    @startuml サンプルの図",
            "        caption サンプルの図",
            "        A -> B : 呼び出し",
            "    @enduml",
        ])
        self.write_header(text)

        result = self.run_script("--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(DIAGRAM_HEADING, result.stdout)
        start_line = line_number_of(text, "@startuml")
        end_line = line_number_of(text, "@enduml")
        self.assertIn(f"L{start_line}: 開始行 indent=4 (expected=8)", result.stdout)
        self.assertIn(f"L{end_line}: 終了行 indent=4 (expected=8)", result.stdout)
        self.assertIn("1 個の図ブロックで字下げの不一致を検出", result.stdout)
        # 既存の字下げレベルの検査は図ブロックの行を指摘しない
        self.assertNotIn("字下げレベルの不一致", result.stdout)

    def test_start_line_deeper_than_comment_body_is_reported(self):
        text = make_header([
            "            @mermaid \"サンプルの図\"",
            "            sequenceDiagram",
            "                A->>B: 呼び出し",
            "            @endmermaid",
        ])
        self.write_header(text)

        result = self.run_script("--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        start_line = line_number_of(text, "@mermaid")
        end_line = line_number_of(text, "@endmermaid")
        self.assertIn(f"L{start_line}: 開始行 indent=12 (expected=8)", result.stdout)
        self.assertIn(f"L{end_line}: 終了行 indent=12 (expected=8)", result.stdout)

    def test_end_line_only_mismatch_is_reported(self):
        text = make_header([
            "        @mermaid \"サンプルの図\"",
            "        sequenceDiagram",
            "            A->>B: 呼び出し",
            "    @endmermaid",
        ])
        self.write_header(text)

        result = self.run_script("--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        start_line = line_number_of(text, "@mermaid")
        end_line = line_number_of(text, "@endmermaid")
        self.assertIn(f"L{end_line}: 終了行 indent=4 (expected=8)", result.stdout)
        self.assertNotIn(f"L{start_line}: 開始行", result.stdout)

    def test_diagram_body_shallower_than_start_line_is_reported(self):
        text = make_header([
            "        @startuml サンプルの図",
            "        caption サンプルの図",
            "    A -> B : 呼び出し",
            "        @enduml",
        ])
        self.write_header(text)

        result = self.run_script("--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        body_line = line_number_of(text, "A -> B")
        self.assertIn(f"L{body_line}: 図の本文 indent=4 (expected>=8)", result.stdout)
        self.assertNotIn("開始行 indent", result.stdout)
        self.assertNotIn("終了行 indent", result.stdout)

    def test_aligned_startuml_block_is_not_reported(self):
        self.write_header(make_header([
            "        @startuml サンプルの図",
            "        caption サンプルの図",
            "",
            "        A -> B : 呼び出し",
            "        alt 成功",
            "            B --> A : 結果",
            "        end",
            "        @enduml",
        ]))

        self.assert_no_diagram_issue(self.run_script("--check"))

    def test_aligned_mermaid_block_is_not_reported(self):
        self.write_header(make_header([
            "        @mermaid \"サンプルの図\"",
            "        sequenceDiagram",
            "",
            "            A->>B: 呼び出し",
            "        @endmermaid",
        ]))

        self.assert_no_diagram_issue(self.run_script("--check"))

    def test_backslash_commands_are_checked(self):
        text = make_header([
            "    \\mermaid \"サンプルの図\"",
            "        sequenceDiagram",
            "    \\endmermaid",
            "     *",
            "    \\startuml サンプルの図",
            "        A -> B : 呼び出し",
            "    \\enduml",
        ])
        self.write_header(text)

        result = self.run_script("--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("\\mermaid (コメント本文の桁: 8)", result.stdout)
        self.assertIn("\\startuml (コメント本文の桁: 8)", result.stdout)
        self.assertIn("2 個の図ブロックで字下げの不一致を検出", result.stdout)

    def test_star_prefixed_diagram_block_is_not_reported(self):
        self.write_header(make_header([
            "     *  @mermaid \"サンプルの図\"",
            "     *  sequenceDiagram",
            "     *      A->>B: 呼び出し",
            "     *  @endmermaid",
            "     *",
            "     *  @startuml サンプルの図",
            "     *  A -> B : 呼び出し",
            "     *  @enduml",
        ]))

        self.assert_no_diagram_issue(self.run_script("--check"))

    def test_comment_body_column_follows_nearest_star_line(self):
        # 図ブロックの直前にある本文の行 (7 桁目) を基準にする
        text = "\n".join([
            "    /**",
            "     *  @brief          サンプル関数です。",
            "     *",
            "     * 処理の流れを示します。",
            "     *",
            "        @startuml サンプルの図",
            "        A -> B : 呼び出し",
            "        @enduml",
            "     */",
            "    int sample(void);",
            "",
        ])
        self.write_header(text)

        result = self.run_script("--check")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("@startuml (コメント本文の桁: 7)", result.stdout)
        self.assertIn("開始行 indent=8 (expected=7)", result.stdout)
        self.assertIn("終了行 indent=8 (expected=7)", result.stdout)

    def test_fix_mode_does_not_rewrite_diagram_block(self):
        text = make_header([
            "    @startuml サンプルの図",
            "        A -> B : 呼び出し",
            "    @enduml",
        ]).replace("     *  @brief", "  *  @brief")
        self.write_header(text)

        result = self.run_script("--fix")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 ファイルを修正しました (1 行)", result.stdout)
        self.assertIn(DIAGRAM_HEADING, result.stdout)
        start_line = line_number_of(text, "@startuml")
        self.assertIn(f"L{start_line}: 開始行 indent=4 (expected=8)", result.stdout)

        fixed = self.header.read_text(encoding="utf-8")
        # * を持つ行の字下げは修正し、図ブロックは書き換えない
        self.assertEqual(fixed, text.replace("  *  @brief", "     *  @brief"))

    def test_dry_run_mode_reports_diagram_block_without_rewriting(self):
        text = make_header([
            "            @startuml サンプルの図",
            "            A -> B : 呼び出し",
            "            @enduml",
        ])
        self.write_header(text)

        result = self.run_script("--dry-run")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("修正対象のファイルはありません", result.stdout)
        self.assertIn(DIAGRAM_HEADING, result.stdout)
        self.assertIn("開始行 indent=12 (expected=8)", result.stdout)
        self.assertEqual(self.header.read_text(encoding="utf-8"), text)


if __name__ == "__main__":
    unittest.main()
