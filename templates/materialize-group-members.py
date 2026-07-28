#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
グループへ移動したメンバーを、定義元のソース ファイル XML へ具象化する。

Doxygen は @ingroup を指定したメンバーについて、ファイル コンパウンド側へ
完全な memberdef ではなく group__*.xml を指す member を出力する場合がある。
Doxybook2 はこの参照をファイル ページの通常メンバーとして描画しないため、
グループ側の memberdef をソース ファイル側へ複製し、index.xml の参照も
複製後の ID へ更新する。
"""

import hashlib
import posixpath
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".cs"}
SKIP_XML_NAMES = {"compound.xsd", "combine.xslt", "Doxyfile.xml", "index.xml"}
MEMBERDEF_RE = re.compile(r"<memberdef\b[^>]*>.*?</memberdef>", re.DOTALL)
ID_ATTR_RE = re.compile(r'(?<![A-Za-z0-9_:.-])id="([^"]+)"')
LOCATION_RE = re.compile(r"<location\b[^>]*/>")


class MaterializeError(RuntimeError):
    """入力 XML の不整合を表す。"""


def normalize_path(value):
    """Doxygen XML 内のパスを比較用に正規化する。"""
    return posixpath.normpath(value.replace("\\", "/"))


def replace_attribute(tag, name, value):
    """XML 開始タグの属性を置換し、存在しない場合は末尾へ追加する。"""
    pattern = re.compile(r'(\s' + re.escape(name) + r')="[^"]*"')
    escaped = (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    if pattern.search(tag):
        return pattern.sub(r'\1="' + escaped + '"', tag, count=1)
    return tag[:-2] + ' {}="{}"/>'.format(name, escaped)


def remove_attribute(tag, name):
    """XML 開始タグから指定属性を除去する。"""
    return re.sub(r'\s+' + re.escape(name) + r'="[^"]*"', "", tag, count=1)


def clone_id(file_compound_id, group_member_id):
    """ファイル コンパウンド内で使用する決定的な memberdef ID を返す。"""
    match = re.search(r"([0-9a-fA-F]{32})$", group_member_id)
    if match:
        digest = match.group(1).lower()
    else:
        seed = "{}\0{}".format(group_member_id, file_compound_id)
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    return "{}_1a{}".format(file_compound_id, digest)


def extract_memberdef_blocks(text, xml_path):
    """memberdef ID と未変更の XML 断片を抽出する。"""
    result = {}
    for block in MEMBERDEF_RE.findall(text):
        opening_end = block.find(">")
        match = ID_ATTR_RE.search(block[: opening_end + 1])
        if match is None:
            raise MaterializeError(
                "{}: memberdef に id 属性がありません".format(xml_path)
            )
        member_id = match.group(1)
        if member_id in result:
            raise MaterializeError(
                "{}: memberdef ID が重複しています: {}".format(xml_path, member_id)
            )
        result[member_id] = block
    return result


def rewrite_clone(block, new_id, location):
    """memberdef の ID と、必要な場合は定義位置をソース側へ変更する。"""
    opening_end = block.find(">")
    opening = block[: opening_end + 1]
    new_opening = ID_ATTR_RE.sub('id="{}"'.format(new_id), opening, count=1)
    result = new_opening + block[opening_end + 1 :]

    decl_file = location.get("file", "")
    body_file = location.get("bodyfile", "")
    if not body_file or normalize_path(decl_file) == normalize_path(body_file):
        return result

    location_match = LOCATION_RE.search(result)
    if location_match is None:
        raise MaterializeError(
            "{}: location 要素の XML 断片を特定できません".format(
                location.get("member_id", new_id)
            )
        )

    location_tag = location_match.group(0)
    location_tag = replace_attribute(location_tag, "file", body_file)
    body_start = location.get("bodystart", "")
    if body_start:
        location_tag = replace_attribute(location_tag, "line", body_start)
    location_tag = remove_attribute(location_tag, "column")
    return (
        result[: location_match.start()]
        + location_tag
        + result[location_match.end() :]
    )


def member_ref_pattern(refid):
    """指定 refid の member 要素全体に一致する正規表現を返す。"""
    return re.compile(
        r'<member\b(?=[^>]*\brefid="'
        + re.escape(refid)
        + r'")[^>]*>.*?</member>',
        re.DOTALL,
    )


def index_compound_pattern(compound_id):
    """index.xml 内の指定 compound 要素全体に一致する正規表現を返す。"""
    return re.compile(
        r'<compound\b(?=[^>]*\brefid="'
        + re.escape(compound_id)
        + r'")[^>]*>.*?</compound>',
        re.DOTALL,
    )


def collect_xml(xml_dir):
    """対象 XML を読み、ElementTree と未変更テキストを返す。"""
    parsed = {}
    texts = {}
    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name in SKIP_XML_NAMES:
            continue
        try:
            parsed[xml_path] = ET.parse(xml_path).getroot()
        except ET.ParseError as exc:
            raise MaterializeError("{}: XML 解析に失敗しました: {}".format(xml_path, exc))
        texts[xml_path] = xml_path.read_text(encoding="utf-8")
    return parsed, texts


def materialize(xml_dir):
    """グループ メンバーをソース ファイル コンパウンドへ具象化する。"""
    xml_dir = Path(xml_dir)
    index_path = xml_dir / "index.xml"
    if not index_path.is_file():
        raise MaterializeError("index.xml が見つかりません: {}".format(index_path))

    try:
        index_root = ET.parse(index_path).getroot()
    except ET.ParseError as exc:
        raise MaterializeError(
            "{}: XML 解析に失敗しました: {}".format(index_path, exc)
        )
    index_text = index_path.read_text(encoding="utf-8")
    parsed, texts = collect_xml(xml_dir)

    group_members = {}
    all_member_ids = {}
    file_compounds = []

    for xml_path, root in parsed.items():
        raw_blocks = extract_memberdef_blocks(texts[xml_path], xml_path)
        for compounddef in root.findall("compounddef"):
            compound_kind = compounddef.get("kind", "")
            if compound_kind == "group":
                for memberdef in compounddef.findall("./sectiondef/memberdef"):
                    member_id = memberdef.get("id", "")
                    if not member_id or member_id not in raw_blocks:
                        raise MaterializeError(
                            "{}: グループ memberdef の XML 断片がありません: {}".format(
                                xml_path, member_id
                            )
                        )
                    if member_id in group_members:
                        raise MaterializeError(
                            "グループ memberdef ID が複数ファイルに存在します: {}".format(
                                member_id
                            )
                        )
                    location = memberdef.find("location")
                    if location is None:
                        raise MaterializeError(
                            "{}: location がないグループ memberdef です: {}".format(
                                xml_path, member_id
                            )
                        )
                    location_data = dict(location.attrib)
                    location_data["member_id"] = member_id
                    group_members[member_id] = {
                        "block": raw_blocks[member_id],
                        "location": location_data,
                    }

            for memberdef in compounddef.findall("./sectiondef/memberdef"):
                member_id = memberdef.get("id", "")
                if member_id:
                    all_member_ids.setdefault(member_id, []).append(xml_path)

            if compound_kind != "file":
                continue
            location = compounddef.find("location")
            file_name = ""
            if location is not None:
                file_name = location.get("file", "")
            if Path(file_name).suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            file_compounds.append(
                {
                    "xml_path": xml_path,
                    "compound": compounddef,
                    "compound_id": compounddef.get("id", ""),
                    "file_name": file_name,
                    "raw_blocks": raw_blocks,
                }
            )

    index_compounds = {}
    for compound in index_root.findall("compound"):
        refid = compound.get("refid", "")
        if refid in index_compounds:
            raise MaterializeError(
                "index.xml の compound refid が重複しています: {}".format(refid)
            )
        index_compounds[refid] = compound

    operations = []
    generated_ids = {}
    skipped = 0
    for file_info in file_compounds:
        compound_id = file_info["compound_id"]
        if not compound_id:
            raise MaterializeError(
                "{}: ファイル compounddef に id がありません".format(
                    file_info["xml_path"]
                )
            )
        index_compound = index_compounds.get(compound_id)
        if index_compound is None:
            raise MaterializeError(
                "index.xml にファイル compound がありません: {}".format(compound_id)
            )

        refs = file_info["compound"].findall("./sectiondef/member")
        for member in refs:
            refid = member.get("refid", "")
            if not refid.startswith("group__"):
                continue
            if refid not in group_members:
                raise MaterializeError(
                    "{}: 参照先のグループ memberdef がありません: {}".format(
                        file_info["xml_path"], refid
                    )
                )

            location = group_members[refid]["location"]
            expected_file = location.get("bodyfile", "")
            if not expected_file:
                expected_file = location.get("file", "")
            if normalize_path(expected_file) != normalize_path(file_info["file_name"]):
                raise MaterializeError(
                    "{}: {} の定義先 {} とファイル compound {} が一致しません".format(
                        file_info["xml_path"],
                        refid,
                        expected_file,
                        file_info["file_name"],
                    )
                )

            new_id = clone_id(compound_id, refid)
            if new_id in all_member_ids:
                raise MaterializeError(
                    "生成先 memberdef ID が既存 ID と衝突します: {} ({})".format(
                        new_id,
                        ", ".join(str(path) for path in all_member_ids[new_id]),
                    )
                )
            if new_id in generated_ids:
                raise MaterializeError(
                    "複数のグループ メンバーが同じ生成先 ID になります: {} "
                    "({}, {})".format(new_id, generated_ids[new_id], refid)
                )
            generated_ids[new_id] = refid

            matching_index_members = [
                item
                for item in index_compound.findall("member")
                if item.get("refid", "") == refid
            ]
            if len(matching_index_members) != 1:
                raise MaterializeError(
                    "index.xml の {} に {} の参照が 1 件ではありません: {} 件".format(
                        compound_id, refid, len(matching_index_members)
                    )
                )

            operations.append(
                {
                    "file_info": file_info,
                    "old_id": refid,
                    "new_id": new_id,
                    "clone": rewrite_clone(
                        group_members[refid]["block"], new_id, location
                    ),
                }
            )

        # 再実行時は、グループ ID から導出できる具象化済み ID を数える。
        for group_id, group_info in group_members.items():
            location = group_info["location"]
            expected_file = location.get("bodyfile", "")
            if not expected_file:
                expected_file = location.get("file", "")
            if normalize_path(expected_file) != normalize_path(file_info["file_name"]):
                continue
            expected_id = clone_id(compound_id, group_id)
            if expected_id not in file_info["raw_blocks"]:
                continue
            index_count = sum(
                1
                for item in index_compound.findall("member")
                if item.get("refid", "") == expected_id
            )
            if index_count != 1:
                raise MaterializeError(
                    "具象化済み ID の index.xml 参照が 1 件ではありません: {}".format(
                        expected_id
                    )
                )
            skipped += 1

    file_updates = {}
    index_updates = index_text
    for operation in operations:
        file_info = operation["file_info"]
        xml_path = file_info["xml_path"]
        text = file_updates.get(xml_path, texts[xml_path])
        pattern = member_ref_pattern(operation["old_id"])
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise MaterializeError(
                "{}: {} の member 参照が 1 件ではありません: {} 件".format(
                    xml_path, operation["old_id"], len(matches)
                )
            )
        file_updates[xml_path] = pattern.sub(operation["clone"], text, count=1)

        compound_pattern = index_compound_pattern(file_info["compound_id"])
        compound_matches = list(compound_pattern.finditer(index_updates))
        if len(compound_matches) != 1:
            raise MaterializeError(
                "index.xml の compound XML 断片が 1 件ではありません: {}".format(
                    file_info["compound_id"]
                )
            )
        compound_block = compound_matches[0].group(0)
        ref_pattern = re.compile(
            r'(<member\b[^>]*\brefid=")'
            + re.escape(operation["old_id"])
            + r'(")'
        )
        if len(ref_pattern.findall(compound_block)) != 1:
            raise MaterializeError(
                "index.xml の {} に {} の参照 XML が 1 件ではありません".format(
                    file_info["compound_id"], operation["old_id"]
                )
            )
        new_compound_block = ref_pattern.sub(
            r"\1" + operation["new_id"] + r"\2", compound_block, count=1
        )
        index_updates = (
            index_updates[: compound_matches[0].start()]
            + new_compound_block
            + index_updates[compound_matches[0].end() :]
        )

    for xml_path, updated in file_updates.items():
        xml_path.write_text(updated, encoding="utf-8", newline="\n")
    if operations:
        index_path.write_text(index_updates, encoding="utf-8", newline="\n")

    print(
        "[materialize-group-members] materialized: {}, already present: {}".format(
            len(operations), skipped
        )
    )
    return len(operations), skipped


def main():
    if len(sys.argv) != 2:
        print("Usage: {} <xml_dir>".format(sys.argv[0]), file=sys.stderr)
        return 2
    xml_dir = Path(sys.argv[1])
    if not xml_dir.is_dir():
        print("Error: xml_dir does not exist: {}".format(xml_dir), file=sys.stderr)
        return 2
    try:
        materialize(xml_dir)
    except MaterializeError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
