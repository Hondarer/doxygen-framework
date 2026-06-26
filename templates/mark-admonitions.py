#!/usr/bin/env python3
"""Mark Doxygen admonition simplesects for Doxybook2 Markdown conversion."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ADMONITION_TYPES = {
    "note": "NOTE",
    "remark": "TIP",
    "important": "IMPORTANT",
    "warning": "WARNING",
    "attention": "CAUTION",
    "deprecated": "DEPRECATED",
}

MARKER_PREFIX = "!doxyfw-admonition"


def mark_file(xml_path: Path) -> bool:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    changed = False

    for simplesect in root.iter("simplesect"):
        kind = simplesect.attrib.get("kind", "")
        admonition_type = ADMONITION_TYPES.get(kind)
        if admonition_type is None:
            continue

        simplesect.set("kind", "par")
        title = simplesect.find("title")
        if title is None:
            title = ET.Element("title")
            simplesect.insert(0, title)
        title.text = f"{MARKER_PREFIX} {admonition_type}"
        changed = True

    if not changed:
        return False

    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: mark-admonitions.py <xml_directory>", file=sys.stderr)
        return 1

    xml_dir = Path(sys.argv[1])
    if not xml_dir.is_dir():
        print(f"Error: XML directory not found: {xml_dir}", file=sys.stderr)
        return 1

    for xml_path in xml_dir.rglob("*"):
        if xml_path.suffix.lower() == ".xml":
            mark_file(xml_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
