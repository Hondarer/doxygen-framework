#!/usr/bin/env python3
"""Convert Doxybook2 admonition marker sections to GitHub alert Markdown."""

from __future__ import annotations

import re
import sys
from pathlib import Path


MARKER_RE = re.compile(r"^(#{1,6})\s+!doxyfw-admonition\s+(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+")
DETAILS_OPEN_RE = re.compile(r"^<!--details:-->\s*$")
ALERT_RE = re.compile(r"^> \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$")


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


def relocate_admonitions(text: str) -> str:
    """Move admonition blockquotes to before the first #### heading in their parent section.

    Within each parent section (H3 or lower), admonition blockquotes that appear
    after #### headings are relocated to just before the first #### heading.
    This places them immediately after brief + details content.
    """
    lines = text.splitlines(keepends=True)
    sections = _split_into_parent_sections(lines)
    result: list[str] = []
    for section in sections:
        result.extend(_relocate_in_section(section))
    return "".join(result)


def _split_into_parent_sections(lines: list[str]) -> list[list[str]]:
    """Split lines into sections by H1-H3 headings."""
    sections: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        match = HEADING_RE.match(line.rstrip("\n"))
        if match is not None and len(match.group(1)) <= 3:
            if current:
                sections.append(current)
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append(current)
    return sections


def _relocate_in_section(section: list[str]) -> list[str]:
    """Within a section, move admonition blockquotes to before the first #### heading."""
    first_h4_index = None
    admonition_ranges: list[tuple[int, int]] = []

    index = 0
    while index < len(section):
        line = section[index]

        heading_match = HEADING_RE.match(line.rstrip("\n"))
        if heading_match is not None and len(heading_match.group(1)) >= 4:
            if first_h4_index is None:
                first_h4_index = index

        if ALERT_RE.match(line.rstrip("\n")):
            start = index
            index += 1
            while index < len(section):
                stripped = section[index].rstrip("\n")
                if stripped.startswith(">"):
                    index += 1
                else:
                    break
            # Include trailing blank line if present
            if index < len(section) and section[index].strip() == "":
                index += 1
            admonition_ranges.append((start, index))
        else:
            index += 1

    if not admonition_ranges or first_h4_index is None:
        return section

    # Only relocate admonitions that appear after the first H4 heading
    to_relocate = [(s, e) for s, e in admonition_ranges if s > first_h4_index]
    if not to_relocate:
        return section

    # Build result: insert relocated admonitions before first_h4_index
    relocated_lines: list[str] = []
    for start, end in to_relocate:
        relocated_lines.extend(section[start:end])

    # Ensure blank line before admonition block
    if relocated_lines and not relocated_lines[0].startswith("\n"):
        if first_h4_index > 0 and section[first_h4_index - 1].strip() != "":
            relocated_lines.insert(0, "\n")

    # Build output excluding relocated ranges
    exclude = set()
    for start, end in to_relocate:
        for i in range(start, end):
            exclude.add(i)

    result: list[str] = []
    for i, line in enumerate(section):
        if i == first_h4_index:
            result.extend(relocated_lines)
        if i not in exclude:
            result.append(line)

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
            if DETAILS_OPEN_RE.match(lines[index].rstrip("\n")):
                break
            content.append(lines[index])
            index += 1

        output.extend(blockquote_lines(content, admonition_type))

    return relocate_admonitions("".join(output))


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
