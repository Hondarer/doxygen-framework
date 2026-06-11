#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
copy-doxygen-images.py - Doxybook2 がコピーしなかった Doxygen 画像の補完

Doxygen XML の <image type="html" name="..."> を走査し、XML 出力ディレクトリに
コピー済みの画像を Doxybook2 出力ディレクトリ直下の images/ へ補完する。

使用方法:
    python3 copy-doxygen-images.py <xml_dir> <docs_dir>
"""

import shutil
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def iter_html_image_names(xml_dir):
    """Doxygen XML に含まれる HTML 用画像名を重複なしで列挙する。"""
    names = set()

    for xml_file in sorted(xml_dir.glob("*.xml")):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as exc:
            print(
                "Warning: failed to parse Doxygen XML: {}: {}".format(xml_file, exc),
                file=sys.stderr,
            )
            continue

        for image in root.iter("image"):
            if image.get("type") != "html":
                continue

            name = image.get("name")
            if not name:
                continue

            names.add(name)

    for name in sorted(names):
        yield name


def copy_missing_images(xml_dir, docs_dir):
    """XML 側に存在し、Doxybook2 出力に欠けている画像をコピーする。"""
    images_dir = docs_dir / "images"
    copied = 0
    missing = 0

    for name in iter_html_image_names(xml_dir):
        src = xml_dir / name
        if not src.is_file():
            missing += 1
            print(
                "Warning: Doxygen image is referenced but not found: {}".format(src),
                file=sys.stderr,
            )
            continue

        dest = images_dir / name
        if dest.exists():
            continue

        images_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
        print("  Copied Doxygen image: {}".format(name))

    print("[copy-doxygen-images] copied={} missing={}".format(copied, missing))

    return 0


def main(argv):
    if len(argv) != 3:
        print(
            "Usage: python3 copy-doxygen-images.py <xml_dir> <docs_dir>",
            file=sys.stderr,
        )
        return 2

    xml_dir = Path(argv[1])
    docs_dir = Path(argv[2])

    if not xml_dir.is_dir():
        print("ERROR: XML directory not found: {}".format(xml_dir), file=sys.stderr)
        return 1

    if not docs_dir.is_dir():
        print(
            "ERROR: Doxybook2 output directory not found: {}".format(docs_dir),
            file=sys.stderr,
        )
        return 1

    return copy_missing_images(xml_dir, docs_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
