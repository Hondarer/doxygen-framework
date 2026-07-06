#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
normalize-function-references.py - Doxygen XML の関数参照を正規化する

同名 static 関数の誤参照により、references / referencedby の refid が
別ファイル関数を指すケースを XML 段階で補正する。
"""

from __future__ import annotations

import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class FunctionMeta:
    func_id: str
    name: str
    file_path: str
    compound_id: str
    is_static: bool


MEMBERDEF_RE = re.compile(
    r"<memberdef\b[^>]*\bkind=\"function\"[^>]*>.*?</memberdef>",
    re.DOTALL,
)
ID_RE = re.compile(r"<memberdef\b[^>]*\bid=\"([^\"]*)\"")
LOCATION_RE = re.compile(r"<location\b([^>]*?)/?>")
ATTR_RE = re.compile(r"(\w+)\s*=\s*\"([^\"]*)\"")
REFERENCES_RE = re.compile(r"<references\s+([^>]*\brefid=\"[^\"]+\"[^>]*)>([^<]*)</references>")
REFERENCEDBY_RE = re.compile(r"<referencedby\s+([^>]*\brefid=\"[^\"]+\"[^>]*)>([^<]*)</referencedby>")


def normalize_path(path_text: str) -> str:
    return path_text.replace("\\", "/")


def xml_files(xml_dir: str) -> List[str]:
    result = []
    for path in sorted(glob.glob(os.path.join(xml_dir, "*.xml"))):
        base = os.path.basename(path)
        if base.startswith("index") or base == "combine.xslt":
            continue
        result.append(path)
    return result


def parse_attrs(attr_text: str) -> Dict[str, str]:
    return dict(ATTR_RE.findall(attr_text))


def update_attr(attr_text: str, key: str, value: str) -> str:
    pattern = re.compile(rf'\b{re.escape(key)}="[^"]*"')
    if pattern.search(attr_text):
        return pattern.sub(f'{key}="{value}"', attr_text, count=1)
    return (attr_text.strip() + f' {key}="{value}"').strip()


def collect_functions(xml_dir: str) -> Tuple[Dict[str, FunctionMeta], Dict[Tuple[str, str], List[str]]]:
    by_id: Dict[str, FunctionMeta] = {}
    by_file_and_name: Dict[Tuple[str, str], List[str]] = {}

    for path in xml_files(xml_dir):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        compound = root.find("compounddef")
        if compound is None:
            continue
        compound_id = compound.get("id", "")
        for member in compound.findall(".//memberdef[@kind='function']"):
            func_id = member.get("id", "")
            if func_id == "":
                continue
            location = member.find("location")
            if location is None:
                continue
            file_path = normalize_path(location.get("bodyfile", "") or location.get("file", ""))
            if file_path == "":
                continue
            name = (member.findtext("name") or "").strip()
            meta = FunctionMeta(
                func_id=func_id,
                name=name,
                file_path=file_path,
                compound_id=compound_id,
                is_static=(member.get("static") == "yes"),
            )
            by_id[func_id] = meta
            by_file_and_name.setdefault((meta.file_path, meta.name), []).append(func_id)

    return by_id, by_file_and_name


def remap_target_id(
    current: FunctionMeta,
    target: FunctionMeta,
    by_file_and_name: Dict[Tuple[str, str], List[str]],
) -> Optional[str]:
    candidates = [
        func_id
        for func_id in by_file_and_name.get((current.file_path, target.name), [])
        if func_id != target.func_id
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def process_memberdef_block(
    block: str,
    by_id: Dict[str, FunctionMeta],
    by_file_and_name: Dict[Tuple[str, str], List[str]],
) -> Tuple[str, int]:
    id_match = ID_RE.search(block)
    if id_match is None:
        return block, 0
    current_id = id_match.group(1)
    current = by_id.get(current_id)
    if current is None:
        return block, 0

    changed = 0

    def replace_reference(match: re.Match[str]) -> str:
        nonlocal changed
        attr_text = match.group(1)
        label_text = match.group(2)
        attrs = parse_attrs(attr_text)
        refid = attrs.get("refid", "")
        target = by_id.get(refid)
        if target is None:
            return match.group(0)
        if not (target.is_static and target.file_path != current.file_path):
            return match.group(0)
        replacement_id = remap_target_id(current, target, by_file_and_name)
        if replacement_id is None:
            print(
                "Warning: static-cross-file-reference unresolved: {} ({}) -> {} ({})".format(
                    current.name,
                    current.file_path,
                    target.name,
                    target.file_path,
                ),
                file=sys.stderr,
            )
            return match.group(0)
        replacement = by_id.get(replacement_id)
        if replacement is None:
            return match.group(0)
        new_attrs = update_attr(attr_text, "refid", replacement.func_id)
        if replacement.compound_id != "":
            new_attrs = update_attr(new_attrs, "compoundref", replacement.compound_id)
        changed += 1
        print(
            "Info: static-cross-file-reference remapped: {} ({}) -> {} ({}) as {} ({})".format(
                current.name,
                current.file_path,
                target.name,
                target.file_path,
                replacement.name,
                replacement.file_path,
            ),
            file=sys.stderr,
        )
        return f"<references {new_attrs}>{label_text}</references>"

    def replace_referencedby(match: re.Match[str]) -> str:
        nonlocal changed
        attr_text = match.group(1)
        label_text = match.group(2)
        attrs = parse_attrs(attr_text)
        refid = attrs.get("refid", "")
        target = by_id.get(refid)
        if target is None:
            return match.group(0)
        if not (current.is_static and target.file_path != current.file_path):
            return match.group(0)
        replacement_id = remap_target_id(current, target, by_file_and_name)
        if replacement_id is None:
            print(
                "Warning: static-cross-file-referencedby unresolved: {} ({}) <- {} ({})".format(
                    current.name,
                    current.file_path,
                    target.name,
                    target.file_path,
                ),
                file=sys.stderr,
            )
            return match.group(0)
        replacement = by_id.get(replacement_id)
        if replacement is None:
            return match.group(0)
        new_attrs = update_attr(attr_text, "refid", replacement.func_id)
        if replacement.compound_id != "":
            new_attrs = update_attr(new_attrs, "compoundref", replacement.compound_id)
        changed += 1
        print(
            "Info: static-cross-file-referencedby remapped: {} ({}) <- {} ({}) as {} ({})".format(
                current.name,
                current.file_path,
                target.name,
                target.file_path,
                replacement.name,
                replacement.file_path,
            ),
            file=sys.stderr,
        )
        return f"<referencedby {new_attrs}>{label_text}</referencedby>"

    new_block = REFERENCES_RE.sub(replace_reference, block)
    new_block = REFERENCEDBY_RE.sub(replace_referencedby, new_block)
    return new_block, changed


def normalize_xml_dir(xml_dir: str) -> Tuple[int, int]:
    by_id, by_file_and_name = collect_functions(xml_dir)
    updated_files = 0
    updated_refs = 0

    for path in xml_files(xml_dir):
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()

        replacements: List[Tuple[str, str]] = []
        for match in MEMBERDEF_RE.finditer(original):
            block = match.group(0)
            new_block, changed = process_memberdef_block(block, by_id, by_file_and_name)
            if changed > 0 and new_block != block:
                replacements.append((block, new_block))
                updated_refs += changed

        if not replacements:
            continue

        text = original
        for old_block, new_block in replacements:
            text = text.replace(old_block, new_block, 1)

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        updated_files += 1

    return updated_files, updated_refs


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("Usage: normalize-function-references.py <xml_dir>", file=sys.stderr)
        return 2
    xml_dir = argv[1]
    if not os.path.isdir(xml_dir):
        print(f"Error: xml_dir does not exist: {xml_dir}", file=sys.stderr)
        return 1
    files, refs = normalize_xml_dir(xml_dir)
    print(f"[normalize-function-references] Updated files={files}, refs={refs}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
