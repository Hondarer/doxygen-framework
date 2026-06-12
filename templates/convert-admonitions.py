#!/usr/bin/env python3
"""Convert Doxybook2 admonition marker sections to GitHub alert Markdown."""

from __future__ import annotations

import re
import sys
from pathlib import Path


MARKER_RE = re.compile(r"^(#{1,6})\s+!doxyfw-admonition\s+(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+")
DETAIL_TITLE_MARKER_RE = re.compile(r"^!doxyfw-detail-title-bold!.+\s*$")
STRUCTURE_TITLE_MARKER_RE = re.compile(r"^!doxyfw-structure-title!#{1,6}\s+.+\s*$")
DETAILS_OPEN_RE = re.compile(r"^<!--details:-->\s*$")


def blockquote_lines(lines: list[str], admonition_type: str) -> list[str]:
    result = [f"> [!{admonition_type}]\n"]
    content = list(lines)

    while content and content[0].strip() == "":
        content.pop(0)
    while content and content[-1].strip() == "":
        content.pop()

    for line in content:
        if line.strip() == "":
            result.append(">\n")
        else:
            result.append(f"> {line}")
    result.append("\n")
    return result


def convert_text(text: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0

    while index < len(lines):
        match = MARKER_RE.match(lines[index].rstrip("\n"))
        if match is None:
            output.append(lines[index])
            index += 1
            continue

        marker_level = len(match.group(1))
        admonition_type = match.group(2)
        index += 1
        content: list[str] = []

        while index < len(lines):
            heading_match = HEADING_RE.match(lines[index].rstrip("\n"))
            if heading_match is not None and len(heading_match.group(1)) <= marker_level:
                break
            if DETAIL_TITLE_MARKER_RE.match(lines[index].rstrip("\n")):
                break
            if STRUCTURE_TITLE_MARKER_RE.match(lines[index].rstrip("\n")):
                break
            if DETAILS_OPEN_RE.match(lines[index].rstrip("\n")):
                break
            content.append(lines[index])
            index += 1

        output.extend(blockquote_lines(content, admonition_type))

    return "".join(output)


def convert_file(markdown_path: Path) -> bool:
    original = markdown_path.read_text(encoding="utf-8")
    converted = convert_text(original)
    if converted == original:
        return False
    markdown_path.write_text(converted, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: convert-admonitions.py <markdown_directory>", file=sys.stderr)
        return 1

    markdown_dir = Path(sys.argv[1])
    if not markdown_dir.is_dir():
        print(f"Error: Markdown directory not found: {markdown_dir}", file=sys.stderr)
        return 1

    for markdown_path in markdown_dir.rglob("*.md"):
        convert_file(markdown_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
