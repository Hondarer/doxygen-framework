#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate-dependency-report.py - Doxygen XML から依存関係レポートを生成する

使用方法:
    python3 generate-dependency-report.py <xml_directory> <output_directory> [category_id]
"""

from __future__ import annotations

import csv
import html
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


SCRIPT_DIR = Path(__file__).resolve().parent
GRAPH_ASSETS = (
    "cytoscape.min.js",
    "cytoscape.LICENSE.txt",
    "webcola.min.js",
    "webcola.LICENSE.txt",
    "cytoscape-cola.js",
    "cytoscape-cola.LICENSE.txt",
)


@dataclass
class FunctionInfo:
    id: str
    name: str
    file: str
    line: Optional[int]
    body_file: str
    body_line: Optional[int]
    compound_id: str
    is_static: bool
    is_exported: bool
    html_url: str = ""
    source_url: str = ""
    brief: str = ""
    callees: Set[str] = field(default_factory=set)
    callers: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class DefinitionLocation:
    file: str
    line: int


def normalize_path(path_text: str) -> str:
    return path_text.replace("\\", "/")


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def xml_files(xml_dir: Path) -> Iterable[Path]:
    for path in sorted(xml_dir.glob("*.xml")):
        if path.name == "combine.xslt" or path.name.startswith("index"):
            continue
        yield path


def find_text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def xml_inner_text(element: Optional[ET.Element]) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def codeline_text(element: ET.Element) -> str:
    parts: List[str] = []

    def append_text(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            if child.tag == "sp":
                parts.append(" ")
            else:
                append_text(child)
            if child.tail:
                parts.append(child.tail)

    append_text(element)
    return "".join(parts)


def collect_file_compound_ids(xml_dir: Path) -> Dict[str, str]:
    file_compounds: Dict[str, str] = {}
    for path in xml_files(xml_dir):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue

        compound = root.find("compounddef")
        if compound is None or compound.get("kind") != "file":
            continue

        compound_id = compound.get("id", "")
        if compound_id == "":
            continue

        names = set()
        compound_name = find_text(compound, "compoundname")
        if compound_name:
            names.add(normalize_path(compound_name))
        location = compound.find("location")
        if location is not None:
            file_name = normalize_path(location.get("file", ""))
            if file_name:
                names.add(file_name)

        for name in names:
            file_compounds[name] = compound_id

    return file_compounds


def collect_file_briefs(xml_dir: Path) -> Dict[str, str]:
    file_briefs: Dict[str, str] = {}
    for path in xml_files(xml_dir):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue

        compound = root.find("compounddef")
        if compound is None or compound.get("kind") != "file":
            continue

        brief = xml_inner_text(compound.find("briefdescription"))
        if not brief:
            continue

        compound_name = find_text(compound, "compoundname")
        if compound_name:
            file_briefs.setdefault(normalize_path(compound_name), brief)
        location = compound.find("location")
        if location is not None:
            file_name = normalize_path(location.get("file", ""))
            if file_name:
                file_briefs.setdefault(file_name, brief)

    return file_briefs


def score_function_info(info: FunctionInfo) -> Tuple[int, int, int]:
    body_score = 1 if info.body_file else 0
    file_score = 1 if info.file else 0
    line_score = 1 if info.line is not None or info.body_line is not None else 0
    return body_score, file_score, line_score


def canonical_priority(info: FunctionInfo) -> Tuple[int, int, int, str]:
    group_penalty = 0 if not info.compound_id.startswith("group__") else -1
    body_score = 1 if info.body_file else 0
    line_score = 1 if info.line is not None else 0
    return group_penalty, body_score, line_score, info.id


def dedupe_key(info: FunctionInfo) -> Tuple[str, ...]:
    if info.name and info.file and info.line is not None:
        return info.name, info.file, str(info.line)
    return info.id,


def build_html_url(compound_id: str, func_id: str) -> str:
    if compound_id == "" or func_id == "":
        return ""
    prefix = compound_id + "_1"
    if func_id.startswith(prefix):
        anchor = func_id[len(prefix):]
    else:
        anchor = func_id
    return f"../{compound_id}.html#{anchor}"


def build_source_url(compound_id: str, line: Optional[int]) -> str:
    if compound_id == "" or line is None:
        return ""
    return f"../{compound_id}_source.html#l{line:05d}"


def build_file_html_url(compound_id: str) -> str:
    if compound_id == "":
        return ""
    return f"../{compound_id}.html"


def build_file_source_url(compound_id: str) -> str:
    if compound_id == "":
        return ""
    return f"../{compound_id}_source.html"


def collect_raw_functions(xml_dir: Path) -> Dict[str, FunctionInfo]:
    functions: Dict[str, FunctionInfo] = {}
    file_compound_ids = collect_file_compound_ids(xml_dir)

    for path in xml_files(xml_dir):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print(f"Warning: failed to parse XML: {path}: {exc}", file=sys.stderr)
            continue

        compound = root.find("compounddef")
        if compound is None:
            continue
        compound_id = compound.get("id", "")

        for member in compound.findall(".//memberdef[@kind='function']"):
            func_id = member.get("id", "")
            if func_id == "":
                continue

            name = find_text(member, "name")
            location = member.find("location")
            file_path = ""
            line = None
            body_file = ""
            body_line = None
            if location is not None:
                file_path = normalize_path(location.get("file", ""))
                line = parse_int(location.get("line"))
                body_file = normalize_path(location.get("bodyfile", ""))
                body_line = parse_int(location.get("bodystart"))

            effective_file = body_file or file_path
            effective_line = body_line if body_line is not None else line
            info = FunctionInfo(
                id=func_id,
                name=name or func_id,
                file=effective_file,
                line=effective_line,
                body_file=body_file,
                body_line=body_line,
                compound_id=compound_id,
                is_static=member.get("static") == "yes",
                is_exported=is_public_include_header(file_path) or is_public_include_header(body_file),
            )
            info.html_url = build_html_url(compound_id, func_id)
            source_compound_id = file_compound_ids.get(effective_file, "")
            info.source_url = build_source_url(source_compound_id, effective_line)
            info.brief = xml_inner_text(member.find("briefdescription"))
            info.callees = {
                ref.get("refid", "")
                for ref in member.findall("references")
                if ref.get("refid", "") != ""
            }
            info.callers = {
                ref.get("refid", "")
                for ref in member.findall("referencedby")
                if ref.get("refid", "") != ""
            }

            current = functions.get(func_id)
            if current is None or score_function_info(info) > score_function_info(current):
                if current is not None:
                    info.callees.update(current.callees)
                    info.callers.update(current.callers)
                functions[func_id] = info
            else:
                current.callees.update(info.callees)
                current.callers.update(info.callers)

    return functions


def canonicalize_functions(raw_functions: Dict[str, FunctionInfo]) -> Dict[str, FunctionInfo]:
    grouped: Dict[Tuple[str, ...], List[FunctionInfo]] = defaultdict(list)
    for info in raw_functions.values():
        grouped[dedupe_key(info)].append(info)

    alias_to_canonical: Dict[str, str] = {}
    canonical_functions: Dict[str, FunctionInfo] = {}
    canonical_aliases: Dict[str, Set[str]] = {}

    for candidates in grouped.values():
        canonical = max(candidates, key=canonical_priority)
        merged_brief = canonical.brief or next(
            (candidate.brief for candidate in candidates if candidate.brief),
            "",
        )
        merged = FunctionInfo(
            id=canonical.id,
            name=canonical.name,
            file=canonical.file,
            line=canonical.line,
            body_file=canonical.body_file,
            body_line=canonical.body_line,
            compound_id=canonical.compound_id,
            is_static=any(candidate.is_static for candidate in candidates),
            is_exported=any(candidate.is_exported for candidate in candidates),
            html_url=canonical.html_url,
            source_url=canonical.source_url,
            brief=merged_brief,
        )
        for candidate in candidates:
            alias_to_canonical[candidate.id] = canonical.id
            merged.callees.update(candidate.callees)
            merged.callers.update(candidate.callers)
        canonical_functions[canonical.id] = merged
        canonical_aliases[canonical.id] = {candidate.id for candidate in candidates}

    scope = set(raw_functions.keys())
    canonical_scope = set(canonical_functions.keys())
    for canonical_id, info in canonical_functions.items():
        remapped_callees = set()
        for callee_id in info.callees:
            if callee_id not in scope:
                continue
            mapped_id = alias_to_canonical[callee_id]
            if mapped_id != canonical_id or callee_id == canonical_id:
                remapped_callees.add(mapped_id)
        info.callees = remapped_callees.intersection(canonical_scope)
        info.callers = set()

    for caller_id, info in canonical_functions.items():
        for callee_id in info.callees:
            canonical_functions[callee_id].callers.add(caller_id)

    return canonical_functions


HEADER_EXTENSIONS = (".h", ".hpp", ".hxx", ".hh")
SOURCE_EXTENSIONS = (".c", ".cpp", ".cxx", ".cc", ".cs")


def is_header_path(path: str) -> bool:
    return path.lower().endswith(HEADER_EXTENSIONS)


def is_source_path(path: str) -> bool:
    return path.lower().endswith(SOURCE_EXTENSIONS)


def is_public_include_header(path: str) -> bool:
    return path_area(path) == "include" and is_header_path(path)


def source_definition_area_rank(path: str) -> int:
    area = path_area(path)
    if area == "libsrc":
        return 0
    if area == "include_internal":
        return 1
    if area == "src":
        return 2
    return 3


def source_definition_platform_rank(path: str) -> int:
    name = Path(path).name.lower()
    if "_linux." in name:
        return 0
    if "_windows." in name:
        return 1
    return 2


def source_definition_sort_key(location: DefinitionLocation) -> Tuple[int, int, str, int]:
    return (
        source_definition_area_rank(location.file),
        source_definition_platform_rank(location.file),
        location.file,
        location.line,
    )


def is_definition_reference_line(line_text: str, function_name: str) -> bool:
    text = " ".join(line_text.strip().split())
    if text == "" or function_name == "" or ";" in text:
        return False

    match = re.search(r"(^|[^A-Za-z0-9_])" + re.escape(function_name) + r"\s*\(", text)
    if match is None:
        return False

    prefix = text[: match.start()].strip()
    if prefix == "":
        return False
    if re.search(r"(^|[^A-Za-z0-9_])(if|for|while|switch|return|sizeof)\s*\(?$", prefix):
        return False
    if re.search(r"(\=|\!|\<|\>|\&\&|\|\|)\s*$", prefix):
        return False
    return True


def choose_definition_location(candidates: List[DefinitionLocation]) -> Optional[DefinitionLocation]:
    if not candidates:
        return None
    return min(candidates, key=source_definition_sort_key)


def find_definition_locations(
    xml_dir: Path,
    needed_ids: Set[str],
    canonical_alias_map: Dict[str, str],
) -> Dict[str, DefinitionLocation]:
    if not needed_ids:
        return {}
    candidates: Dict[str, List[DefinitionLocation]] = defaultdict(list)
    for path in xml_files(xml_dir):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        compound = root.find("compounddef")
        if compound is None or compound.get("kind") != "file":
            continue
        location = compound.find("location")
        if location is None:
            continue
        compound_file = normalize_path(location.get("file", ""))
        if not compound_file or not is_source_path(compound_file):
            continue
        programlisting = compound.find("programlisting")
        if programlisting is None:
            continue
        for codeline in programlisting.findall("codeline"):
            lineno = parse_int(codeline.get("lineno"))
            if lineno is None:
                continue
            text = codeline_text(codeline)
            if ";" in text:
                continue
            for ref in codeline.findall(".//ref"):
                refid = ref.get("refid", "")
                if refid == "":
                    continue
                target = canonical_alias_map.get(refid, refid)
                if target not in needed_ids:
                    continue
                function_name = xml_inner_text(ref)
                if not is_definition_reference_line(text, function_name):
                    continue
                candidates[target].append(DefinitionLocation(compound_file, lineno))
    results: Dict[str, DefinitionLocation] = {}
    for target, target_candidates in candidates.items():
        location = choose_definition_location(target_candidates)
        if location is not None:
            results[target] = location
    return results


def warn_include_definition_src_fallback(info: FunctionInfo, location: DefinitionLocation) -> None:
    if path_area(location.file) != "src":
        return
    if path_area(info.file) not in {"include", "include_internal"}:
        return
    print(
        "Warning: include function definition fallback to src: {} ({}:{})".format(
            info.name,
            location.file,
            location.line,
        ),
        file=sys.stderr,
    )


def apply_definition_locations(
    xml_dir: Path,
    functions: Dict[str, FunctionInfo],
) -> None:
    needed = {fid for fid, info in functions.items() if is_header_path(info.file)}
    if not needed:
        return
    alias_map: Dict[str, str] = {}
    for fid in functions:
        alias_map[fid] = fid
    definitions = find_definition_locations(xml_dir, needed, alias_map)
    if not definitions:
        return
    file_compound_ids = collect_file_compound_ids(xml_dir)
    for fid, location in definitions.items():
        info = functions[fid]
        warn_include_definition_src_fallback(info, location)
        def_file = location.file
        def_line = location.line
        info.file = def_file
        info.line = def_line
        info.body_file = def_file
        info.body_line = def_line
        source_compound_id = file_compound_ids.get(def_file, "")
        info.source_url = build_source_url(source_compound_id, def_line)


def collect_functions(xml_dir: Path) -> Dict[str, FunctionInfo]:
    functions = canonicalize_functions(collect_raw_functions(xml_dir))
    apply_definition_locations(xml_dir, functions)
    return functions


def tarjan_scc(nodes: Iterable[str], edges: Dict[str, Set[str]]) -> List[List[str]]:
    index = 0
    stack: List[str] = []
    on_stack: Set[str] = set()
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    result: List[List[str]] = []

    def strong_connect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in edges.get(node, set()):
            if target not in indices:
                strong_connect(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] == indices[node]:
            component = []
            while True:
                popped = stack.pop()
                on_stack.remove(popped)
                component.append(popped)
                if popped == node:
                    break
            result.append(component)

    for node in nodes:
        if node not in indices:
            strong_connect(node)

    return result


def detect_cycle_groups(functions: Dict[str, FunctionInfo]) -> Tuple[Dict[str, str], List[Dict[str, object]]]:
    edges = {func_id: set(info.callees) for func_id, info in functions.items()}
    components = tarjan_scc(functions.keys(), edges)
    func_to_scc: Dict[str, str] = {}
    sccs: List[Dict[str, object]] = []

    next_id = 1
    for component in components:
        has_self_loop = len(component) == 1 and component[0] in edges.get(component[0], set())
        if len(component) <= 1 and not has_self_loop:
            continue
        scc_id = f"scc-{next_id}"
        next_id += 1
        for func_id in component:
            func_to_scc[func_id] = scc_id
        sccs.append(
            {
                "id": scc_id,
                "size": len(component),
                "functions": sorted(component, key=lambda value: functions[value].name),
            }
        )

    return func_to_scc, sccs


AREA_ORDER = {
    "same-file": 1,
    "include-callee": 2,
    "libsrc-file-caller": 3,
    "src-file-caller": 4,
    "other-to-libsrc-caller": 5,
    "cross-area-caller": 6,
}

DEPENDENCY_RANKS = {
    "leaf-static": 0,
    "leaf-global": 1,
    "file-local": 2,
    "include-callee": 2,
    "libsrc-file-caller": 3,
    "src-file-caller": 4,
    "other-to-libsrc-caller": 5,
    "cross-area-caller": 6,
    "cycle": 999,
}

DEPENDENCY_LEVEL_BASES = {
    "leaf-static": 0,
    "leaf-global": 1000,
    "file-local": 2000,
    "include-callee": 2000,
    "libsrc-file-caller": 3000,
    "src-file-caller": 4000,
    "other-to-libsrc-caller": 5000,
    "cross-area-caller": 6000,
}

CYCLE_DEPENDENCY_LEVEL_BASE = 9000


def path_area(file_path: str) -> str:
    parts = [part for part in normalize_path(file_path).split("/") if part]
    if "libsrc" in parts:
        return "libsrc"
    if "src" in parts:
        return "src"
    if "include_internal" in parts:
        return "include_internal"
    if "include" in parts:
        return "include"
    return "other"


# Doxygen が制御構文を phantom memberdef として生成するとき、name に C キーワードが設定される。
# bodyfile はソースファイルを指すため body_file == "" チェックでは除外できない。
_C_KEYWORDS: frozenset = frozenset({
    "if", "else", "for", "while", "do", "switch", "case", "default",
    "break", "continue", "return", "goto",
    "sizeof", "typeof", "_Alignof",
    "typedef", "struct", "union", "enum",
    "extern", "static", "inline", "register", "auto", "volatile",
    "const", "restrict", "_Atomic",
    "void", "int", "char", "short", "long", "float", "double",
    "unsigned", "signed", "_Bool", "_Complex", "_Imaginary",
})


def is_external_function(info: FunctionInfo) -> bool:
    """自ライブラリに含まれない外部関数かどうかを判定する。

    Doxygen は以下の 2 種類の phantom memberdef を生成することがある。いずれも依存関係レポートの
    対象外とする。

    1. 標準ライブラリなどプロジェクト外の関数:
       呼び出し箇所を location とした phantom エントリが生成される。bodyfile を持たないため
       body_file == "" で識別する。

    2. C キーワード (if, for, while など):
       EXTRACT_ALL=YES のとき Doxygen が制御構文を「関数」として memberdef に出力することがある。
       この場合 bodyfile がソースファイルを指すため body_file == "" では除外できない。
       name が C キーワードかどうかで識別する。
    """
    if info.name in _C_KEYWORDS:
        return True
    return info.body_file == ""


def classify_call_kind(caller: FunctionInfo, callee: FunctionInfo) -> str:
    if caller.file == callee.file:
        return "same-file"

    caller_area = path_area(caller.file)
    callee_area = path_area(callee.file)

    if callee_area == "include" and caller_area in {"libsrc", "src", "include_internal"}:
        return "include-callee"
    if callee_area == "include_internal" and caller_area == "libsrc":
        return "include-callee"

    if caller_area == "libsrc" and callee_area == "libsrc":
        return "libsrc-file-caller"
    if caller_area == "src" and callee_area == "src":
        return "src-file-caller"
    if caller_area != "libsrc" and callee_area == "libsrc":
        return "other-to-libsrc-caller"
    return "cross-area-caller"


def warn_reverse_boundary_call(caller: FunctionInfo, callee: FunctionInfo) -> None:
    if path_area(caller.file) != "libsrc" or path_area(callee.file) != "src":
        return
    print(
        "Warning: reverse-boundary-caller detected: {} ({}:{}) -> {} ({}:{})".format(
            caller.name,
            caller.file,
            caller.line if caller.line is not None else "",
            callee.name,
            callee.file,
            callee.line if callee.line is not None else "",
        ),
        file=sys.stderr,
    )


def dominant_call_kind(info: FunctionInfo, functions: Dict[str, FunctionInfo]) -> str:
    if not info.callees:
        return "none"
    return max(
        (classify_call_kind(info, functions[callee_id]) for callee_id in info.callees),
        key=lambda kind: AREA_ORDER[kind],
    )


def compute_dependency_depths(
    functions: Dict[str, FunctionInfo],
    cycle_map: Dict[str, str],
) -> Dict[str, Optional[int]]:
    depths: Dict[str, Optional[int]] = {}
    visiting: Set[str] = set()

    def visit(func_id: str) -> Optional[int]:
        if func_id in depths:
            return depths[func_id]
        if func_id in cycle_map:
            depths[func_id] = None
            return None
        if func_id in visiting:
            depths[func_id] = None
            return None

        visiting.add(func_id)
        max_depth = -1
        for callee_id in functions[func_id].callees:
            callee_depth = visit(callee_id)
            if callee_depth is None:
                callee_depth = 0
            max_depth = max(max_depth, callee_depth)
        visiting.remove(func_id)

        depths[func_id] = max_depth + 1
        return depths[func_id]

    for func_id in functions:
        visit(func_id)

    return depths


def classify_function(info: FunctionInfo, functions: Dict[str, FunctionInfo], cycle_map: Dict[str, str]) -> str:
    if info.id in cycle_map:
        return "cycle"
    if not info.callees:
        if info.is_static:
            return "leaf-static"
        return "leaf-global"
    call_kind = dominant_call_kind(info, functions)
    if call_kind == "same-file":
        return "file-local"
    return call_kind


def compute_dependency_level(
    info: FunctionInfo,
    dependency_class: str,
    dependency_depth: Optional[int],
    cycle_group_size: Optional[int],
) -> Optional[int]:
    if dependency_class == "cycle" and cycle_group_size is not None:
        return CYCLE_DEPENDENCY_LEVEL_BASE + cycle_group_size
    if dependency_depth is None:
        return None
    base = DEPENDENCY_LEVEL_BASES[dependency_class]
    if dependency_class in {"leaf-static", "leaf-global"}:
        return base + len(info.callers)
    return base + dependency_depth


def build_report_data(xml_dir: Path, output_dir: Path, category_id: str) -> Dict[str, object]:
    all_functions = collect_functions(xml_dir)

    external_ids: Set[str] = {fid for fid, info in all_functions.items() if is_external_function(info)}
    functions: Dict[str, FunctionInfo] = {fid: info for fid, info in all_functions.items() if fid not in external_ids}

    owned_to_external_callees: Dict[str, List[Dict[str, str]]] = {}
    for fid, info in functions.items():
        ext_names: List[str] = sorted(
            {all_functions[cid].name for cid in info.callees if cid in external_ids}
        )
        owned_to_external_callees[fid] = [{"name": n} for n in ext_names]
        info.callees = {cid for cid in info.callees if cid not in external_ids}

    for info in functions.values():
        info.callers = set()
    for caller_id, info in functions.items():
        for callee_id in info.callees:
            if callee_id in functions:
                functions[callee_id].callers.add(caller_id)

    cycle_map, sccs = detect_cycle_groups(functions)
    cycle_group_sizes = {str(scc["id"]): int(scc["size"]) for scc in sccs}
    depths = compute_dependency_depths(functions, cycle_map)
    file_briefs = collect_file_briefs(xml_dir)
    file_compound_ids = collect_file_compound_ids(xml_dir)

    function_rows: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []
    file_groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    for func_id, info in functions.items():
        dependency_class = classify_function(info, functions, cycle_map)
        dependency_rank = DEPENDENCY_RANKS[dependency_class]
        dependency_depth = depths[func_id]
        scc_id = cycle_map.get(func_id)
        cycle_group_size = cycle_group_sizes.get(scc_id) if scc_id is not None else None
        dependency_level = compute_dependency_level(info, dependency_class, dependency_depth, cycle_group_size)
        source_area = path_area(info.file)
        callee_areas = sorted({path_area(functions[callee_id].file) for callee_id in info.callees})
        max_callee_area = ""
        if callee_areas:
            max_callee_area = max(
                callee_areas,
                key=lambda area: max(
                    AREA_ORDER[classify_call_kind(info, functions[callee_id])]
                    for callee_id in info.callees
                    if path_area(functions[callee_id].file) == area
                ),
            )
        same_file_callees = sum(1 for callee_id in info.callees if functions[callee_id].file == info.file)
        cross_file_callees = len(info.callees) - same_file_callees
        row = {
            "id": info.id,
            "name": info.name,
            "file": info.file,
            "line": info.line,
            "isStatic": info.is_static,
            "isExported": info.is_exported,
            "dependencyLevel": dependency_level,
            "dependencyRank": dependency_rank,
            "dependencyDepth": dependency_depth,
            "dependencyClass": dependency_class,
            "sourceArea": source_area,
            "maxCalleeArea": max_callee_area,
            "dominantCallKind": dominant_call_kind(info, functions),
            "inScopeCalleeCount": len(info.callees),
            "inScopeCallerCount": len(info.callers),
            "sameFileCalleeCount": same_file_callees,
            "crossFileCalleeCount": cross_file_callees,
            "sccId": scc_id,
            "cycleGroupSize": cycle_group_size,
            "htmlUrl": info.html_url,
            "sourceUrl": info.source_url,
            "brief": info.brief,
            "externalCallees": owned_to_external_callees.get(func_id, []),
            "externalCalleeCount": len(owned_to_external_callees.get(func_id, [])),
        }
        function_rows.append(row)
        file_groups[info.file].append(row)

        for callee_id in sorted(info.callees):
            callee = functions[callee_id]
            warn_reverse_boundary_call(info, callee)
            edges.append(
                {
                    "caller": func_id,
                    "callee": callee_id,
                    "sameFile": callee.file == info.file,
                    "callKind": classify_call_kind(info, callee),
                    "callerArea": source_area,
                    "calleeArea": path_area(callee.file),
                    "callerFile": info.file,
                    "calleeFile": callee.file,
                }
            )

    function_rows.sort(
        key=lambda row: (
            row["dependencyLevel"] is None,
            row["dependencyLevel"] if row["dependencyLevel"] is not None else 999999,
            row["dependencyClass"],
            row["file"],
            row["name"],
        )
    )
    edges.sort(key=lambda row: (row["callerFile"], row["caller"], row["callee"]))

    file_edge_map: Dict[Tuple[str, str], Dict[str, object]] = {}
    for edge in edges:
        if edge["callerFile"] == edge["calleeFile"]:
            continue
        key = (str(edge["callerFile"]), str(edge["calleeFile"]))
        current = file_edge_map.get(key)
        if current is None:
            current = {
                "id": f"{key[0]}\n{key[1]}",
                "source": key[0],
                "target": key[1],
                "fromFile": key[0],
                "toFile": key[1],
                "weight": 0,
                "label": "",
            }
            file_edge_map[key] = current
        current["weight"] = int(current["weight"]) + 1
        current["label"] = str(current["weight"])
    file_edges = [file_edge_map[key] for key in sorted(file_edge_map)]

    file_rows = []
    for file_path, rows in sorted(file_groups.items()):
        level_counts: Dict[str, int] = defaultdict(int)
        class_counts: Dict[str, int] = defaultdict(int)
        area_counts: Dict[str, int] = defaultdict(int)
        dominant_area = ""
        for row in rows:
            level_key = "cycle" if row["dependencyLevel"] is None else str(row["dependencyLevel"])
            level_counts[level_key] += 1
            class_counts[str(row["dependencyClass"])] += 1
            area_counts[str(row["sourceArea"])] += 1
        if area_counts:
            dominant_area = max(sorted(area_counts), key=lambda key: (area_counts[key], key))
        file_rows.append(
            {
                "path": file_path,
                "functionCount": len(rows),
                "exportCount": sum(1 for row in rows if row["isExported"]),
                "staticCount": sum(1 for row in rows if row["isStatic"]),
                "edgeCount": sum(int(row["inScopeCalleeCount"]) for row in rows),
                "dominantArea": dominant_area,
                "levels": dict(sorted(level_counts.items())),
                "classes": dict(sorted(class_counts.items())),
                "areas": dict(sorted(area_counts.items())),
                "brief": file_briefs.get(file_path, ""),
                "htmlUrl": build_file_html_url(file_compound_ids.get(file_path, "")),
                "sourceUrl": build_file_source_url(file_compound_ids.get(file_path, "")),
            }
        )

    summary = {
        "functionCount": len(function_rows),
        "edgeCount": len(edges),
        "fileCount": len(file_rows),
        "cycleGroupCount": len(sccs),
        "exportCount": sum(1 for row in function_rows if row["isExported"]),
        "staticCount": sum(1 for row in function_rows if row["isStatic"]),
        "leafCount": sum(1 for row in function_rows if row["inScopeCalleeCount"] == 0),
    }

    return {
        "meta": {
            "categoryId": category_id,
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "xmlDir": normalize_path(str(xml_dir)),
            "outputDir": normalize_path(str(output_dir)),
            "source": "doxygen-xml",
        },
        "summary": summary,
        "functions": function_rows,
        "edges": edges,
        "fileEdges": file_edges,
        "files": file_rows,
        "sccs": sccs,
    }


def write_data_js(output_dir: Path, data: Dict[str, object]) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    (output_dir / "dependency-data.js").write_text(
        "window.DoxyfwDependencyData = " + text + ";\n",
        encoding="utf-8",
    )


def write_data_json(output_dir: Path, data: Dict[str, object]) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    (output_dir / "dependency-data.json").write_text(text + "\n", encoding="utf-8")


def write_csv(output_dir: Path, data: Dict[str, object]) -> None:
    def write_dict_csv(file_name: str, encoding: str, fieldnames: List[str], rows: Iterable[Dict[str, object]]) -> None:
        with (output_dir / file_name).open("w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})

    function_fields = [
        "dependencyLevel",
        "dependencyRank",
        "dependencyDepth",
        "dependencyClass",
        "sourceArea",
        "maxCalleeArea",
        "dominantCallKind",
        "isExported",
        "isStatic",
        "name",
        "file",
        "line",
        "inScopeCalleeCount",
        "inScopeCallerCount",
        "sameFileCalleeCount",
        "crossFileCalleeCount",
        "sccId",
        "cycleGroupSize",
        "id",
        "htmlUrl",
        "sourceUrl",
        "brief",
    ]
    write_dict_csv("dependency-functions.csv", "utf-8", function_fields, data["functions"])
    write_dict_csv("dependency-functions-utf8-bom.csv", "utf-8-sig", function_fields, data["functions"])

    file_fields = [
        "path",
        "functionCount",
        "exportCount",
        "staticCount",
        "edgeCount",
        "dominantArea",
        "levels",
        "classes",
        "areas",
        "brief",
        "htmlUrl",
        "sourceUrl",
    ]
    file_rows = []
    for row in data["files"]:
        file_rows.append(
            {
                "path": row["path"],
                "functionCount": row["functionCount"],
                "exportCount": row["exportCount"],
                "staticCount": row["staticCount"],
                "edgeCount": row["edgeCount"],
                "dominantArea": row["dominantArea"],
                "levels": json.dumps(row["levels"], ensure_ascii=False, sort_keys=True),
                "classes": json.dumps(row["classes"], ensure_ascii=False, sort_keys=True),
                "areas": json.dumps(row["areas"], ensure_ascii=False, sort_keys=True),
                "brief": row.get("brief", ""),
                "htmlUrl": row.get("htmlUrl", ""),
                "sourceUrl": row.get("sourceUrl", ""),
            }
        )
    write_dict_csv("dependency-files.csv", "utf-8", file_fields, file_rows)
    write_dict_csv("dependency-files-utf8-bom.csv", "utf-8-sig", file_fields, file_rows)


def write_html(output_dir: Path, category_id: str) -> None:
    title = "依存関係レポート"
    escaped_category = html.escape(category_id or "doxygen")
    js_category = json.dumps(category_id or "doxygen", ensure_ascii=False)
    html_text = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="../doxygen.css">
  <script src="dependency-data.js"></script>
  <script src="cytoscape.min.js"></script>
  <script src="webcola.min.js"></script>
  <script src="cytoscape-cola.js"></script>
  <script>
    (function () {{
      "use strict";
      const key = "doxyfw-dependency-theme";
      let theme = "";
      try {{
        theme = window.localStorage ? window.localStorage.getItem(key) || "" : "";
      }} catch (err) {{
        theme = "";
      }}
      if (theme !== "light" && theme !== "dark") {{
        theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }}
      document.documentElement.setAttribute("data-theme", theme);
    }}());
  </script>
  <style>
    :root {{
      color-scheme: light;
      --dep-page-bg: #ffffff;
      --dep-text: #111827;
      --dep-muted: #596579;
      --dep-border: #d8dee8;
      --dep-bg: #f7f9fc;
      --dep-accent: #0e639c;
      --dep-warning: #a16207;
      --dep-danger: #b91c1c;
      --dep-input-bg: #ffffff;
      --dep-input-text: #1f2937;
      --dep-input-border: #b8c2d1;
      --dep-input-focus: #0e639c;
      --dep-table-scrollbar-thumb: #888888;
      --dep-table-scrollbar-thumb-hover: #757575;
      --dep-filter-warning-bg: #fef3c7;
      --dep-filter-warning-text: #713f12;
      --dep-badge-text: #111827;
      --dep-badge-leaf-bg: #dcfce7;
      --dep-badge-leaf-border: #16a34a;
      --dep-badge-local-bg: #e0f2fe;
      --dep-badge-local-border: #0284c7;
      --dep-badge-cycle-bg: #fee2e2;
      --dep-badge-cycle-border: #dc2626;
      --dep-badge-caller-bg: #fef3c7;
      --dep-badge-caller-border: #d97706;
      --dep-badge-library-bg: #eef2ff;
      --dep-badge-library-border: #4f46e5;
      --dep-badge-source-bg: #f3e8ff;
      --dep-badge-source-border: #9333ea;
      --dep-graph-bg: #ffffff;
      --dep-graph-label-bg: #ffffff;
      --dep-graph-text: #111827;
      --dep-graph-parent-text: #1f2937;
      --dep-graph-node-bg: #dbeafe;
      --dep-graph-node-border: #2563eb;
      --dep-graph-file-bg: #f8fafc;
      --dep-graph-file-border: #64748b;
      --dep-graph-muted-file-bg: #f8fafc;
      --dep-graph-muted-file-border: #dbe4f0;
      --dep-graph-muted-file-text: #a8b4c3;
      --dep-graph-parent-bg: #f1f5f9;
      --dep-graph-edge: #64748b;
      --dep-graph-muted-edge: #e2e8f0;
      --dep-graph-active-edge: #334155;
      --dep-graph-emphasis-edge: #111827;
      --dep-graph-leaf-bg: #dcfce7;
      --dep-graph-leaf-border: #16a34a;
      --dep-graph-local-bg: #e0f2fe;
      --dep-graph-local-border: #0284c7;
      --dep-graph-caller-bg: #fef3c7;
      --dep-graph-caller-border: #d97706;
      --dep-graph-danger-bg: #fee2e2;
      --dep-graph-danger-border: #dc2626;
      --dep-graph-library-bg: #eef2ff;
      --dep-graph-library-border: #4f46e5;
      --dep-graph-muted-library-bg: #f7f9ff;
      --dep-graph-muted-library-border: #d5ddff;
      --dep-graph-source-bg: #f3e8ff;
      --dep-graph-source-border: #9333ea;
      --dep-graph-muted-source-bg: #fbf5ff;
      --dep-graph-muted-source-border: #eadcff;
    }}
    :root[data-theme="dark"] {{
      color-scheme: dark;
      --dep-page-bg: #1e1e1e;
      --dep-text: #d4d4d4;
      --dep-muted: #9b9b9b;
      --dep-border: #3c3c3c;
      --dep-bg: #252526;
      --dep-accent: #3794d8;
      --dep-warning: #cca700;
      --dep-danger: #f48771;
      --dep-input-bg: #1e1e1e;
      --dep-input-text: #d4d4d4;
      --dep-input-border: #3c3c3c;
      --dep-input-focus: #3794d8;
      --dep-table-scrollbar-thumb: #676767;
      --dep-table-scrollbar-thumb-hover: #787878;
      --dep-filter-warning-bg: #3a3314;
      --dep-filter-warning-text: #d7ba7d;
      --dep-badge-text: #d4d4d4;
      --dep-badge-leaf-bg: #163b2b;
      --dep-badge-leaf-border: #4ec9b0;
      --dep-badge-local-bg: #17364a;
      --dep-badge-local-border: #4fc1ff;
      --dep-badge-cycle-bg: #4b2525;
      --dep-badge-cycle-border: #f48771;
      --dep-badge-caller-bg: #3f321b;
      --dep-badge-caller-border: #d7ba7d;
      --dep-badge-library-bg: #2d2a4a;
      --dep-badge-library-border: #9cdcfe;
      --dep-badge-source-bg: #3b2a4a;
      --dep-badge-source-border: #c586c0;
      --dep-graph-bg: #1e1e1e;
      --dep-graph-label-bg: #252526;
      --dep-graph-text: #d4d4d4;
      --dep-graph-parent-text: #d4d4d4;
      --dep-graph-node-bg: #264f78;
      --dep-graph-node-border: #3794ff;
      --dep-graph-file-bg: #252526;
      --dep-graph-file-border: #858585;
      --dep-graph-muted-file-bg: #171717;
      --dep-graph-muted-file-border: #242424;
      --dep-graph-muted-file-text: #505050;
      --dep-graph-parent-bg: #2d2d30;
      --dep-graph-edge: #858585;
      --dep-graph-muted-edge: #2d2d2d;
      --dep-graph-active-edge: #c5c5c5;
      --dep-graph-emphasis-edge: #f3f4f6;
      --dep-graph-leaf-bg: #163b2b;
      --dep-graph-leaf-border: #4ec9b0;
      --dep-graph-local-bg: #17364a;
      --dep-graph-local-border: #4fc1ff;
      --dep-graph-caller-bg: #3f321b;
      --dep-graph-caller-border: #d7ba7d;
      --dep-graph-danger-bg: #4b2525;
      --dep-graph-danger-border: #f48771;
      --dep-graph-library-bg: #2d2a4a;
      --dep-graph-library-border: #9cdcfe;
      --dep-graph-muted-library-bg: #1f1f22;
      --dep-graph-muted-library-border: #2a3134;
      --dep-graph-source-bg: #3b2a4a;
      --dep-graph-source-border: #c586c0;
      --dep-graph-muted-source-bg: #211f22;
      --dep-graph-muted-source-border: #2e282e;
    }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--dep-page-bg);
      color: var(--dep-text);
      scrollbar-color: color-mix(in srgb, var(--dep-accent) 55%, var(--dep-input-border)) var(--dep-input-bg);
      scrollbar-width: auto;
    }}
    body::-webkit-scrollbar,
    .dep-table-wrap::-webkit-scrollbar,
    .dep-detail::-webkit-scrollbar {{
      width: 14px;
      height: 14px;
    }}
    body::-webkit-scrollbar-track,
    .dep-table-wrap::-webkit-scrollbar-track,
    .dep-detail::-webkit-scrollbar-track {{
      background: var(--dep-input-bg);
    }}
    body::-webkit-scrollbar-thumb,
    .dep-table-wrap::-webkit-scrollbar-thumb,
    .dep-detail::-webkit-scrollbar-thumb {{
      border: 2px solid var(--dep-input-bg);
      border-radius: 999px;
      background: color-mix(in srgb, var(--dep-accent) 55%, var(--dep-input-border));
    }}
    body::-webkit-scrollbar-thumb:hover,
    .dep-table-wrap::-webkit-scrollbar-thumb:hover,
    .dep-detail::-webkit-scrollbar-thumb:hover {{
      background: color-mix(in srgb, var(--dep-accent) 75%, var(--dep-input-border));
    }}
    .dep-table-wrap::-webkit-scrollbar-thumb,
    .dep-detail::-webkit-scrollbar-thumb {{
      background: var(--dep-table-scrollbar-thumb);
    }}
    .dep-table-wrap::-webkit-scrollbar-thumb:hover,
    .dep-detail::-webkit-scrollbar-thumb:hover {{
      background: var(--dep-table-scrollbar-thumb-hover);
    }}
    main {{
      max-width: min(2000px, 96vw);
      margin: 0 auto;
      padding: 20px;
    }}
    h1 {{
      font-size: 1.6rem;
      margin: 0;
    }}
    .dep-title-row {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 12px;
    }}
    .dep-meta {{
      color: var(--dep-muted);
      display: inline;
      font-size: 1rem;
      font-weight: 400;
      margin-left: 10px;
    }}
    .dep-summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 8px;
      margin-bottom: 18px;
    }}
    .dep-metric {{
      display: flex;
      align-items: baseline;
      gap: 8px;
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      padding: 10px;
      background: var(--dep-bg);
    }}
    .dep-metric strong {{
      font-size: 1.35rem;
    }}
    .dep-controls {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) repeat(6, minmax(110px, 170px)) auto;
      gap: 8px;
      margin-bottom: 12px;
    }}
    .dep-file-controls {{
      grid-template-columns: minmax(220px, 1fr) repeat(5, minmax(110px, 170px)) auto;
    }}
    .dep-downloads {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .dep-title-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .dep-download-menu {{
      position: relative;
    }}
    .dep-download-menu.open > .dep-download-menu-button {{
      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-bg));
      border-color: var(--dep-accent);
      color: var(--dep-accent);
    }}
    .dep-download-menu-items {{
      position: absolute;
      right: 0;
      top: calc(100% + 4px);
      z-index: 20;
      min-width: 160px;
      display: grid;
      gap: 4px;
      padding: 6px;
      border: 1px solid var(--dep-border);
      border-radius: 4px;
      background: var(--dep-bg);
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
    }}
    .dep-download-menu-items[hidden] {{
      display: none;
    }}
    .dep-download-menu-items .dep-download {{
      border-color: transparent;
      background: transparent;
      justify-content: flex-start;
    }}
    .dep-download,
    .dep-download-menu-button,
    .dep-theme-toggle {{
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border: 1px solid var(--dep-border);
      border-radius: 4px;
      background: var(--dep-bg);
      color: var(--dep-input-text);
      text-decoration: none;
      font: inherit;
      font-size: 0.9rem;
      cursor: pointer;
    }}
    .dep-download:hover,
    .dep-download-menu-button:hover,
    .dep-theme-toggle:hover {{
      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-bg));
      border-color: var(--dep-accent);
      color: var(--dep-accent);
    }}
    .dep-download-menu-items .dep-download:hover {{
      border-color: transparent;
    }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      min-height: 34px;
      border: 1px solid var(--dep-input-border);
      border-radius: 4px;
      padding: 6px 8px;
      background: var(--dep-input-bg);
      color: var(--dep-input-text);
      color-scheme: inherit;
    }}
    select {{
      padding-right: 32px;
    }}
    input:focus, select:focus {{
      border-color: var(--dep-input-focus);
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--dep-input-focus) 18%, transparent);
      outline: none;
    }}
    select option {{
      background: var(--dep-input-bg);
      color: var(--dep-input-text);
      padding-right: 24px;
    }}
    .dep-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 340px;
      gap: 14px;
      align-items: start;
    }}
    .dep-table-panel {{
      min-width: 0;
    }}
    .dep-filter-notice {{
      display: none;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
      border: 1px solid color-mix(in srgb, var(--dep-warning) 45%, var(--dep-border));
      border-radius: 6px;
      padding: 8px 10px;
      background: var(--dep-filter-warning-bg);
      color: var(--dep-filter-warning-text);
    }}
    .dep-filter-notice.visible {{
      display: flex;
    }}
    .dep-neighbor-button,
    .dep-filter-clear {{
      border: 1px solid var(--dep-input-border);
      border-radius: 4px;
      background: var(--dep-input-bg);
      color: var(--dep-input-text);
      cursor: pointer;
      font: inherit;
    }}
    .dep-filter-clear {{
      flex: 0 0 auto;
      min-height: 34px;
      padding: 6px 12px;
      white-space: nowrap;
    }}
    .dep-filter-clear:hover {{
      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-bg));
      border-color: var(--dep-input-focus);
      color: var(--dep-input-focus);
    }}
    .dep-table-wrap {{
      overflow: auto;
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      max-height: calc(100vh - 310px);
      scrollbar-color: var(--dep-table-scrollbar-thumb) var(--dep-input-bg);
      scrollbar-width: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    th, td {{
      padding: 5px 7px;
      border-bottom: 1px solid var(--dep-border);
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      position: sticky;
      top: 0;
      background: var(--dep-bg);
      text-align: left;
      z-index: 1;
    }}
    .dep-sort-button {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border: 0;
      padding: 0;
      background: transparent;
      color: inherit;
      cursor: pointer;
      font: inherit;
      font-weight: 600;
      text-align: inherit;
    }}
    .dep-sort-button:hover {{
      color: var(--dep-accent);
    }}
    .dep-sort-mark {{
      display: inline-block;
      min-width: 1em;
      color: var(--dep-accent);
      font-size: 0.78rem;
      line-height: 1;
    }}
    .dep-num {{
      font-variant-numeric: tabular-nums;
      text-align: right;
    }}
    tr {{
      cursor: pointer;
    }}
    tr:hover {{
      background: color-mix(in srgb, var(--dep-border) 30%, transparent);
    }}
    tr.selected, tr.selected:hover {{
      background: color-mix(in srgb, var(--dep-accent) 18%, transparent);
    }}
    .dep-file {{
      max-width: 420px;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 6px;
      border: 1px solid var(--dep-border);
      background: var(--dep-bg);
      color: var(--dep-badge-text);
      font-size: 0.74rem;
      line-height: 1.2;
    }}
    .badge.leaf-static,
    .badge.leaf-global {{
      background: var(--dep-badge-leaf-bg);
      border-color: var(--dep-badge-leaf-border);
    }}
    .badge.file-local {{
      background: var(--dep-badge-local-bg);
      border-color: var(--dep-badge-local-border);
    }}
    .badge.cycle {{
      background: var(--dep-badge-cycle-bg);
      border-color: var(--dep-badge-cycle-border);
    }}
    .badge.libsrc-file-caller,
    .badge.src-file-caller,
    .badge.other-to-libsrc-caller,
    .badge.cross-area-caller {{
      background: var(--dep-badge-caller-bg);
      border-color: var(--dep-badge-caller-border);
    }}
    .badge.area-library {{
      background: var(--dep-badge-library-bg);
      border-color: var(--dep-badge-library-border);
    }}
    .badge.area-source {{
      background: var(--dep-badge-source-bg);
      border-color: var(--dep-badge-source-border);
    }}
    .dep-detail {{
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      padding: 12px;
      min-height: 240px;
      background: var(--dep-bg);
      box-sizing: border-box;
    }}
    .dep-detail h2 {{
      margin: 0 0 8px;
      font-size: 1.05rem;
      overflow-wrap: anywhere;
    }}
    .dep-detail .dep-brief {{
      margin: 0 0 12px;
      color: var(--dep-text);
      font-size: 0.95rem;
      line-height: 1.5;
      white-space: pre-wrap;
    }}
    .dep-detail dl {{
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr);
      gap: 6px 10px;
      margin: 0 0 12px;
    }}
    .dep-detail dt {{
      color: var(--dep-muted);
    }}
    .dep-detail dd {{
      margin: 0;
      overflow-wrap: anywhere;
    }}
    .dep-detail a {{
      color: var(--dep-accent);
      overflow-wrap: anywhere;
    }}
    .dep-detail a:hover {{
      color: var(--dep-accent);
      text-decoration-thickness: 2px;
    }}
    .dep-neighbors {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .dep-neighbors ul {{
      margin: 4px 0 0;
      padding-left: 18px;
    }}
    .dep-neighbor-button {{
      max-width: 100%;
      padding: 0;
      border-color: transparent;
      background: transparent;
      color: var(--dep-accent);
      text-align: left;
      text-decoration: none;
      white-space: normal;
      overflow-wrap: anywhere;
    }}
    .dep-neighbor-button:hover {{
      border-color: transparent;
      color: var(--dep-accent);
      text-decoration: none;
    }}
    .dep-neighbors small {{
      overflow-wrap: anywhere;
    }}
    .dep-external-callee {{
      color: var(--dep-muted);
      overflow-wrap: anywhere;
    }}
    .dep-empty {{
      color: var(--dep-muted);
    }}
    .dep-tabs {{
      display: flex;
      gap: 6px;
      margin: 0 0 12px;
      border-bottom: 1px solid var(--dep-border);
    }}
    .dep-tab {{
      min-height: 34px;
      border: 1px solid transparent;
      border-bottom: 0;
      border-radius: 6px 6px 0 0;
      padding: 6px 12px;
      background: transparent;
      color: var(--dep-input-text);
      cursor: pointer;
      font: inherit;
    }}
    .dep-tab.active {{
      border-color: var(--dep-border);
      background: var(--dep-bg);
      color: var(--dep-accent);
      font-weight: 600;
    }}
    .dep-panel {{
      display: none;
    }}
    .dep-panel.active {{
      display: block;
    }}
    .dep-graph-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 340px;
      gap: 14px;
      align-items: start;
    }}
    .dep-graph-shell {{
      position: relative;
      min-width: 0;
    }}
    .dep-graph-toolbar {{
      position: absolute;
      top: 10px;
      left: 10px;
      z-index: 40;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    /* inert 時はツールバー コンテナを hit-test 可能なまま残し、ボタンだけ無効化する。
       コンテナへ pointer-events:none を付けるとクリックが背後のグラフへ貫通し、レイアウト
       中の物理クリックが背景タップ (選択解除) を発火させてしまうため、ボタンで吸収する。 */
    .dep-graph-shell.controls-inert .dep-graph-toolbar button {{
      pointer-events: none;
      cursor: default;
      opacity: 0.55;
    }}
    .dep-graph-toolbar button {{
      min-height: 30px;
      border: 1px solid var(--dep-input-border);
      border-radius: 4px;
      padding: 4px 8px;
      background: var(--dep-input-bg);
      color: var(--dep-input-text);
      cursor: pointer;
      font: inherit;
    }}
    .dep-graph-toolbar button:hover {{
      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-bg));
      border-color: var(--dep-input-focus);
      color: var(--dep-input-focus);
    }}
    .dep-graph {{
      position: relative;
      width: 100%;
      height: calc(100vh - 260px);
      min-height: 520px;
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      background: var(--dep-graph-bg);
    }}
    .dep-graph-hidden-notice {{
      position: absolute;
      right: 10px;
      bottom: 10px;
      z-index: 30;
      display: none;
      padding: 4px 10px;
      border: 1px solid var(--dep-border);
      border-radius: 4px;
      background: var(--dep-input-bg);
      color: var(--dep-input-text);
      font: inherit;
      font-size: 0.78rem;
      cursor: pointer;
    }}
    .dep-graph-hidden-notice.visible {{
      display: block;
    }}
    .dep-graph-hidden-notice:hover {{
      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-input-bg));
      color: var(--dep-accent);
      border-color: var(--dep-accent);
    }}
    .dep-graph.layout-initializing::after,
    .dep-graph.layout-relayouting::after {{
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      color: var(--dep-muted);
      font-size: 0.95rem;
      padding: 8px 12px;
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      background: color-mix(in srgb, var(--dep-bg) 82%, transparent);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
      pointer-events: none;
      z-index: 20;
    }}
    .dep-graph.layout-initializing::after {{
      content: "初期化しています...";
    }}
    .dep-graph.layout-relayouting::after {{
      content: "レイアウトしています...";
    }}
    .dep-graph.layout-initializing::after,
    .dep-graph.layout-relayouting::after {{
      inset: 0;
      transform: none;
      border: 0;
      border-radius: 0;
      background: var(--dep-graph-bg);
      box-shadow: none;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .dep-graph.layout-initializing canvas,
    .dep-graph.layout-relayouting canvas {{
      opacity: 0;
    }}
    .dep-graph-note {{
      color: var(--dep-muted);
      margin: 0 0 8px;
    }}
    .dep-graph-detail ul {{
      margin: 6px 0 0;
      padding-left: 18px;
    }}
    .dep-graph-detail li {{
      margin: 2px 0;
      overflow-wrap: anywhere;
    }}
    .dep-graph-context-menu {{
      position: fixed;
      z-index: 1000;
      display: none;
      min-width: 180px;
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      padding: 4px;
      background: var(--dep-input-bg);
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18);
    }}
    .dep-graph-context-menu.visible {{
      display: block;
    }}
    .dep-graph-context-menu button {{
      display: block;
      width: 100%;
      min-height: 30px;
      border: 0;
      border-radius: 4px;
      padding: 6px 8px;
      background: transparent;
      color: var(--dep-input-text);
      cursor: pointer;
      font: inherit;
      text-align: left;
    }}
    .dep-graph-context-menu button:hover {{
      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-input-bg));
      color: var(--dep-accent);
    }}
    .dep-graph-context-menu-separator {{
      height: 0;
      margin: 4px 4px;
      border-top: 1px solid var(--dep-border);
    }}
    .dep-graph-context-menu-label {{
      padding: 6px 8px 2px;
      font-size: 11px;
      color: var(--dep-muted);
    }}
    .dep-graph-context-menu button.dep-menu-option {{
      padding-left: 24px;
      position: relative;
    }}
    .dep-graph-context-menu button.dep-menu-option.checked::before {{
      content: "\\2713";
      position: absolute;
      left: 8px;
    }}
    @media (min-width: 981px) {{
      html, body {{
        height: 100%;
        overflow: hidden;
      }}
      main {{
        box-sizing: border-box;
        height: 100vh;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }}
      .dep-summary {{
        flex: 0 0 auto;
      }}
      .dep-tabs {{
        flex: 0 0 auto;
      }}
      .dep-panel.active {{
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
      }}
      .dep-controls {{
        flex: 0 0 auto;
      }}
      .dep-layout,
      .dep-graph-layout {{
        flex: 1 1 auto;
        min-height: 0;
        align-items: stretch;
      }}
      .dep-table-panel {{
        display: flex;
        flex-direction: column;
        min-height: 0;
      }}
      .dep-graph-shell {{
        min-height: 0;
      }}
      .dep-filter-notice {{
        flex: 0 0 auto;
      }}
      .dep-table-wrap,
      .dep-detail {{
        max-height: 100%;
        overflow: auto;
        scrollbar-width: auto;
      }}
      .dep-table-wrap {{
        scrollbar-color: var(--dep-table-scrollbar-thumb) var(--dep-input-bg);
      }}
      .dep-detail {{
        scrollbar-color: var(--dep-table-scrollbar-thumb) var(--dep-input-bg);
      }}
      .dep-table-wrap {{
        flex: 1 1 auto;
        min-height: 0;
      }}
      .dep-graph {{
        height: 100%;
        min-height: 0;
      }}
    }}
    @media (max-width: 980px) {{
      main {{
        padding: 12px;
      }}
      .dep-title-row {{
        flex-direction: column;
        align-items: stretch;
      }}
      .dep-downloads {{
        justify-content: flex-start;
      }}
      .dep-download-menu-items {{
        left: 0;
        right: auto;
      }}
      .dep-title-actions {{
        justify-content: flex-start;
      }}
      .dep-controls, .dep-layout, .dep-graph-layout {{
        grid-template-columns: 1fr;
      }}
      .dep-table-wrap {{
        max-height: none;
      }}
      .dep-graph {{
        height: 70vh;
        min-height: 420px;
      }}
      .dep-metric {{
        display: block;
      }}
    }}
  </style>
</head>
<body>
<main>
  <div class="dep-title-row">
    <h1>{title}<span class="dep-meta">対象: {escaped_category}</span></h1>
    <div class="dep-title-actions">
      <button type="button" id="themeToggle" class="dep-theme-toggle" aria-pressed="false">ライト</button>
      <section class="dep-downloads" role="group" aria-label="ダウンロード">
        <a class="dep-download" href="dependency-data.json" download data-download-name="dependency-data.json" data-download-kind="json" title="JSON 形式の全データをダウンロード">JSON</a>
        <div class="dep-download-menu">
          <button type="button" class="dep-download-menu-button" aria-expanded="false" title="関数一覧の CSV をダウンロード">関数 CSV</button>
          <div class="dep-download-menu-items" hidden>
            <a class="dep-download" href="dependency-functions-utf8-bom.csv" download data-download-name="dependency-functions-utf8-bom.csv" data-download-kind="functions-csv" data-download-bom="true" title="関数一覧の CSV を UTF-8 BOM ありでダウンロード">BOMあり UTF-8</a>
            <a class="dep-download" href="dependency-functions.csv" download data-download-name="dependency-functions.csv" data-download-kind="functions-csv" title="関数一覧の CSV を UTF-8 BOM なしでダウンロード">BOMなし UTF-8</a>
          </div>
        </div>
        <div class="dep-download-menu">
          <button type="button" class="dep-download-menu-button" aria-expanded="false" title="ファイル一覧の CSV をダウンロード">ファイル CSV</button>
          <div class="dep-download-menu-items" hidden>
            <a class="dep-download" href="dependency-files-utf8-bom.csv" download data-download-name="dependency-files-utf8-bom.csv" data-download-kind="files-csv" data-download-bom="true" title="ファイル一覧の CSV を UTF-8 BOM ありでダウンロード">BOMあり UTF-8</a>
            <a class="dep-download" href="dependency-files.csv" download data-download-name="dependency-files.csv" data-download-kind="files-csv" title="ファイル一覧の CSV を UTF-8 BOM なしでダウンロード">BOMなし UTF-8</a>
          </div>
        </div>
      </section>
    </div>
  </div>
  <section class="dep-summary" id="summary"></section>
  <nav class="dep-tabs" aria-label="表示切り替え">
    <button type="button" class="dep-tab active" data-tab-target="functionListPanel">関数一覧</button>
    <button type="button" class="dep-tab" data-tab-target="fileListPanel">ファイル一覧</button>
    <button type="button" class="dep-tab" data-tab-target="overviewPanel">全体マップ</button>
  </nav>
  <section class="dep-panel active" id="functionListPanel">
    <section class="dep-controls" aria-label="フィルター">
      <input id="search" type="search" placeholder="関数名またはファイル名で検索">
      <select id="levelFilter"><option value="">level すべて</option></select>
      <select id="classFilter"><option value="">分類すべて</option></select>
      <select id="exportFilter"><option value="">export すべて</option><option value="yes">export yes</option><option value="no">export no</option></select>
      <select id="staticFilter"><option value="">static すべて</option><option value="yes">static yes</option><option value="no">static no</option></select>
      <select id="areaFilter"><option value="">領域すべて</option></select>
      <select id="fileFilter"><option value="">ファイルすべて</option></select>
      <button type="button" id="clearFilters" class="dep-filter-clear">クリア</button>
    </section>
    <div class="dep-layout">
    <div class="dep-table-panel">
      <div class="dep-filter-notice" id="filterNotice">
        <span>現在のフィルターでは選択行は非表示です。</span>
        <button type="button" id="clearHiddenFunctionFilters" class="dep-filter-clear">クリア</button>
      </div>
      <div class="dep-table-wrap">
        <table>
          <thead>
            <tr>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-sort-key="level">level <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-sort-key="class">分類 <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-sort-key="export">export <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-sort-key="static">static <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-sort-key="area">領域 <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-sort-key="name">関数 <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-sort-key="file">ファイル <span class="dep-sort-mark"></span></button></th>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-sort-key="calleeCount">呼び出し先 <span class="dep-sort-mark"></span></button></th>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-sort-key="callerCount">呼び出し元 <span class="dep-sort-mark"></span></button></th>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-sort-key="crossFileCount">他ファイル <span class="dep-sort-mark"></span></button></th>
            </tr>
          </thead>
          <tbody id="functionRows"></tbody>
        </table>
      </div>
    </div>
    <aside class="dep-detail" id="detail">
      <p class="dep-empty">関数を選択してください。</p>
    </aside>
  </div>
  </section>
  <section class="dep-panel" id="fileListPanel">
    <section class="dep-controls dep-file-controls" aria-label="ファイル フィルター">
      <input id="fileSearch" type="search" placeholder="ファイル名または分類で検索">
      <select id="fileLevelFilter"><option value="">level すべて</option></select>
      <select id="fileClassFilter"><option value="">分類すべて</option></select>
      <select id="fileExportFilter"><option value="">export すべて</option><option value="yes">export yes</option><option value="no">export no</option></select>
      <select id="fileStaticFilter"><option value="">static すべて</option><option value="yes">static yes</option><option value="no">static no</option></select>
      <select id="fileAreaFilter"><option value="">領域すべて</option></select>
      <button type="button" id="clearFileFilters" class="dep-filter-clear">クリア</button>
    </section>
    <div class="dep-layout">
    <div class="dep-table-panel">
      <div class="dep-filter-notice" id="fileFilterNotice">
        <span>現在のフィルターでは選択行は非表示です。</span>
        <button type="button" id="clearHiddenFileFilters" class="dep-filter-clear">クリア</button>
      </div>
      <div class="dep-table-wrap">
        <table>
          <thead>
            <tr>
              <th><button type="button" class="dep-sort-button" data-file-sort-key="area">領域 <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-file-sort-key="path">ファイル <span class="dep-sort-mark"></span></button></th>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-file-sort-key="functionCount">関数 <span class="dep-sort-mark"></span></button></th>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-file-sort-key="exportCount">export <span class="dep-sort-mark"></span></button></th>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-file-sort-key="staticCount">static <span class="dep-sort-mark"></span></button></th>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-file-sort-key="edgeCount">呼び出し <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-file-sort-key="level">level <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-file-sort-key="class">分類 <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-file-sort-key="areas">領域内訳 <span class="dep-sort-mark"></span></button></th>
            </tr>
          </thead>
          <tbody id="fileRows"></tbody>
        </table>
      </div>
    </div>
    <aside class="dep-detail" id="fileDetail">
      <p class="dep-empty">ファイルを選択してください。</p>
    </aside>
  </div>
  </section>
  <section class="dep-panel" id="overviewPanel">
    <div class="dep-graph-layout">
      <div class="dep-graph-shell">
        <div class="dep-graph-toolbar">
          <button type="button" id="overviewFit">表示範囲にフィット</button>
          <button type="button" id="overviewRelayout">レイアウト再実行</button>
          <button type="button" id="overviewReset">初期化</button>
        </div>
        <div id="overviewGraph" class="dep-graph">
          <button type="button" id="overviewHiddenNotice" class="dep-graph-hidden-notice">非表示ファイルの再表示</button>
        </div>
        <div id="overviewGraphMenu" class="dep-graph-context-menu" role="menu" aria-label="マップ操作">
          <button type="button" role="menuitem" data-action="hide-file" data-menu-scope="node">このファイルを非表示</button>
          <!-- SVG 保存は要素数が多い場合に不安定なため、拡張用コードだけを残す。
          <button type="button" role="menuitem" data-svg-scope="full">マップ全体を SVG で保存</button>
          <button type="button" role="menuitem" data-svg-scope="viewport">表示範囲を SVG で保存</button>
          -->
          <div class="dep-graph-context-menu-label" data-menu-scope="background">呼び出し元関数</div>
          <button type="button" role="menuitemradio" class="dep-menu-option" data-menu-scope="background" data-caller-depth="0">非表示</button>
          <button type="button" role="menuitemradio" class="dep-menu-option" data-menu-scope="background" data-caller-depth="1">1 つ先</button>
          <button type="button" role="menuitemradio" class="dep-menu-option" data-menu-scope="background" data-caller-depth="all">すべて</button>
          <div class="dep-graph-context-menu-label" data-menu-scope="background">呼び出し先関数</div>
          <button type="button" role="menuitemradio" class="dep-menu-option" data-menu-scope="background" data-callee-depth="0">非表示</button>
          <button type="button" role="menuitemradio" class="dep-menu-option" data-menu-scope="background" data-callee-depth="1">1 つ先</button>
          <button type="button" role="menuitemradio" class="dep-menu-option" data-menu-scope="background" data-callee-depth="all">すべて</button>
          <div class="dep-graph-context-menu-separator" role="separator" aria-hidden="true" data-menu-scope="background"></div>
          <button type="button" role="menuitem" data-menu-scope="background" data-png-scope="full">マップ全体を PNG で保存</button>
          <button type="button" role="menuitem" data-menu-scope="background" data-png-scope="viewport">表示範囲を PNG で保存</button>
          <div class="dep-graph-context-menu-separator" role="separator" aria-hidden="true" data-menu-scope="background"></div>
          <button type="button" role="menuitem" data-menu-scope="background" data-action="fit">表示範囲にフィット</button>
          <button type="button" role="menuitem" data-menu-scope="background" data-action="relayout">レイアウト再実行</button>
          <button type="button" role="menuitem" data-menu-scope="background" data-action="reset">初期化</button>
        </div>
      </div>
      <aside class="dep-detail dep-graph-detail" id="overviewDetail">
        <p class="dep-empty">ファイルまたは関数を選択してください。</p>
      </aside>
    </div>
  </section>
</main>
<script>
(function () {{
  "use strict";
  // 表示はページ読み込み時の dependency-data.js を断面として固定する。
  const data = window.DoxyfwDependencyData || {{ summary: {{}}, functions: [], edges: [] }};
  const functions = data.functions || [];
  const edges = data.edges || [];
  const files = data.files || [];
  const sccs = data.sccs || [];
  const byId = new Map(functions.map((fn) => [fn.id, fn]));
  const baseOrder = new Map(functions.map((fn, index) => [fn.id, index]));
  const sccById = new Map(sccs.map((scc) => [scc.id, scc]));
  const fileByPath = new Map(files.map((file) => [file.path, file]));
  const functionsByFile = new Map();
  const callees = new Map();
  const callers = new Map();
  for (const fn of functions) {{
    if (!functionsByFile.has(fn.file)) functionsByFile.set(fn.file, []);
    functionsByFile.get(fn.file).push(fn);
  }}
  // edgesByFunctionId は全体マップの関数選択時に、全エッジの線形走査を避けて
  // 表示関数の近傍エッジだけを列挙するための隣接リスト (caller 側・callee 側の両方に登録)。
  const edgesByFunctionId = new Map();
  for (const edge of edges) {{
    if (!callees.has(edge.caller)) callees.set(edge.caller, []);
    if (!callers.has(edge.callee)) callers.set(edge.callee, []);
    callees.get(edge.caller).push(edge.callee);
    callers.get(edge.callee).push(edge.caller);
    if (!edgesByFunctionId.has(edge.caller)) edgesByFunctionId.set(edge.caller, []);
    if (!edgesByFunctionId.has(edge.callee)) edgesByFunctionId.set(edge.callee, []);
    edgesByFunctionId.get(edge.caller).push(edge);
    if (edge.callee !== edge.caller) edgesByFunctionId.get(edge.callee).push(edge);
  }}
  const fileEdges = (data.fileEdges && data.fileEdges.length > 0) ? data.fileEdges : buildFileEdges(edges);
  const fileEdgeByKey = new Map(fileEdges.map((edge) => [edge.id, {{ data: edge }}]));
  const edgePairsByFileKey = new Map();
  for (const edge of edges) {{
    if (edge.callerFile === edge.calleeFile) continue;
    const key = overviewEdgeKey(edge.callerFile, edge.calleeFile);
    if (!edgePairsByFileKey.has(key)) edgePairsByFileKey.set(key, []);
    edgePairsByFileKey.get(key).push(edge);
  }}
  for (const pairs of edgePairsByFileKey.values()) {{
    pairs.sort((a, b) => compareText(a.callerFile, b.callerFile) || compareText(a.caller, b.caller) || compareText(a.callee, b.callee));
  }}
  const OVERVIEW_SYNC_CHUNK_SIZE = 100;
  // processOverviewChunks の 1 フレームあたりの処理時間予算 (ms)。
  const OVERVIEW_CHUNK_FRAME_BUDGET_MS = 8;
  // 位置アニメーションの時間。
  const OVERVIEW_ANIMATION_MS = 430;
  // 状態クラス (ミュート等) のフェードの時間。
  const OVERVIEW_FADE_MS = 215;

  const summary = document.getElementById("summary");
  const rows = document.getElementById("functionRows");
  const fileRows = document.getElementById("fileRows");
  const detail = document.getElementById("detail");
  const fileDetail = document.getElementById("fileDetail");
  const search = document.getElementById("search");
  const levelFilter = document.getElementById("levelFilter");
  const classFilter = document.getElementById("classFilter");
  const exportFilter = document.getElementById("exportFilter");
  const staticFilter = document.getElementById("staticFilter");
  const areaFilter = document.getElementById("areaFilter");
  const fileFilter = document.getElementById("fileFilter");
  const filterNotice = document.getElementById("filterNotice");
  const clearFilters = document.getElementById("clearFilters");
  const clearHiddenFunctionFilters = document.getElementById("clearHiddenFunctionFilters");
  const fileSearch = document.getElementById("fileSearch");
  const fileLevelFilter = document.getElementById("fileLevelFilter");
  const fileClassFilter = document.getElementById("fileClassFilter");
  const fileExportFilter = document.getElementById("fileExportFilter");
  const fileStaticFilter = document.getElementById("fileStaticFilter");
  const fileAreaFilter = document.getElementById("fileAreaFilter");
  const fileFilterNotice = document.getElementById("fileFilterNotice");
  const clearFileFilters = document.getElementById("clearFileFilters");
  const clearHiddenFileFilters = document.getElementById("clearHiddenFileFilters");
  const sortButtons = Array.from(document.querySelectorAll("[data-sort-key]"));
  const fileSortButtons = Array.from(document.querySelectorAll("[data-file-sort-key]"));
  const tabButtons = Array.from(document.querySelectorAll("[data-tab-target]"));
  const tabPanels = Array.from(document.querySelectorAll(".dep-panel"));
  const overviewGraph = document.getElementById("overviewGraph");
  const overviewGraphShell = overviewGraph ? overviewGraph.closest(".dep-graph-shell") : null;
  const overviewDetail = document.getElementById("overviewDetail");
  const overviewFit = document.getElementById("overviewFit");
  const overviewRelayout = document.getElementById("overviewRelayout");
  const overviewReset = document.getElementById("overviewReset");
  const overviewGraphMenu = document.getElementById("overviewGraphMenu");
  const overviewHiddenNotice = document.getElementById("overviewHiddenNotice");
  const themeToggle = document.getElementById("themeToggle");
  const reportCategory = {js_category};
  const themeStorageKey = "doxyfw-dependency-theme";
  let selectedId = "";
  let selectedFilePath = "";
  let selectedEdgeKey = "";
  let sortState = {{ key: "level", direction: "asc" }};
  let fileSortState = {{ key: "path", direction: "asc" }};
  let activeTab = "functionListPanel";
  let currentTheme = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  let overviewCy = null;
  let overviewLayoutInitialized = false;
  let overviewPositionAnimation = null;
  let overviewActiveLayout = null;
  let overviewLayoutRunning = false;
  let overviewLayoutToken = 0;
  let overviewSyncToken = 0;
  // cola (Phase B) の実起動回数。テスト専用フックが Phase B のスキップを確定的に
  // 検証するために参照する (通常描画では未使用)。
  let overviewLayoutRunCount = 0;
  // 直近レイアウトが cola へ投入したノード数と、その純計算時間 (ms)。テスト専用フックが
  // 部分コレクション化の効果 (投入ノード数の削減・時間短縮) を測るために参照する。
  let overviewLastLayoutNodeCount = 0;
  let overviewLastLayoutDurationMs = 0;
  let overviewRelayoutRevealToken = 0;
  let overviewRenderedSelectionSignature = null;
  let overviewPendingSelectionSignature = null;
  // 画面に「状態クラス (強調・ミュート) が適用済み」の選択署名。rendered は Phase B/C の
  // 完了まで更新されず、pending は適用前から目標を指すため、状態クラスの遷移判定
  // (deferStateClassChanges / clearingSelection) の「直前状態」にはどちらも使えない。
  // Phase A (非遅延時) と Phase C (遅延クラス適用後) で更新する。
  let overviewVisualStateSignature = null;
  // 全体マップの背景右クリックメニューで切り替える、呼び出し元/先の表示深さ。
  // 0 = 非表示、1 = 1 つ先 (既定)、Infinity = すべて。URL・永続化は行わないページ内一時設定。
  let overviewCallerDepth = 1;
  let overviewCalleeDepth = 1;
  // 全体マップで「非表示」にしたファイル。UI 用語は非表示だが実体はノード・エッジを
  // 削除し描画を軽くする。値は非表示時のファイル ノード位置 (復活時の元位置復元用)。
  let hiddenOverviewFiles = new Map();
  // 復活させるファイルへ、次の sync で与える元位置を一時的に保持する。
  let overviewRestorePositions = new Map();
  // 操作割り込みで中止されたレイアウトの移動対象 (seed のままになった関数ノード id) を一時的に
  // 保持する。中止 (stopOverviewActiveLayout) 時に記録し、次の sync で movingNodeIds へ再投入して
  // Phase B をやり直す。自然完了したレイアウトは記録しないため、grab によるアニメーション中断など
  // 中止を伴わないケースには影響しない。再投入した sync で消費・クリアする。
  let overviewPendingRelayoutNodeIds = new Set();
  // 右クリック対象のファイル ノード (メニューの「このファイルを非表示」で使う)。
  let overviewMenuTargetFile = "";
  let overviewLayoutWatchdog = null;
  let overviewInteractionStateBeforeLayout = null;
  let overviewDraggingNodeIds = new Set();
  let overviewUserMovedNodePositions = new Map();
  let overviewFunctionGrabInterruptedLayout = false;
  let overviewDeferredPositionAnimation = null;
  let overviewDragRevision = 0;
  let overviewSyncAfterDrag = false;
  let overviewLastClassUpdatePlan = null;
  let overviewSuppressBackgroundTapUntil = 0;
  let previousSelectedRowVisible = false;
  let previousSelectedFileRowVisible = false;
  let pendingFunctionListScroll = false;
  let pendingFileListScroll = false;

  function text(value) {{
    return value === null || value === undefined ? "" : String(value);
  }}

  function escapeHtml(value) {{
    return text(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }}

  function escapeXml(value) {{
    return text(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }}

  function safeFileNamePart(value) {{
    const normalized = text(value).trim().replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
    return normalized || "doxygen";
  }}

  function cssVar(name) {{
    return window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }}

  // #rgb / #rrggbb の前景色を背景色と alpha で混色し、不透明な #rrggbb を返す。
  // エッジを opacity 1 で描いても、アルファ 0.7 で重ねたのと同じ見た目にするために使う。
  // Cytoscape は opacity<1 の矢印を destination-out で切り抜くため、塊が不透明に浮く。
  // see: https://github.com/cytoscape/cytoscape.js/blob/master/src/extensions/renderer/canvas/drawing-edges.js
  function blendColor(fg, bg, alpha) {{
    const toRgb = (value) => {{
      if (typeof value !== "string") return null;
      let hex = value.trim().replace(/^#/, "");
      if (/^[0-9a-fA-F]{{3}}$/.test(hex)) hex = hex.replace(/(.)/g, "$1$1");
      if (!/^[0-9a-fA-F]{{6}}$/.test(hex)) return null;
      return [parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16)];
    }};
    const f = toRgb(fg);
    const b = toRgb(bg);
    if (!f || !b) return fg;
    const mix = f.map((c, i) => Math.max(0, Math.min(255, Math.round(alpha * c + (1 - alpha) * b[i]))));
    return "#" + mix.map((c) => c.toString(16).padStart(2, "0")).join("");
  }}

  function updateThemeToggle() {{
    if (!themeToggle) return;
    const isDark = currentTheme === "dark";
    themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
    themeToggle.textContent = isDark ? "ダーク" : "ライト";
    themeToggle.title = isDark ? "ライト モードに切り替え" : "ダーク モードに切り替え";
  }}

  function saveTheme(theme) {{
    try {{
      if (window.localStorage) window.localStorage.setItem(themeStorageKey, theme);
    }} catch (err) {{
      // 保存できない環境では、このページ内の切り替えだけ反映する。
    }}
  }}

  function applyTheme(theme, persist) {{
    currentTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", currentTheme);
    if (persist) saveTheme(currentTheme);
    updateThemeToggle();
    refreshOverviewGraphStyle();
  }}

  function graphColors() {{
    // エッジは opacity 1 で描くため、アルファ 0.7 で重ねた見た目を背景との混色で再現する。
    const graphBackground = cssVar("--dep-graph-bg") || "#ffffff";
    const flatEdge = (name, fallback) => blendColor(cssVar(name) || fallback, graphBackground, 0.7);
    return {{
      background: graphBackground,
      labelBackground: cssVar("--dep-graph-label-bg") || "#ffffff",
      text: cssVar("--dep-graph-text") || "#111827",
      parentText: cssVar("--dep-graph-parent-text") || "#1f2937",
      nodeBackground: cssVar("--dep-graph-node-bg") || "#dbeafe",
      nodeBorder: cssVar("--dep-graph-node-border") || "#2563eb",
      fileBackground: cssVar("--dep-graph-file-bg") || "#f8fafc",
      fileBorder: cssVar("--dep-graph-file-border") || "#64748b",
      mutedFileBackground: cssVar("--dep-graph-muted-file-bg") || "#f8fafc",
      mutedFileBorder: cssVar("--dep-graph-muted-file-border") || "#dbe4f0",
      mutedFileText: cssVar("--dep-graph-muted-file-text") || "#a8b4c3",
      parentBackground: cssVar("--dep-graph-parent-bg") || "#f1f5f9",
      edge: flatEdge("--dep-graph-edge", "#64748b"),
      mutedEdge: flatEdge("--dep-graph-muted-edge", "#e2e8f0"),
      activeEdge: flatEdge("--dep-graph-active-edge", "#334155"),
      emphasisEdge: flatEdge("--dep-graph-emphasis-edge", "#111827"),
      leafBackground: cssVar("--dep-graph-leaf-bg") || "#dcfce7",
      leafBorder: cssVar("--dep-graph-leaf-border") || "#16a34a",
      localBackground: cssVar("--dep-graph-local-bg") || "#e0f2fe",
      localBorder: cssVar("--dep-graph-local-border") || "#0284c7",
      callerBackground: cssVar("--dep-graph-caller-bg") || "#fef3c7",
      callerBorder: cssVar("--dep-graph-caller-border") || "#d97706",
      dangerBackground: cssVar("--dep-graph-danger-bg") || "#fee2e2",
      dangerBorder: cssVar("--dep-graph-danger-border") || "#dc2626",
      libraryBackground: cssVar("--dep-graph-library-bg") || "#eef2ff",
      libraryBorder: cssVar("--dep-graph-library-border") || "#4f46e5",
      mutedLibraryBackground: cssVar("--dep-graph-muted-library-bg") || "#f7f9ff",
      mutedLibraryBorder: cssVar("--dep-graph-muted-library-border") || "#d5ddff",
      sourceBackground: cssVar("--dep-graph-source-bg") || "#f3e8ff",
      sourceBorder: cssVar("--dep-graph-source-border") || "#9333ea",
      mutedSourceBackground: cssVar("--dep-graph-muted-source-bg") || "#fbf5ff",
      mutedSourceBorder: cssVar("--dep-graph-muted-source-border") || "#eadcff"
    }};
  }}

  function levelText(fn) {{
    return fn.dependencyLevel === null || fn.dependencyLevel === undefined ? "cycle" : String(fn.dependencyLevel);
  }}

  function levelSortValue(fn) {{
    if (fn.dependencyLevel === null || fn.dependencyLevel === undefined) return Number.POSITIVE_INFINITY;
    return Number(fn.dependencyLevel);
  }}

  function mapKeys(value) {{
    if (!value || typeof value !== "object") return [];
    return Object.keys(value).sort((a, b) => compareText(a, b));
  }}

  function countMapText(value) {{
    return mapKeys(value).map((key) => key + ": " + value[key]).join(", ");
  }}

  function fileLevelText(file) {{
    const keys = mapKeys(file.levels);
    return keys.length === 0 ? "" : keys.join(", ");
  }}

  function fileClassText(file) {{
    return countMapText(file.classes);
  }}

  function fileAreasText(file) {{
    return countMapText(file.areas);
  }}

  function fileLevelSortValue(file) {{
    let best = Number.POSITIVE_INFINITY;
    for (const key of mapKeys(file.levels)) {{
      const value = key === "cycle" ? Number.POSITIVE_INFINITY : Number(key);
      if (Number.isFinite(value)) best = Math.min(best, value);
    }}
    return best;
  }}

  function dominantFileClass(file) {{
    const classes = file.classes || {{}};
    const keys = mapKeys(classes);
    if (keys.length === 0) return "";
    return keys.sort((a, b) => Number(classes[b] || 0) - Number(classes[a] || 0) || compareText(a, b))[0];
  }}

  function compareText(a, b) {{
    return text(a).localeCompare(text(b), "ja");
  }}

  function compareNumbers(a, b) {{
    return Number(a || 0) - Number(b || 0);
  }}

  function compareByKey(a, b, key) {{
    if (key === "level") return levelSortValue(a) - levelSortValue(b);
    if (key === "class") return compareText(a.dependencyClass, b.dependencyClass);
    if (key === "export") return Number(a.isExported) - Number(b.isExported);
    if (key === "static") return Number(a.isStatic) - Number(b.isStatic);
    if (key === "area") return compareText(a.sourceArea, b.sourceArea);
    if (key === "name") return compareText(a.name, b.name);
    if (key === "file") return compareText(a.file, b.file);
    if (key === "calleeCount") return compareNumbers(a.inScopeCalleeCount, b.inScopeCalleeCount);
    if (key === "callerCount") return compareNumbers(a.inScopeCallerCount, b.inScopeCallerCount);
    if (key === "crossFileCount") return compareNumbers(a.crossFileCalleeCount, b.crossFileCalleeCount);
    return 0;
  }}

  function compareFileByKey(a, b, key) {{
    if (key === "area") return compareText(a.dominantArea, b.dominantArea);
    if (key === "path") return compareText(a.path, b.path);
    if (key === "functionCount") return compareNumbers(a.functionCount, b.functionCount);
    if (key === "exportCount") return compareNumbers(a.exportCount, b.exportCount);
    if (key === "staticCount") return compareNumbers(a.staticCount, b.staticCount);
    if (key === "edgeCount") return compareNumbers(a.edgeCount, b.edgeCount);
    if (key === "level") return fileLevelSortValue(a) - fileLevelSortValue(b);
    if (key === "class") return compareText(dominantFileClass(a), dominantFileClass(b));
    if (key === "areas") return compareText(fileAreasText(a), fileAreasText(b));
    return 0;
  }}

  function compareBaseOrder(a, b) {{
    return (baseOrder.get(a.id) || 0) - (baseOrder.get(b.id) || 0);
  }}

  function sortedFunctions(items) {{
    return items.slice().sort((a, b) => {{
      let result = compareByKey(a, b, sortState.key);
      if (sortState.direction === "desc") result = -result;
      if (result !== 0) return result;
      return compareBaseOrder(a, b);
    }});
  }}

  function sortedFiles(items) {{
    return items.slice().sort((a, b) => {{
      let result = compareFileByKey(a, b, fileSortState.key);
      if (fileSortState.direction === "desc") result = -result;
      if (result !== 0) return result;
      return compareText(a.path, b.path);
    }});
  }}

  function renderSortMarks() {{
    for (const button of sortButtons) {{
      const mark = button.querySelector(".dep-sort-mark");
      if (!mark) continue;
      if (button.getAttribute("data-sort-key") === sortState.key) {{
        mark.textContent = sortState.direction === "asc" ? "▲" : "▼";
      }} else {{
        mark.textContent = "";
      }}
    }}
  }}

  function renderFileSortMarks() {{
    for (const button of fileSortButtons) {{
      const mark = button.querySelector(".dep-sort-mark");
      if (!mark) continue;
      if (button.getAttribute("data-file-sort-key") === fileSortState.key) {{
        mark.textContent = fileSortState.direction === "asc" ? "▲" : "▼";
      }} else {{
        mark.textContent = "";
      }}
    }}
  }}

  function activateTab(tabId) {{
    const previousTab = activeTab;
    const immediateOverviewUpdate = tabId === "overviewPanel" && activeTab !== "overviewPanel";
    activeTab = tabId;
    for (const item of tabButtons) {{
      item.classList.toggle("active", item.getAttribute("data-tab-target") === activeTab);
    }}
    for (const panel of tabPanels) {{
      panel.classList.toggle("active", panel.id === activeTab);
    }}
    abortOverviewInitializationOnTabLeave(previousTab, activeTab);
    refreshActiveGraph({{ immediate: immediateOverviewUpdate }});
    if (activeTab === "functionListPanel" && pendingFunctionListScroll) {{
      syncSelectedRowScroll(true);
    }}
    if (activeTab === "fileListPanel" && pendingFileListScroll) {{
      syncSelectedFileRowScroll(true);
    }}
    updateUrlHashFromState();
  }}

  // タブと選択状態を URL ハッシュ (#tab=...&fn=... / &file=...) で共有できるようにする。
  // file:// の固定 URL でも機能するよう、クエリ文字列でなくハッシュ フラグメントを使う。
  const urlHashTabNames = {{
    functionListPanel: "functions",
    fileListPanel: "files",
    overviewPanel: "overview"
  }};
  const urlHashPanelIds = {{
    functions: "functionListPanel",
    files: "fileListPanel",
    overview: "overviewPanel"
  }};
  let applyingUrlHash = false;

  function currentUrlHashString() {{
    const params = ["tab=" + (urlHashTabNames[activeTab] || "functions")];
    if (selectedId) {{
      params.push("fn=" + encodeURIComponent(selectedId));
    }} else if (selectedFilePath) {{
      params.push("file=" + encodeURIComponent(selectedFilePath));
    }}
    return "#" + params.join("&");
  }}

  function updateUrlHashFromState() {{
    if (applyingUrlHash) return;
    const next = currentUrlHashString();
    if (window.location.hash === next) return;
    try {{
      // replaceState なら再読み込みも履歴の増加も起きない (file:// でも動作する)。
      window.history.replaceState(null, "", next);
    }} catch (err) {{
      window.location.hash = next.slice(1);
    }}
  }}

  function applyStateFromUrlHash() {{
    const rawHash = window.location.hash.replace(/^#/, "");
    if (!rawHash) return;
    let params = null;
    try {{
      params = new URLSearchParams(rawHash);
    }} catch (err) {{
      return;
    }}
    applyingUrlHash = true;
    try {{
      const fnId = params.get("fn") || "";
      const filePath = params.get("file") || "";
      if (fnId && byId.has(fnId)) {{
        selectFunction(fnId);
      }} else if (filePath && fileByPath.has(filePath)) {{
        selectFile(filePath);
      }}
      const panelId = urlHashPanelIds[params.get("tab") || ""] || "";
      if (panelId && panelId !== activeTab) activateTab(panelId);
    }} finally {{
      applyingUrlHash = false;
    }}
    // 不正値を取り除いた正規形へ書き戻す。
    updateUrlHashFromState();
  }}

  function addMetric(label, value) {{
    const item = document.createElement("div");
    item.className = "dep-metric";
    item.innerHTML = "<strong>" + escapeHtml(value) + "</strong><span>" + escapeHtml(label) + "</span>";
    summary.appendChild(item);
  }}

  function shortPath(path) {{
    const parts = text(path).split("/");
    return parts[parts.length - 1] || text(path);
  }}

  function graphClassFor(klass) {{
    if (klass === "cycle") return "dep-danger-node";
    if (klass === "leaf-static" || klass === "leaf-global") return "dep-leaf-node";
    if (klass === "file-local") return "dep-local-node";
    return "dep-caller-node";
  }}

  function graphFileClassFor(area) {{
    if (area === "include" || area === "include_internal" || area === "libsrc") return "dep-file-library-node";
    if (area === "src") return "dep-file-source-node";
    return "";
  }}

  function areaBadgeClass(area) {{
    if (area === "include" || area === "include_internal" || area === "libsrc") return "area-library";
    if (area === "src") return "area-source";
    return "";
  }}

  function areaBadge(area) {{
    const classes = ["badge"];
    const areaClass = areaBadgeClass(area);
    if (areaClass) classes.push(areaClass);
    return "<span class=\\"" + classes.map(escapeHtml).join(" ") + "\\">" + escapeHtml(area) + "</span>";
  }}

  function fileSelectionLink(filePath, label) {{
    return "<a href=\\"#\\" data-file-path=\\"" + escapeHtml(filePath) + "\\">" + escapeHtml(label || filePath) + "</a>";
  }}

  function overviewEdgeKey(fromFile, toFile) {{
    return text(fromFile) + "\\n" + text(toFile);
  }}

  function buildFileEdges(sourceEdges) {{
    const edgeMap = new Map();
    for (const edge of sourceEdges) {{
      if (edge.callerFile === edge.calleeFile) continue;
      const key = overviewEdgeKey(edge.callerFile, edge.calleeFile);
      const current = edgeMap.get(key) || {{
        id: key,
        source: edge.callerFile,
        target: edge.calleeFile,
        fromFile: edge.callerFile,
        toFile: edge.calleeFile,
        weight: 0,
        label: ""
      }};
      current.weight += 1;
      current.label = String(current.weight);
      edgeMap.set(key, current);
    }}
    return Array.from(edgeMap.values()).sort((a, b) => compareText(a.fromFile, b.fromFile) || compareText(a.toFile, b.toFile));
  }}

  function graphFunctionWeight(fn) {{
    const rank = Number(fn.dependencyRank);
    if (!Number.isFinite(rank)) return 10;
    return Math.max(2, Math.min(10, rank + 1));
  }}

  function graphStyle(opts) {{
    const colors = graphColors();
    // トランジションは「クラス変更後の計算済みスタイル」に定義がある場合のみ補間される。
    //   - ミュート クラスに定義 -> ミュート化 (非強調側) はフェード、ミュート解除
    //     (関連関数・親ファイルの強調復帰) は即時反映。
    //   - dep-overview-fade は選択解除 (選択中 -> 無選択) の Phase C でのみ一時付与され、
    //     ミュート解除を通常表示へフェードで戻す (フェード完了後にクラスを除去する)。
    //     スタイルシート差し替え (fromJson) はトランジションを伴わず適用されるため、
    //     ベース側への一時的な定義追加では補間が発火しない。クラス付与で行うこと。
    //   - fadeMode: "none" は duration 0 で完全即時。タブ切替 (suppressFade) やテーマ切替で
    //     色を即時確定するために使う。
    const fadeMode = (opts && opts.fadeMode) || "muted";
    const transitionMs = fadeMode === "none" ? "0ms" : OVERVIEW_FADE_MS + "ms";
    const baseNodeStyle = {{
      "label": "data(label)",
      "font-size": 11,
      "text-wrap": "wrap",
      "text-max-width": 120,
      "text-valign": "center",
      "text-halign": "center",
      "background-color": colors.nodeBackground,
      "border-color": colors.nodeBorder,
      "border-width": 1,
      "color": colors.text,
      "width": "mapData(weight, 1, 12, 42, 86)",
      "height": "mapData(weight, 1, 12, 42, 86)",
      "z-index": 1,
      "z-index-compare": "manual",
      "z-compound-depth": "bottom"
    }};
    const baseEdgeStyle = {{
      "curve-style": "bezier",
      "target-arrow-shape": "triangle",
      "target-arrow-color": colors.edge,
      "line-color": colors.edge,
      "opacity": 1,
      "width": "mapData(weight, 1, 8, 1, 5)",
      "label": "data(label)",
      "font-size": 10,
      "color": colors.edge,
      "text-background-color": colors.labelBackground,
      "text-background-opacity": 0.85,
      "text-background-padding": 2,
      "z-compound-depth": "bottom",
      "z-index-compare": "manual",
      "z-index": 0
    }};
    return [
      {{
        selector: "node",
        style: baseNodeStyle
      }},
      {{
        selector: "edge",
        style: baseEdgeStyle
      }},
      {{
        selector: "node.dep-overview-fade",
        style: {{
          "transition-property": "background-color, border-color, color",
          "transition-duration": transitionMs
        }}
      }},
      {{
        selector: "edge.dep-overview-fade",
        style: {{
          "transition-property": "line-color, target-arrow-color, color",
          "transition-duration": transitionMs
        }}
      }},
      {{
        selector: ".dep-leaf-node, .dep-local-node, .dep-caller-node, .dep-danger-node",
        style: {{
          "z-index": 4,
          "z-compound-depth": "top"
        }}
      }},
      {{ selector: ".dep-leaf-node", style: {{ "background-color": colors.leafBackground, "border-color": colors.leafBorder }} }},
      {{ selector: ".dep-local-node", style: {{ "background-color": colors.localBackground, "border-color": colors.localBorder }} }},
      {{ selector: ".dep-caller-node", style: {{ "background-color": colors.callerBackground, "border-color": colors.callerBorder }} }},
      {{ selector: ".dep-danger-node", style: {{ "background-color": colors.dangerBackground, "border-color": colors.dangerBorder }} }},
      {{ selector: ".dep-file-node", style: {{ "background-color": colors.fileBackground, "border-color": colors.fileBorder, "z-index": 1 }} }},
      {{ selector: ".dep-center-node", style: {{ "border-width": 2 }} }},
      {{ selector: ".dep-upstream-node", style: {{ "shape": "round-rectangle" }} }},
      {{ selector: ".dep-downstream-node", style: {{ "shape": "ellipse" }} }},
      {{ selector: ".dep-both-node", style: {{ "shape": "diamond" }} }},
      {{
        selector: "$node > node",
        style: {{
          "shape": "round-rectangle",
          "background-color": colors.parentBackground,
          "background-opacity": 0.5,
          "border-color": colors.fileBorder,
          "border-width": 1,
          "label": "data(label)",
          "text-valign": "top",
          "text-halign": "center",
          "text-margin-y": -2,
          "font-size": 12,
          "padding": 16,
          "color": colors.parentText,
          "z-index": 2,
          "z-compound-depth": "bottom"
        }}
      }},
      {{ selector: ".dep-file-library-node", style: {{ "background-color": colors.libraryBackground, "border-color": colors.libraryBorder }} }},
      {{ selector: ".dep-file-source-node", style: {{ "background-color": colors.sourceBackground, "border-color": colors.sourceBorder }} }},
      {{
        selector: ".dep-file-node-muted",
        style: {{
          "background-color": colors.mutedFileBackground,
          "border-color": colors.mutedFileBorder,
          "color": colors.mutedFileText,
          "transition-property": "background-color, border-color, color",
          "transition-duration": transitionMs,
          "z-index": -1
        }}
      }},
      {{
        selector: ".dep-file-node-muted.dep-file-library-node",
        style: {{
          "background-color": colors.mutedLibraryBackground,
          "border-color": colors.mutedLibraryBorder
        }}
      }},
      {{
        selector: ".dep-file-node-muted.dep-file-source-node",
        style: {{
          "background-color": colors.mutedSourceBackground,
          "border-color": colors.mutedSourceBorder
        }}
      }},
      {{
        selector: ".dep-base-edge-muted",
        style: {{
          "line-color": colors.mutedEdge,
          "target-arrow-color": colors.mutedEdge,
          "color": colors.mutedEdge,
          "transition-property": "line-color, target-arrow-color, color",
          "transition-duration": transitionMs,
          "z-index": -2
        }}
      }},
      {{
        selector: ".dep-emphasis-edge",
        style: {{
          "line-color": colors.emphasisEdge,
          "target-arrow-color": colors.emphasisEdge,
          "color": colors.emphasisEdge,
          "z-index": 2
        }}
      }},
      {{
        selector: ".dep-selected-edge",
        style: {{
          "line-color": colors.emphasisEdge,
          "target-arrow-color": colors.emphasisEdge,
          "color": colors.emphasisEdge,
          "z-index": 2
        }}
      }},
      {{
        selector: ".dep-function-edge",
        style: {{
          "line-color": colors.emphasisEdge,
          "target-arrow-color": colors.emphasisEdge,
          "color": colors.emphasisEdge,
          "z-compound-depth": "top",
          "z-index": 3
        }}
      }},
      {{
        selector: ".dep-pull-edge",
        style: {{
          "opacity": 0,
          "events": "no",
          "width": 1,
          "target-arrow-shape": "none",
          "curve-style": "straight"
        }}
      }},
      {{
        selector: ".dep-selected-file",
        style: {{
          "border-width": 2
        }}
      }},
      {{ selector: ":selected", style: {{ "border-width": 2 }} }}
    ];
  }}

  function graphUnavailable(container, detailElement) {{
    container.innerHTML = "<p class=\\"dep-empty\\">Cytoscape.js を読み込めませんでした。</p>";
    detailElement.innerHTML = "<p class=\\"dep-empty\\">グラフ ライブラリを確認してください。</p>";
  }}

  function refreshOverviewGraphStyle() {{
    if (!overviewCy) return;
    // テーマ切替は全色の差し替えであり、トランジションが効くと全要素が OVERVIEW_FADE_MS
    // フェードしてしまう。duration 0 のスタイルで色を即時確定してから、既定のスタイル
    // (fadeMode: "muted") を再適用する。2 回目の適用では色が変化しないため補間は走らない。
    applyOverviewFadeMode("none");
    applyOverviewFadeMode("muted");
  }}

  // 現在のスタイルシートを指定の fadeMode で適用し直す。色は変えないため、モード切替
  // 自体で補間は走らない (トランジション定義の有無だけが変わる)。
  function applyOverviewFadeMode(mode) {{
    if (!overviewCy) return;
    const styleJson = graphStyle({{ fadeMode: mode }});
    const style = overviewCy.style();
    if (style && typeof style.fromJson === "function") {{
      style.fromJson(styleJson).update();
      return;
    }}
    if (typeof overviewCy.style === "function") {{
      overviewCy.style(styleJson);
    }}
  }}

  // 選択解除時に付与した dep-overview-fade をフェード完了後に除去するタイマー (常に 1 本のみ)。
  // クラスは transition 定義のみで色を持たないため、除去しても見た目は変わらない。
  let overviewFadeClassCleanupTimer = null;

  function scheduleOverviewFadeClassCleanup() {{
    if (overviewFadeClassCleanupTimer !== null) window.clearTimeout(overviewFadeClassCleanupTimer);
    overviewFadeClassCleanupTimer = window.setTimeout(() => {{
      overviewFadeClassCleanupTimer = null;
      if (!overviewCy) return;
      overviewCy.elements(".dep-overview-fade").removeClass("dep-overview-fade");
    }}, OVERVIEW_FADE_MS + 60);
  }}

  function hideOverviewGraphMenu() {{
    if (!overviewGraphMenu) return;
    overviewGraphMenu.classList.remove("visible");
  }}

  function overviewDepthAttrValue(depth) {{
    if (depth === Infinity) return "all";
    return String(depth);
  }}

  function updateOverviewDepthMenuChecks() {{
    if (!overviewGraphMenu) return;
    const callerValue = overviewDepthAttrValue(overviewCallerDepth);
    const calleeValue = overviewDepthAttrValue(overviewCalleeDepth);
    for (const item of overviewGraphMenu.querySelectorAll("[data-caller-depth]")) {{
      item.classList.toggle("checked", item.getAttribute("data-caller-depth") === callerValue);
    }}
    for (const item of overviewGraphMenu.querySelectorAll("[data-callee-depth]")) {{
      item.classList.toggle("checked", item.getAttribute("data-callee-depth") === calleeValue);
    }}
  }}

  function applyOverviewGraphMenuScope(scope) {{
    if (!overviewGraphMenu) return;
    // 各項目は data-menu-scope を持つ。背景の右クリックでは background、ファイル ノードの
    // 右クリックでは node の項目だけ表示する。未指定の項目は常に表示する。
    for (const item of overviewGraphMenu.querySelectorAll("[data-menu-scope]")) {{
      const itemScope = item.getAttribute("data-menu-scope");
      item.style.display = !itemScope || itemScope === scope ? "" : "none";
    }}
    updateOverviewDepthMenuChecks();
  }}

  function showOverviewGraphMenu(clientX, clientY, scope) {{
    if (!overviewGraphMenu) return;
    applyOverviewGraphMenuScope(scope || "background");
    const margin = 8;
    overviewGraphMenu.classList.add("visible");
    overviewGraphMenu.style.left = "0px";
    overviewGraphMenu.style.top = "0px";
    const rect = overviewGraphMenu.getBoundingClientRect();
    const left = Math.min(Math.max(margin, clientX), Math.max(margin, window.innerWidth - rect.width - margin));
    const top = Math.min(Math.max(margin, clientY), Math.max(margin, window.innerHeight - rect.height - margin));
    overviewGraphMenu.style.left = left + "px";
    overviewGraphMenu.style.top = top + "px";
  }}

  function updateOverviewHiddenNotice() {{
    if (!overviewHiddenNotice) return;
    overviewHiddenNotice.classList.toggle("visible", hiddenOverviewFiles.size > 0);
  }}

  function hideOverviewFile(filePath) {{
    if (!filePath || hiddenOverviewFiles.has(filePath)) return;
    // レイアウト計算中 (seed の窓内) の非表示は、実行中レイアウトを中止して操作を反映した上で、
    // 取り残された seed 関数を再レイアウトする。定常状態の通常非表示では再 sync せず、不要な
    // 再レイアウトとちらつきを避ける。
    const resyncForInterrupt = Boolean(overviewActiveLayout ||
      (overviewPositionAnimation && overviewPositionAnimation.active));
    let savedPosition = null;
    if (overviewCy) {{
      const node = overviewCy.getElementById(filePath);
      if (node && node.length) {{
        const position = node.position();
        savedPosition = {{ x: position.x, y: position.y }};
        // UI 用語は「非表示」だが、描画を軽くするため実体を削除する。compound 子の
        // 関数ノードと接続エッジは Cytoscape が連動して削除する。割り込み時はここで削除せず、
        // 再 sync の stale 削除に委ねる (layoutNeeded が立ち、中止された関数が Phase B へ再投入される)。
        if (!resyncForInterrupt) {{
          overviewCy.batch(() => {{
            node.remove();
          }});
        }}
      }}
    }}
    hiddenOverviewFiles.set(filePath, savedPosition);
    updateOverviewHiddenNotice();
    if (resyncForInterrupt) forceRenderOverviewGraph();
  }}

  // 非表示ファイルをすべて元の位置に再表示する。選択状態や詳細ペインは変えない。
  function revealAllOverviewFiles() {{
    if (hiddenOverviewFiles.size === 0) return;
    for (const [path, position] of hiddenOverviewFiles) {{
      if (position) overviewRestorePositions.set(path, position);
    }}
    hiddenOverviewFiles.clear();
    updateOverviewHiddenNotice();
    forceRenderOverviewGraph();
  }}

  function suppressOverviewBackgroundTap() {{
    const now = window.performance && typeof window.performance.now === "function" ? window.performance.now() : Date.now();
    overviewSuppressBackgroundTapUntil = now + 500;
  }}

  function isOverviewBackgroundTapSuppressed() {{
    const now = window.performance && typeof window.performance.now === "function" ? window.performance.now() : Date.now();
    return now <= overviewSuppressBackgroundTapUntil;
  }}

  function overviewFitElements() {{
    if (!overviewCy) return undefined;
    return overviewCy.elements(":visible").not(".dep-pull-edge");
  }}

  function fitOverviewGraph() {{
    if (overviewCy) overviewCy.fit(overviewFitElements(), 30);
  }}

  function overviewViewport() {{
    if (!overviewCy) return null;
    const pan = overviewCy.pan();
    return {{
      zoom: overviewCy.zoom(),
      pan: {{ x: pan.x, y: pan.y }}
    }};
  }}

  function restoreOverviewViewport(viewport) {{
    if (!overviewCy || !viewport) return;
    overviewCy.zoom(viewport.zoom);
    overviewCy.pan(viewport.pan);
  }}

  function requestOverviewFrame(callback) {{
    const requestFrame = window.requestAnimationFrame || window.webkitRequestAnimationFrame || ((fn) => window.setTimeout(() => fn(Date.now()), 16));
    requestFrame(callback);
  }}

  function scheduleOverviewRelayoutReveal(opts) {{
    const viewport = opts && opts.viewport ? opts.viewport : null;
    const revealToken = ++overviewRelayoutRevealToken;
    const waitUntilReady = () => {{
      if (revealToken !== overviewRelayoutRevealToken) return;
      if (activeTab === "overviewPanel" && !isOverviewRenderedSelectionCurrent()) {{
        requestOverviewFrame(waitUntilReady);
        return;
      }}
      restoreOverviewViewport(viewport);
      requestOverviewFrame(() => {{
        requestOverviewFrame(() => {{
          if (revealToken !== overviewRelayoutRevealToken) return;
          if (activeTab === "overviewPanel" && !isOverviewRenderedSelectionCurrent()) {{
            waitUntilReady();
            return;
          }}
          if (overviewGraph) overviewGraph.classList.remove("layout-relayouting");
          setOverviewControlsInert(false);
        }});
      }});
    }};
    waitUntilReady();
  }}

  function setOverviewControlsInert(inert) {{
    if (overviewGraphShell) overviewGraphShell.classList.toggle("controls-inert", inert);
  }}

  function setOverviewGraphInteractionLocked(locked) {{
    if (!overviewCy) return;
    if (locked) {{
      if (overviewInteractionStateBeforeLayout !== null) return;
      overviewInteractionStateBeforeLayout = {{
        panningEnabled: overviewCy.panningEnabled(),
        zoomingEnabled: overviewCy.zoomingEnabled(),
        autoungrabify: overviewCy.autoungrabify(),
        boxSelectionEnabled: overviewCy.boxSelectionEnabled()
      }};
      overviewCy.panningEnabled(false);
      overviewCy.zoomingEnabled(false);
      overviewCy.autoungrabify(true);
      overviewCy.boxSelectionEnabled(false);
      return;
    }}
    if (overviewInteractionStateBeforeLayout === null) return;
    overviewCy.panningEnabled(overviewInteractionStateBeforeLayout.panningEnabled);
    overviewCy.zoomingEnabled(overviewInteractionStateBeforeLayout.zoomingEnabled);
    overviewCy.autoungrabify(overviewInteractionStateBeforeLayout.autoungrabify);
    overviewCy.boxSelectionEnabled(overviewInteractionStateBeforeLayout.boxSelectionEnabled);
    overviewInteractionStateBeforeLayout = null;
  }}

  function setOverviewLayoutRunning(running) {{
    overviewLayoutRunning = running;
    setOverviewControlsInert(running);
    setOverviewGraphInteractionLocked(running);
    if (!running && overviewGraph) overviewGraph.classList.remove("layout-relayouting");
    if (!running && overviewLayoutWatchdog !== null) {{
      window.clearTimeout(overviewLayoutWatchdog);
      overviewLayoutWatchdog = null;
    }}
  }}

  function relayoutOverviewGraph() {{
    if (!overviewCy || overviewLayoutRunning) return;
    const layoutToken = ++overviewLayoutToken;
    setOverviewLayoutRunning(true);
    requestOverviewFrame(() => {{
      requestOverviewFrame(() => {{
        if (!overviewCy || layoutToken !== overviewLayoutToken) {{
          setOverviewLayoutRunning(false);
          return;
        }}
        overviewLayoutWatchdog = window.setTimeout(() => {{
          if (layoutToken === overviewLayoutToken) setOverviewLayoutRunning(false);
        }}, 8000);
        runOverviewLayout({{
          manual: true,
          layoutToken: layoutToken,
          onComplete: () => {{
            if (layoutToken === overviewLayoutToken) setOverviewLayoutRunning(false);
          }}
        }});
      }});
    }});
  }}

  function resetOverviewGraphState() {{
    overviewCallerDepth = 1;
    overviewCalleeDepth = 1;
    clearSelection();
  }}

  function parseOverviewDepthValue(value) {{
    if (value === "all") return Infinity;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 1;
  }}

  // 呼び出し元/先の表示深さを変更する。関数選択中はマップへ即時反映する。
  function setOverviewDepth(kind, value) {{
    const depth = parseOverviewDepthValue(value);
    const changed = kind === "caller" ? depth !== overviewCallerDepth : depth !== overviewCalleeDepth;
    if (kind === "caller") overviewCallerDepth = depth; else overviewCalleeDepth = depth;
    if (!changed) return;
    if (selectedId && activeTab === "overviewPanel") forceRenderOverviewGraph();
  }}

  function handleOverviewGraphMenuAction(action) {{
    if (action === "fit") {{
      fitOverviewGraph();
      return true;
    }}
    if (action === "relayout") {{
      relayoutOverviewGraph();
      return true;
    }}
    if (action === "reset") {{
      resetOverviewGraphState();
      return true;
    }}
    if (action === "hide-file") {{
      if (overviewMenuTargetFile) hideOverviewFile(overviewMenuTargetFile);
      return true;
    }}
    return false;
  }}

  function downloadTextFile(fileName, textContent, mimeType) {{
    const url = URL.createObjectURL(new Blob([textContent], {{ type: mimeType }}));
    const tmp = document.createElement("a");
    tmp.href = url;
    tmp.setAttribute("download", fileName);
    document.body.appendChild(tmp);
    tmp.click();
    document.body.removeChild(tmp);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }}

  function graphStyleValue(element, name, fallback) {{
    const value = element.style(name);
    if (value === null || value === undefined || value === "") return fallback;
    return value;
  }}

  function graphStyleNumber(element, name, fallback) {{
    const value = Number(graphStyleValue(element, name, fallback));
    if (Number.isFinite(value)) return value;
    return fallback;
  }}

  function svgPoint(element, scope) {{
    if (scope === "viewport") return element.renderedPosition();
    return element.position();
  }}

  function svgBox(element, scope) {{
    const box = scope === "viewport"
      ? element.renderedBoundingBox({{ includeLabels: true, includeOverlays: false }})
      : element.boundingBox({{ includeLabels: true, includeOverlays: false }});
    return {{
      x1: box.x1,
      y1: box.y1,
      x2: box.x2,
      y2: box.y2,
      w: Math.max(1, box.w),
      h: Math.max(1, box.h)
    }};
  }}

  function svgElementBounds(scope) {{
    if (!overviewCy || overviewCy.elements().length === 0) {{
      return {{ x1: 0, y1: 0, x2: overviewGraph.clientWidth, y2: overviewGraph.clientHeight }};
    }}
    if (scope === "viewport") {{
      return {{ x1: 0, y1: 0, x2: overviewCy.width(), y2: overviewCy.height() }};
    }}
    const box = overviewCy.elements(":visible").not(".dep-pull-edge").boundingBox({{ includeLabels: true, includeOverlays: false }});
    const padding = 40;
    return {{
      x1: box.x1 - padding,
      y1: box.y1 - padding,
      x2: box.x2 + padding,
      y2: box.y2 + padding
    }};
  }}

  function svgShapeForNode(node, point, width, height, fill, stroke, strokeWidth) {{
    const shape = graphStyleValue(node, "shape", "ellipse");
    const attrs = " fill=\\"" + escapeXml(fill) + "\\" stroke=\\"" + escapeXml(stroke) + "\\" stroke-width=\\"" + escapeXml(strokeWidth) + "\\"";
    if (shape === "diamond") {{
      const x = point.x;
      const y = point.y;
      const hw = width / 2;
      const hh = height / 2;
      return "<polygon points=\\"" + [x, y - hh, x + hw, y, x, y + hh, x - hw, y].map((value) => Number(value).toFixed(2)).join(" ") + "\\"" + attrs + "/>";
    }}
    if (shape === "round-rectangle" || shape === "roundrectangle" || node.isParent()) {{
      const x = point.x - width / 2;
      const y = point.y - height / 2;
      return "<rect x=\\"" + x.toFixed(2) + "\\" y=\\"" + y.toFixed(2) + "\\" width=\\"" + width.toFixed(2) + "\\" height=\\"" + height.toFixed(2) + "\\" rx=\\"10\\" ry=\\"10\\"" + attrs + "/>";
    }}
    return "<ellipse cx=\\"" + point.x.toFixed(2) + "\\" cy=\\"" + point.y.toFixed(2) + "\\" rx=\\"" + (width / 2).toFixed(2) + "\\" ry=\\"" + (height / 2).toFixed(2) + "\\"" + attrs + "/>";
  }}

  function svgText(label, x, y, fontSize, color, anchor) {{
    if (!label) return "";
    return "<text x=\\"" + x.toFixed(2) + "\\" y=\\"" + y.toFixed(2) + "\\" text-anchor=\\"" + escapeXml(anchor || "middle") + "\\" dominant-baseline=\\"middle\\" font-family=\\"system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif\\" font-size=\\"" + escapeXml(fontSize) + "\\" fill=\\"" + escapeXml(color) + "\\">" + escapeXml(label) + "</text>";
  }}

  function svgArrow(start, end, size, fill, opacity) {{
    const angle = Math.atan2(end.y - start.y, end.x - start.x);
    const spread = Math.PI / 7;
    const p1 = {{
      x: end.x - Math.cos(angle - spread) * size,
      y: end.y - Math.sin(angle - spread) * size
    }};
    const p2 = {{
      x: end.x - Math.cos(angle + spread) * size,
      y: end.y - Math.sin(angle + spread) * size
    }};
    const points = [end.x, end.y, p1.x, p1.y, p2.x, p2.y].map((value) => Number(value).toFixed(2)).join(" ");
    return "<polygon points=\\"" + points + "\\" fill=\\"" + escapeXml(fill) + "\\" opacity=\\"" + escapeXml(opacity) + "\\"/>";
  }}

  function svgNode(node, scope) {{
    const point = svgPoint(node, scope);
    const box = svgBox(node, scope);
    const width = scope === "viewport" ? Math.max(1, node.renderedWidth()) : Math.max(1, node.width());
    const height = scope === "viewport" ? Math.max(1, node.renderedHeight()) : Math.max(1, node.height());
    const shapeWidth = node.isParent() ? box.w : width;
    const shapeHeight = node.isParent() ? box.h : height;
    const shapePoint = node.isParent() ? {{ x: (box.x1 + box.x2) / 2, y: (box.y1 + box.y2) / 2 }} : point;
    const fill = graphStyleValue(node, "background-color", "#ffffff");
    const stroke = graphStyleValue(node, "border-color", "#64748b");
    const strokeWidth = graphStyleNumber(node, "border-width", 1);
    const fontSize = graphStyleNumber(node, "font-size", node.isParent() ? 12 : 11);
    const color = graphStyleValue(node, "color", "#111827");
    const labelY = node.isParent() ? box.y1 + Math.max(14, fontSize - 2) : point.y;
    return svgShapeForNode(node, shapePoint, shapeWidth, shapeHeight, fill, stroke, strokeWidth) +
      svgText(node.data("label"), point.x, labelY, fontSize, color, "middle");
  }}

  function svgEdge(edge, scope) {{
    if (edge.hasClass("dep-pull-edge")) return "";
    const source = edge.source();
    const target = edge.target();
    if (!source.length || !target.length) return "";
    const start = svgPoint(source, scope);
    const end = svgPoint(target, scope);
    const stroke = graphStyleValue(edge, "line-color", "#94a3b8");
    const strokeWidth = Math.max(1, graphStyleNumber(edge, "width", 1));
    const opacity = graphStyleValue(edge, "opacity", "1");
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    const label = edge.data("label");
    const fontSize = graphStyleNumber(edge, "font-size", 10);
    const color = graphStyleValue(edge, "color", "#111827");
    return "<line x1=\\"" + start.x.toFixed(2) + "\\" y1=\\"" + start.y.toFixed(2) + "\\" x2=\\"" + end.x.toFixed(2) + "\\" y2=\\"" + end.y.toFixed(2) + "\\" stroke=\\"" + escapeXml(stroke) + "\\" stroke-width=\\"" + escapeXml(strokeWidth) + "\\" opacity=\\"" + escapeXml(opacity) + "\\"/>" +
      svgArrow(start, end, Math.max(7, strokeWidth + 6), stroke, opacity) +
      (label ? "<rect x=\\"" + (midX - 10).toFixed(2) + "\\" y=\\"" + (midY - 8).toFixed(2) + "\\" width=\\"20\\" height=\\"16\\" rx=\\"3\\" fill=\\"" + escapeXml(cssVar("--dep-graph-label-bg") || "#ffffff") + "\\" opacity=\\"0.85\\"/>" + svgText(label, midX, midY, fontSize, color, "middle") : "");
  }}

  function overviewSvgOrderedElements() {{
    if (!overviewCy) return [];
    const visibleEdges = overviewCy.edges(":visible");
    const visibleNodes = overviewCy.nodes(":visible");
    const mutedFileEdges = visibleEdges
      .filter((edge) => !edge.hasClass("dep-function-edge") && edge.hasClass("dep-base-edge-muted"))
      .toArray();
    const mutedFileNodes = visibleNodes
      .filter((node) => !node.isParent() && node.hasClass("dep-file-node") && node.hasClass("dep-file-node-muted"))
      .toArray();
    const fileEdges = visibleEdges
      .filter((edge) => !edge.hasClass("dep-function-edge") && !edge.hasClass("dep-base-edge-muted") && !edge.hasClass("dep-emphasis-edge") && !edge.hasClass("dep-selected-edge"))
      .toArray();
    const fileOverviewNodes = visibleNodes
      .filter((node) => !node.isParent() && node.hasClass("dep-file-node") && !node.hasClass("dep-file-node-muted"))
      .toArray();
    const fileDetailNodes = visibleNodes.filter((node) => node.isParent()).toArray();
    const emphasisEdges = visibleEdges
      .filter((edge) => edge.hasClass("dep-function-edge") || edge.hasClass("dep-emphasis-edge") || edge.hasClass("dep-selected-edge"))
      .toArray();
    const functionNodes = visibleNodes.filter((node) => !node.isParent() && !node.hasClass("dep-file-node")).toArray();
    return mutedFileEdges.concat(mutedFileNodes, fileEdges, fileOverviewNodes, fileDetailNodes, emphasisEdges, functionNodes);
  }}

  function buildOverviewSvg(scope) {{
    if (!overviewCy) return "";
    stopOverviewPositionAnimation();
    const bounds = svgElementBounds(scope);
    const width = Math.max(1, bounds.x2 - bounds.x1);
    const height = Math.max(1, bounds.y2 - bounds.y1);
    const elementsSvg = overviewSvgOrderedElements()
      .map((element) => element.isEdge() ? svgEdge(element, scope) : svgNode(element, scope))
      .join("");
    const colors = graphColors();
    return "<?xml version=\\"1.0\\" encoding=\\"UTF-8\\"?>\\n" +
      "<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"" + width.toFixed(0) + "\\" height=\\"" + height.toFixed(0) + "\\" viewBox=\\"" + bounds.x1.toFixed(2) + " " + bounds.y1.toFixed(2) + " " + width.toFixed(2) + " " + height.toFixed(2) + "\\" role=\\"img\\">" +
      "<title>" + escapeXml("依存関係マップ") + "</title>" +
      "<rect x=\\"" + bounds.x1.toFixed(2) + "\\" y=\\"" + bounds.y1.toFixed(2) + "\\" width=\\"" + width.toFixed(2) + "\\" height=\\"" + height.toFixed(2) + "\\" fill=\\"" + escapeXml(colors.background) + "\\"/>" +
      elementsSvg +
      "</svg>\\n";
  }}

  function downloadOverviewSvg(scope) {{
    if (!overviewCy) return;
    const safeCategory = safeFileNamePart(reportCategory);
    const suffix = scope === "full" ? "full" : "viewport";
    const svg = buildOverviewSvg(scope);
    if (!svg) return;
    downloadTextFile("dependency-map-" + safeCategory + "-" + suffix + ".svg", svg, "image/svg+xml;charset=utf-8");
  }}

  function downloadOverviewPng(scope) {{
    if (!overviewCy) return;
    stopOverviewPositionAnimation();
    const safeCategory = safeFileNamePart(reportCategory);
    const suffix = scope === "full" ? "full" : "viewport";
    const colors = graphColors();
    const png = overviewCy.png({{
      full: scope === "full",
      bg: colors.background,
      output: "base64uri"
    }});
    if (!png) return;
    const tmp = document.createElement("a");
    tmp.href = png;
    tmp.setAttribute("download", "dependency-map-" + safeCategory + "-" + suffix + ".png");
    document.body.appendChild(tmp);
    tmp.click();
    document.body.removeChild(tmp);
  }}

  function renderOverviewDetail(filePath) {{
    const file = fileByPath.get(filePath) || {{}};
    const rows = (functionsByFile.get(filePath) || []).slice().sort((a, b) => compareBaseOrder(a, b));
    const items = rows
      .map((fn) => "<li><button type=\\"button\\" class=\\"dep-neighbor-button\\" data-function-id=\\"" + escapeHtml(fn.id) + "\\">" + escapeHtml(fn.name) + "</button> <small>" + escapeHtml(fn.dependencyClass) + "</small></li>")
      .join("");
    overviewDetail.innerHTML =
      "<h2>" + escapeHtml(shortPath(filePath)) + "</h2>" +
      (file.brief ? "<p class=\\"dep-brief\\">" + escapeHtml(file.brief) + "</p>" : "") +
      "<dl>" +
      "<dt>領域</dt><dd>" + areaBadge(file.dominantArea || "") + "</dd>" +
      "<dt>ファイル</dt><dd>" + escapeHtml(filePath) + "</dd>" +
      "<dt>export</dt><dd>" + escapeHtml(file.exportCount || 0) + "</dd>" +
      "<dt>関数</dt><dd>" + escapeHtml(file.functionCount || rows.length) + "</dd>" +
      "<dt>リンク</dt><dd>" + [linkFor(file, "Doxygen", false), linkFor(file, "source", true)].filter(Boolean).join(" / ") + "</dd>" +
      "</dl>" +
      (items ? "<strong>関数</strong><ul>" + items + "</ul>" : "<p class=\\"dep-empty\\">関数はありません。</p>");
    bindOverviewActions();
  }}

  function bindFileDetailActions() {{
    for (const button of fileDetail.querySelectorAll("[data-function-id]")) {{
      button.addEventListener("click", () => selectFunction(button.getAttribute("data-function-id"), {{ activateFunctionList: true }}));
    }}
    for (const link of fileDetail.querySelectorAll("[data-file-path]")) {{
      link.addEventListener("click", (event) => {{
        event.preventDefault();
        selectFile(link.getAttribute("data-file-path"));
      }});
    }}
  }}

  function renderFileDetail(filePath) {{
    const file = fileByPath.get(filePath);
    if (!file) {{
      fileDetail.innerHTML = "<p class=\\"dep-empty\\">ファイルを選択してください。</p>";
      return;
    }}
    const rows = (functionsByFile.get(filePath) || []).slice().sort((a, b) => compareBaseOrder(a, b));
    const items = rows
      .map((fn) => "<li><button type=\\"button\\" class=\\"dep-neighbor-button\\" data-function-id=\\"" + escapeHtml(fn.id) + "\\">" + escapeHtml(fn.name) + "</button> <small>" + escapeHtml(fn.dependencyClass) + "</small></li>")
      .join("");
    fileDetail.innerHTML =
      "<h2>" + escapeHtml(shortPath(filePath)) + "</h2>" +
      (file.brief ? "<p class=\\"dep-brief\\">" + escapeHtml(file.brief) + "</p>" : "") +
      "<dl>" +
      "<dt>領域</dt><dd>" + areaBadge(file.dominantArea || "") + "</dd>" +
      "<dt>ファイル</dt><dd>" + escapeHtml(filePath) + "</dd>" +
      "<dt>関数</dt><dd>" + escapeHtml(file.functionCount || rows.length) + "</dd>" +
      "<dt>export</dt><dd>" + escapeHtml(file.exportCount || 0) + "</dd>" +
      "<dt>static</dt><dd>" + escapeHtml(file.staticCount || 0) + "</dd>" +
      "<dt>呼び出し</dt><dd>" + escapeHtml(file.edgeCount || 0) + "</dd>" +
      "<dt>level</dt><dd>" + escapeHtml(fileLevelText(file)) + "</dd>" +
      "<dt>分類</dt><dd>" + escapeHtml(fileClassText(file)) + "</dd>" +
      "<dt>領域内訳</dt><dd>" + escapeHtml(fileAreasText(file)) + "</dd>" +
      "<dt>リンク</dt><dd>" + [linkFor(file, "Doxygen", false), linkFor(file, "source", true)].filter(Boolean).join(" / ") + "</dd>" +
      "</dl>" +
      (items ? "<strong>関数</strong><ul>" + items + "</ul>" : "<p class=\\"dep-empty\\">関数はありません。</p>");
    bindFileDetailActions();
  }}

  function renderOverviewFunctionDetail(fn) {{
    overviewDetail.innerHTML =
      "<h2>" + escapeHtml(fn.name) + "</h2>" +
      (fn.brief ? "<p class=\\"dep-brief\\">" + escapeHtml(fn.brief) + "</p>" : "") +
      "<dl>" +
      "<dt>分類</dt><dd><span class=\\"badge " + escapeHtml(fn.dependencyClass) + "\\">" + escapeHtml(fn.dependencyClass) + "</span></dd>" +
      "<dt>level</dt><dd>" + escapeHtml(levelText(fn)) + "</dd>" +
      "<dt>領域</dt><dd>" + areaBadge(fn.sourceArea) + "</dd>" +
      "<dt>呼び出し種別</dt><dd>" + escapeHtml(fn.dominantCallKind) + "</dd>" +
      "<dt>export</dt><dd>" + (fn.isExported ? "yes" : "no") + "</dd>" +
      "<dt>static</dt><dd>" + (fn.isStatic ? "yes" : "no") + "</dd>" +
      "<dt>ファイル</dt><dd>" + fileSelectionLink(fn.file, fn.file) + "</dd>" +
      "<dt>行</dt><dd>" + escapeHtml(fn.line) + "</dd>" +
      "<dt>リンク</dt><dd>" + [linkFor(fn, "Doxygen", false), linkFor(fn, "source", true)].filter(Boolean).join(" / ") + "</dd>" +
      "</dl>" +
      "<div class=\\"dep-neighbors\\">" +
      "<section><strong>呼び出し先 (ライブラリ内)</strong>" + neighborList(callees.get(fn.id), "対象範囲内の呼び出し先はありません。") + "</section>" +
      (fn.externalCallees && fn.externalCallees.length > 0 ? "<section><strong>呼び出し先 (外部)</strong>" + externalCalleeList(fn.externalCallees) + "</section>" : "") +
      "<section><strong>呼び出し元</strong>" + neighborList(callers.get(fn.id), "対象範囲内の呼び出し元はありません。") + "</section>" +
      cycleGroupSection(fn) +
      "</div>";
    bindOverviewActions();
  }}

  function fileArea(filePath) {{
    const file = fileByPath.get(filePath);
    if (file && file.dominantArea) return file.dominantArea;
    const rows = functionsByFile.get(filePath) || [];
    return rows.length > 0 ? rows[0].sourceArea : "";
  }}

  function edgeFunctionPairs(fromFile, toFile) {{
    return (edgePairsByFileKey.get(overviewEdgeKey(fromFile, toFile)) || [])
      .map((edge) => {{
        return {{ caller: byId.get(edge.caller), callee: byId.get(edge.callee) }};
      }})
      .filter((pair) => pair.caller && pair.callee)
      .sort((a, b) => compareBaseOrder(a.caller, b.caller) || compareBaseOrder(a.callee, b.callee));
  }}

  function edgePairList(fromFile, toFile) {{
    const pairs = edgeFunctionPairs(fromFile, toFile);
    if (pairs.length === 0) return "<p class=\\"dep-empty\\">対象範囲内の呼び出しはありません。</p>";
    const items = pairs.map((pair) => {{
      return "<li>" +
        "<button type=\\"button\\" class=\\"dep-neighbor-button\\" data-function-id=\\"" + escapeHtml(pair.caller.id) + "\\">" + escapeHtml(pair.caller.name) + "</button>" +
        " -> " +
        "<button type=\\"button\\" class=\\"dep-neighbor-button\\" data-function-id=\\"" + escapeHtml(pair.callee.id) + "\\">" + escapeHtml(pair.callee.name) + "</button>" +
        "</li>";
    }});
    return "<ul>" + items.join("") + "</ul>";
  }}

  function renderOverviewEdgeDetail(edgeKey) {{
    const parts = text(edgeKey).split("\\n");
    const fromFile = parts[0] || "";
    const toFile = parts[1] || "";
    overviewDetail.innerHTML =
      "<h2>ファイル間依存</h2>" +
      "<dl>" +
      "<dt>from</dt><dd>" + fileSelectionLink(fromFile, fromFile) + " " + areaBadge(fileArea(fromFile)) + "</dd>" +
      "<dt>to</dt><dd>" + fileSelectionLink(toFile, toFile) + " " + areaBadge(fileArea(toFile)) + "</dd>" +
      "</dl>" +
      "<div class=\\"dep-neighbors\\">" +
      "<section><strong>関数</strong>" + edgePairList(fromFile, toFile) + "</section>" +
      "</div>";
    bindOverviewActions();
  }}

  function bindOverviewActions() {{
    for (const button of overviewDetail.querySelectorAll("[data-function-id]")) {{
      button.addEventListener("click", () => selectFunction(button.getAttribute("data-function-id")));
    }}
    for (const link of overviewDetail.querySelectorAll("[data-file-path]")) {{
      link.addEventListener("click", (event) => {{
        event.preventDefault();
        selectFile(link.getAttribute("data-file-path"));
      }});
    }}
  }}

  function overviewSelectionContext(selection) {{
    return {{
      selectedId: selection && Object.prototype.hasOwnProperty.call(selection, "selectedId") ? selection.selectedId : selectedId,
      selectedFilePath: selection && Object.prototype.hasOwnProperty.call(selection, "selectedFilePath") ? selection.selectedFilePath : selectedFilePath,
      selectedEdgeKey: selection && Object.prototype.hasOwnProperty.call(selection, "selectedEdgeKey") ? selection.selectedEdgeKey : selectedEdgeKey
    }};
  }}

  function overviewEmptySelection() {{
    return {{ selectedId: "", selectedFilePath: "", selectedEdgeKey: "" }};
  }}

  function overviewSelectionState(edgeMap, selection) {{
    const context = overviewSelectionContext(selection);
    const activeFiles = new Set();
    const activeFileEdges = new Set();
    const emphasisFileEdges = new Set();
    if (context.selectedId) {{
      const visibleFnIds = visibleFunctionIdsForOverview(context);
      for (const fnId of visibleFnIds) {{
        const fn = byId.get(fnId);
        if (fn) activeFiles.add(fn.file);
      }}
      return {{ activeFiles: activeFiles, activeFileEdges: activeFileEdges, emphasisFileEdges: emphasisFileEdges, hasSelection: true }};
    }}
    if (context.selectedEdgeKey) {{
      const edge = edgeMap.get(context.selectedEdgeKey);
      if (edge) {{
        activeFiles.add(edge.data.fromFile);
        activeFiles.add(edge.data.toFile);
        activeFileEdges.add(context.selectedEdgeKey);
      }}
      return {{ activeFiles: activeFiles, activeFileEdges: activeFileEdges, emphasisFileEdges: emphasisFileEdges, hasSelection: true }};
    }}
    if (context.selectedFilePath) {{
      activeFiles.add(context.selectedFilePath);
      for (const edge of edgeMap.values()) {{
        if (edge.data.fromFile === context.selectedFilePath || edge.data.toFile === context.selectedFilePath) {{
          activeFiles.add(edge.data.fromFile);
          activeFiles.add(edge.data.toFile);
        }}
        if (edge.data.fromFile === context.selectedFilePath || edge.data.toFile === context.selectedFilePath) {{
          emphasisFileEdges.add(edge.data.id);
        }}
      }}
      for (const edge of edgeMap.values()) {{
        if (activeFiles.has(edge.data.fromFile) && activeFiles.has(edge.data.toFile)) {{
          activeFileEdges.add(edge.data.id);
        }}
      }}
      return {{ activeFiles: activeFiles, activeFileEdges: activeFileEdges, emphasisFileEdges: emphasisFileEdges, hasSelection: true }};
    }}
    return {{ activeFiles: activeFiles, activeFileEdges: activeFileEdges, emphasisFileEdges: emphasisFileEdges, hasSelection: false }};
  }}

  // ファイル ノード/エッジの data は不変 (id/ラベル/weight など) のため、初期化時に 1 回だけ
  // 構築して毎 sync 再利用する。sync ごとに変わるのは classes と復活位置 (position) のみ。
  // Phase A の element.data(target.data) は cytoscape が値を要素側へコピーするだけで
  // 引数オブジェクトを書き換えないため、共有してよい。
  const overviewFileNodeData = new Map(files.map((file) => [file.path, {{
    id: file.path,
    label: shortPath(file.path),
    weight: Math.max(1, Number(file.functionCount || 1)),
    path: file.path
  }}]));
  const overviewFileEdgeData = new Map(fileEdges.map((edge) => [edge.id, {{
    id: edge.id,
    source: edge.source,
    target: edge.target,
    kind: "file-edge",
    fromFile: edge.fromFile,
    toFile: edge.toFile,
    label: edge.label,
    weight: edge.weight
  }}]));

  function overviewBaseElements(selection) {{
    const context = overviewSelectionContext(selection);
    const selectionState = overviewSelectionState(fileEdgeByKey, context);
    const elements = [];
    for (const file of files) {{
      if (hiddenOverviewFiles.has(file.path)) continue;
      const classes = ["dep-file-node"];
      const areaClass = graphFileClassFor(file.dominantArea);
      if (areaClass) classes.push(areaClass);
      if (!context.selectedId && file.path === context.selectedFilePath) classes.push("dep-selected-file");
      if (selectionState.hasSelection && !selectionState.activeFiles.has(file.path)) {{
        classes.push("dep-file-node-muted");
      }}
      const fileElement = {{
        data: overviewFileNodeData.get(file.path),
        classes: classes.join(" ")
      }};
      const restorePosition = overviewRestorePositions.get(file.path);
      if (restorePosition) fileElement.position = {{ x: restorePosition.x, y: restorePosition.y }};
      elements.push(fileElement);
    }}
    for (const edge of fileEdges) {{
      if (hiddenOverviewFiles.has(edge.fromFile) || hiddenOverviewFiles.has(edge.toFile)) continue;
      const classes = [];
      if (selectedEdgeKey && edge.id === selectedEdgeKey) classes.push("dep-selected-edge");
      if (selectionState.emphasisFileEdges.has(edge.id)) classes.push("dep-emphasis-edge");
      if (selectionState.hasSelection && !selectionState.activeFileEdges.has(edge.id)) {{
        classes.push("dep-base-edge-muted");
      }}
      elements.push({{
        data: overviewFileEdgeData.get(edge.id),
        classes: classes.join(" ")
      }});
    }}
    return elements;
  }}

  // 深さ設定 (overviewCallerDepth / overviewCalleeDepth) に基づき、起点から edgeMap
  // (callers または callees) を辿って到達可能な id 集合を ids へ追加する。
  // depth 0 は非表示 (追加なし)、1 は起点の 1 段のみ、Infinity は推移閉包 (BFS) で全段。
  // direction: "caller" は edgeMap (callers) を辿るときのエッジ向き (neighbor -> current)、
  // "callee" は edgeMap (callees) を辿るときのエッジ向き (current -> neighbor) を表す。
  // routeEdgeIds には辿った各ステップのエッジ id (関数間エッジ id と同じ "caller->callee" 形式)
  // を記録する。これにより、選択の展開経路 (ルート) 上のエッジを強調対象として区別できる。
  function overviewRouteEdgeKey(direction, current, neighbor) {{
    return direction === "caller" ? (neighbor + "->" + current) : (current + "->" + neighbor);
  }}

  function collectOverviewRelatedIds(startId, edgeMap, depth, direction, ids, routeEdgeIds) {{
    if (depth <= 0) return;
    if (depth === 1) {{
      for (const c of (edgeMap.get(startId) || [])) {{
        ids.add(c);
        routeEdgeIds.add(overviewRouteEdgeKey(direction, startId, c));
      }}
      return;
    }}
    const visited = new Set([startId]);
    let frontier = [startId];
    while (frontier.length > 0) {{
      const next = [];
      for (const current of frontier) {{
        for (const neighbor of (edgeMap.get(current) || [])) {{
          routeEdgeIds.add(overviewRouteEdgeKey(direction, current, neighbor));
          if (visited.has(neighbor)) continue;
          visited.add(neighbor);
          ids.add(neighbor);
          next.push(neighbor);
        }}
      }}
      frontier = next;
    }}
  }}

  // relatedFunctionIdsForSelection は 1 回の sync 内で複数箇所 (overviewSelectionState と
  // buildOverviewElements 系) から呼ばれるため、直近結果をメモ化する。呼び出し関係
  // (edges/callers/callees) は静的データであり、キーは選択 id と深さ設定のみで決まる。
  // 返す Set は読み取り専用として扱うこと (呼び出し側で変更しない)。
  let overviewRelatedSelectionCache = {{ key: null, value: null }};

  // 選択関数から表示する関連関数 id 集合と、強調対象のエッジ id 集合 (呼び出し元/先の
  // 展開で辿った経路) を求める。選択関数の循環グループ全体は呼び出し元/先の深さ設定に
  // 関わらず常に表示する (routeEdgeIds には含めないが、循環グループ内のエッジは
  // overviewFunctionEdgeClasses 側の selectedCycleIds 判定で別途強調する)。
  function relatedFunctionIdsForSelection(selectedId) {{
    const cacheKey = selectedId + "|" + overviewCallerDepth + "|" + overviewCalleeDepth;
    if (overviewRelatedSelectionCache.key === cacheKey) return overviewRelatedSelectionCache.value;
    const ids = new Set([selectedId]);
    const routeEdgeIds = new Set();
    const selectedFn = byId.get(selectedId);
    for (const c of cycleGroupFunctionIds(selectedFn)) ids.add(c);
    collectOverviewRelatedIds(selectedId, callers, overviewCallerDepth, "caller", ids, routeEdgeIds);
    collectOverviewRelatedIds(selectedId, callees, overviewCalleeDepth, "callee", ids, routeEdgeIds);
    const value = {{ ids: ids, routeEdgeIds: routeEdgeIds }};
    overviewRelatedSelectionCache = {{ key: cacheKey, value: value }};
    return value;
  }}

  function visibleFunctionIdsForOverview(selection) {{
    const context = overviewSelectionContext(selection);
    if (context.selectedId) {{
      return relatedFunctionIdsForSelection(context.selectedId).ids;
    }}
    if (context.selectedFilePath) {{
      const ids = new Set();
      for (const fn of (functionsByFile.get(context.selectedFilePath) || [])) ids.add(fn.id);
      return ids;
    }}
    return new Set();
  }}

  // 表示関数集合 (includedFnIds) の間を結ぶ関数間エッジを、全エッジの線形走査を避けて
  // 隣接リスト (edgesByFunctionId) から列挙する。両端に登録されるため id で重複排除する。
  // 結果集合は「両端が included のエッジすべて」で、全走査と同一。
  function overviewIncludedFunctionEdges(includedFnIds) {{
    const seen = new Set();
    const result = [];
    for (const fnId of includedFnIds) {{
      for (const edge of (edgesByFunctionId.get(fnId) || [])) {{
        if (!includedFnIds.has(edge.caller) || !includedFnIds.has(edge.callee)) continue;
        const key = edge.caller + "->" + edge.callee;
        if (seen.has(key)) continue;
        seen.add(key);
        result.push(edge);
      }}
    }}
    return result;
  }}

  // 強調対象は、呼び出し元/先の展開で辿った経路上のエッジ (routeEdgeIds) と、選択関数の
  // 循環グループ内のエッジ (selectedCycleIds の両端一致)。表示はされていても展開経路に
  // 含まれないエッジ (例: 呼び出し先ルート上の関数から、別に表示中の関数への呼び出し元
  // 方向の関連など) は通常表示のままにする。
  function overviewFunctionEdgeClasses(edge, selectedCycleIds, routeEdgeIds, selection) {{
    const context = overviewSelectionContext(selection);
    const classes = [];
    if (context.selectedId && (routeEdgeIds.has(edge.caller + "->" + edge.callee) ||
        (selectedCycleIds.has(edge.caller) && selectedCycleIds.has(edge.callee)))) {{
      classes.push("dep-function-edge");
    }}
    return classes.join(" ");
  }}

  function buildOverviewElements(selection) {{
    const context = overviewSelectionContext(selection);
    const elements = overviewBaseElements(context);
    const relatedSelection = context.selectedId ? relatedFunctionIdsForSelection(context.selectedId) : null;
    const visibleFnIds = relatedSelection ? relatedSelection.ids : visibleFunctionIdsForOverview(context);
    const routeEdgeIds = relatedSelection ? relatedSelection.routeEdgeIds : new Set();
    const visibleFns = Array.from(visibleFnIds)
      .map((id) => byId.get(id))
      .filter(Boolean)
      .filter((fn) => !hiddenOverviewFiles.has(fn.file))
      .sort((a, b) => {{
        if (a.id === context.selectedId) return -1;
        if (b.id === context.selectedId) return 1;
        return compareBaseOrder(a, b);
      }});
    const includedFnIds = new Set(visibleFns.map((fn) => fn.id));
    const selectedCycleIds = new Set(cycleGroupFunctionIds(byId.get(context.selectedId)));
    const childrenByFile = new Map();
    for (let index = 0; index < visibleFns.length; index++) {{
      const fn = visibleFns[index];
      const classes = [graphClassFor(fn.dependencyClass)];
      if (fn.id === context.selectedId) classes.push("dep-center-node");
      elements.push({{
        data: {{
          id: fn.id,
          label: fn.name,
          parent: fn.file,
          weight: graphFunctionWeight(fn)
        }},
        position: overviewFunctionPosition(fn, index, visibleFns.length, context),
        classes: classes.join(" ")
      }});
      if (!childrenByFile.has(fn.file)) childrenByFile.set(fn.file, []);
      childrenByFile.get(fn.file).push(fn.id);
    }}
    if (context.selectedId) {{
      for (const edge of overviewIncludedFunctionEdges(includedFnIds)) {{
        elements.push({{
          data: {{
            id: edge.caller + "->" + edge.callee,
            source: edge.caller,
            target: edge.callee,
            weight: 1
          }},
          classes: overviewFunctionEdgeClasses(edge, selectedCycleIds, routeEdgeIds, context)
        }});
      }}
    }} else if (context.selectedFilePath) {{
      for (const [filePath, ids] of childrenByFile) {{
        if (ids.length < 2) continue;
        const hub = ids[0];
        for (let i = 1; i < ids.length; i++) {{
          elements.push({{
            data: {{
              id: "pull-" + filePath + "-" + ids[i],
              source: hub,
              target: ids[i]
            }},
            classes: "dep-pull-edge"
          }});
        }}
      }}
    }}
    return elements;
  }}

  async function buildOverviewElementsAsync(token, selection) {{
    const context = overviewSelectionContext(selection);
    const selectionState = overviewSelectionState(fileEdgeByKey, context);
    const elements = [];
    if (!(await processOverviewChunks(files, token, (chunk) => {{
      for (const file of chunk) {{
        if (hiddenOverviewFiles.has(file.path)) continue;
        const classes = ["dep-file-node"];
        const areaClass = graphFileClassFor(file.dominantArea);
        if (areaClass) classes.push(areaClass);
        if (!context.selectedId && file.path === context.selectedFilePath) classes.push("dep-selected-file");
        if (selectionState.hasSelection && !selectionState.activeFiles.has(file.path)) {{
          classes.push("dep-file-node-muted");
        }}
        elements.push({{
          data: overviewFileNodeData.get(file.path),
          classes: classes.join(" ")
        }});
      }}
    }}))) return null;
    if (!(await processOverviewChunks(fileEdges, token, (chunk) => {{
      for (const edge of chunk) {{
        if (hiddenOverviewFiles.has(edge.fromFile) || hiddenOverviewFiles.has(edge.toFile)) continue;
        const classes = [];
        if (selectedEdgeKey && edge.id === selectedEdgeKey) classes.push("dep-selected-edge");
        if (selectionState.emphasisFileEdges.has(edge.id)) classes.push("dep-emphasis-edge");
        if (selectionState.hasSelection && !selectionState.activeFileEdges.has(edge.id)) {{
          classes.push("dep-base-edge-muted");
        }}
        elements.push({{
          data: overviewFileEdgeData.get(edge.id),
          classes: classes.join(" ")
        }});
      }}
    }}))) return null;
    const relatedSelection = context.selectedId ? relatedFunctionIdsForSelection(context.selectedId) : null;
    const visibleFnIds = relatedSelection ? relatedSelection.ids : visibleFunctionIdsForOverview(context);
    const routeEdgeIds = relatedSelection ? relatedSelection.routeEdgeIds : new Set();
    const visibleFns = Array.from(visibleFnIds)
      .map((id) => byId.get(id))
      .filter(Boolean)
      .filter((fn) => !hiddenOverviewFiles.has(fn.file))
      .sort((a, b) => {{
        if (a.id === context.selectedId) return -1;
        if (b.id === context.selectedId) return 1;
        return compareBaseOrder(a, b);
      }});
    const includedFnIds = new Set(visibleFns.map((fn) => fn.id));
    const selectedCycleIds = new Set(cycleGroupFunctionIds(byId.get(context.selectedId)));
    const childrenByFile = new Map();
    let fnIndex = 0;
    if (!(await processOverviewChunks(visibleFns, token, (chunk) => {{
      for (const fn of chunk) {{
        const index = fnIndex;
        fnIndex += 1;
        const classes = [graphClassFor(fn.dependencyClass)];
        if (fn.id === context.selectedId) classes.push("dep-center-node");
        elements.push({{
          data: {{
            id: fn.id,
            label: fn.name,
            parent: fn.file,
            weight: graphFunctionWeight(fn)
          }},
          position: overviewFunctionPosition(fn, index, visibleFns.length, context),
          classes: classes.join(" ")
        }});
        if (!childrenByFile.has(fn.file)) childrenByFile.set(fn.file, []);
        childrenByFile.get(fn.file).push(fn.id);
      }}
    }}))) return null;
    if (context.selectedId) {{
      if (!(await processOverviewChunks(overviewIncludedFunctionEdges(includedFnIds), token, (chunk) => {{
        for (const edge of chunk) {{
          elements.push({{
            data: {{
              id: edge.caller + "->" + edge.callee,
              source: edge.caller,
              target: edge.callee,
              weight: 1
            }},
            classes: overviewFunctionEdgeClasses(edge, selectedCycleIds, routeEdgeIds, context)
          }});
        }}
      }}))) return null;
    }} else if (context.selectedFilePath) {{
      const childGroups = Array.from(childrenByFile.entries());
      if (!(await processOverviewChunks(childGroups, token, (chunk) => {{
        for (const [filePath, ids] of chunk) {{
          if (ids.length < 2) continue;
          const hub = ids[0];
          for (let i = 1; i < ids.length; i++) {{
            elements.push({{
              data: {{
                id: "pull-" + filePath + "-" + ids[i],
                source: hub,
                target: ids[i]
              }},
              classes: "dep-pull-edge"
            }});
          }}
        }}
      }}))) return null;
    }}
    return isLatestOverviewSync(token) ? elements : null;
  }}

  function overviewFunctionPosition(fn, index, count, selection) {{
    const context = overviewSelectionContext(selection);
    if (!overviewCy) return {{ x: 0, y: 0 }};
    const parent = overviewCy.getElementById(fn.file);
    const center = parent && parent.length > 0 ? parent.position() : {{ x: 0, y: 0 }};
    if (fn.id === context.selectedId) return {{ x: center.x, y: center.y }};
    const ringIndex = context.selectedId ? Math.max(0, index - 1) : index;
    const ringCount = context.selectedId ? Math.max(1, count - 1) : Math.max(1, count);
    const radius = 56 + Math.min(72, ringCount * 4);
    const angle = -Math.PI / 2 + (Math.PI * 2 * ringIndex) / ringCount;
    return {{
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius
    }};
  }}

  function overviewFileEdgeLength(edge, maxLength, minLength) {{
    if (edge.hasClass("dep-pull-edge")) return 48;
    const weight = Math.max(1, Number(edge.data("weight") || 1));
    const normalized = Math.min(1, Math.log2(weight) / 4);
    return maxLength - (maxLength - minLength) * normalized;
  }}

  // 進行中のレイアウト (cola / cose) を実際に停止する。layout.stop() は
  // adaptor.stop() を呼ぶが layoutstop の発火は非同期になり得るため、ロックの解除は
  // ここで即座に行い、停止由来の遅延 layoutstop は finishLayout 側の isCurrentLayout()
  // ガードで無害化する。これを呼ばないと、新しい選択で別レイアウトを起動しても旧 cola が
  // maxSimulationTime まで走り続け、同一 overviewCy 上で位置を奪い合って全体が暴れる。
  function stopOverviewActiveLayout() {{
    if (!overviewActiveLayout) return;
    const active = overviewActiveLayout;
    overviewActiveLayout = null;
    // 中止するレイアウトの移動対象は seed のまま取り残されるため、再レイアウト保留として記録する。
    // 次の sync で現存するものを movingNodeIds へ再投入し Phase B をやり直す。
    if (active.movingNodeIds) {{
      for (const id of active.movingNodeIds) overviewPendingRelayoutNodeIds.add(id);
    }}
    if (active.lockedNodes) {{
      try {{ active.lockedNodes.unlock(); }} catch (err) {{ /* 解除済みは無視 */ }}
    }}
    // layout.stop() は layoutstop を同期発火させることがある。その場合、割り込み元 (選択変更)
    // の sync がトークンを更新する前に finishLayout が走るため、isCurrentLayout() だけでは
    // 中止と自然完了を区別できず、「自然完了」と誤認して上で登録した再レイアウト保留を消し、
    // 未収束の seed 座標を最終位置として確定してしまう。中止をハンドル自体へ記録し、
    // finishLayout 側で完了処理を抑止する。
    active.aborted = true;
    if (active.layout && typeof active.layout.stop === "function") {{
      try {{ active.layout.stop(); }} catch (err) {{ /* 停止済みは無視 */ }}
    }}
  }}

  function runOverviewLayout(opts) {{
    if (!overviewCy) return;
    stopOverviewActiveLayout();
    const fit = Boolean(opts && opts.fit);
    const manual = Boolean(opts && opts.manual);
    const deferPositions = Boolean(opts && opts.deferPositions);
    const animatePositions = !(opts && opts.animatePositions === false);
    const instantPositions = Boolean(opts && opts.instantPositions);
    const fullConvergence = Boolean(opts && opts.fullConvergence);
    const unlockAllDuringLayout = Boolean(opts && opts.unlockAllDuringLayout);
    const scopeToVisibleChildren = Boolean(opts && opts.scopeToVisibleChildren);
    const movingNodeIds = opts && opts.movingNodeIds ? opts.movingNodeIds : null;
    const anchorCenters = opts && opts.anchorCenters ? opts.anchorCenters : new Map();
    const immediate = Boolean(opts && opts.immediate) || !overviewLayoutInitialized;
    const layoutPasses = Math.max(1, Number((opts && opts.layoutPasses) || 1));
    const onComplete = opts && typeof opts.onComplete === "function" ? opts.onComplete : null;
    const layoutToken = opts && opts.layoutToken ? opts.layoutToken : ++overviewLayoutToken;
    const syncToken = opts && opts.syncToken ? opts.syncToken : null;
    const startPositions = overviewNodePositions();
    const lockedNodes = (!unlockAllDuringLayout && movingNodeIds) ? overviewCy.nodes().filter((node) => !movingNodeIds.has(node.id())) : overviewCy.collection();
    // Phase B は「展開中ファイル配下の関数の座標」だけを見た目へ反映し、ファイル位置は
    // 計算後に anchor で元へ戻す。全グラフを cola にかけると崩壊 (子なし) ファイルまで
    // 計算してから捨てるため、コストが総ノード数に比例する。scopeToVisibleChildren のときは
    // レイアウトに効く部分グラフ (子を持つファイル + その子 + 子同士のエッジ) だけを対象にし、
    // コストを可視関数数に比例させる。cytoscape-cola は渡した eles のノード/エッジだけを
    // 計算対象にする。
    let layoutTarget = overviewCy;
    if (scopeToVisibleChildren) {{
      const layoutParents = overviewCy.nodes(":parent");
      const layoutChildren = layoutParents.children();
      if (layoutChildren.length > 0) {{
        // 関数配置に効くのは関数間エッジ (dep-function-edge / dep-pull-edge) のみ。
        // file-edge は端点がファイル ノードで関数配置に影響しないため除外する。
        const layoutEdges = overviewCy.edges().filter(
          (edge) => layoutChildren.contains(edge.source()) && layoutChildren.contains(edge.target())
        );
        layoutTarget = layoutParents.union(layoutChildren).union(layoutEdges);
      }}
    }}
    overviewLayoutInitialized = true;
    stopOverviewPositionAnimation();
    const isCurrentLayout = () => (
      layoutToken === overviewLayoutToken && (!syncToken || isLatestOverviewSync(syncToken))
    );
    let startedLayout = null;
    let activeHandle = null;
    let layoutStartMs = 0;
    const finishLayout = async () => {{
      // layoutstop が発火した時点でこのレイアウトは終了。cola の純計算時間を記録する。
      if (layoutStartMs > 0) overviewLastLayoutDurationMs = performance.now() - layoutStartMs;
      // アクティブ ハンドルが自分自身を指しているなら解放する (別レイアウトに更新済みなら触らない)。
      if (overviewActiveLayout && overviewActiveLayout.layout === startedLayout) overviewActiveLayout = null;
      // stopOverviewActiveLayout で中止されたレイアウトは自然完了として扱わない。中止時の
      // layout.stop() が layoutstop を同期発火させると、割り込み元のトークン更新前に到達する
      // ため isCurrentLayout() が真のまま通過し、再レイアウト保留の削除と未収束座標の確定が
      // 誤って行われる (seed 表示中の関数選択で再レイアウトが失火する実測要因)。
      if (activeHandle && activeHandle.aborted) {{
        lockedNodes.unlock();
        return;
      }}
      if (!isCurrentLayout()) {{
        lockedNodes.unlock();
        return;
      }}
      // このレイアウトは中止されず完了した。レイアウト対象を再レイアウト保留から外す
      // (中止時に stopOverviewActiveLayout が登録するのと対称。これで pending は「最後の
      // レイアウト試行が中止されたノード」だけを保持する)。
      if (movingNodeIds) {{
        for (const id of movingNodeIds) overviewPendingRelayoutNodeIds.delete(id);
      }}
      if (immediate && layoutPasses > 1) {{
        lockedNodes.unlock();
        const nextOpts = Object.assign({{}}, opts || {{}});
        nextOpts.layoutPasses = layoutPasses - 1;
        nextOpts.onComplete = onComplete;
        setTimeout(() => runOverviewLayout(nextOpts), 50);
        return;
      }}
      if (animatePositions || instantPositions) {{
        applyOverviewUserMovedPositions(startPositions, anchorCenters);
        applyOverviewAnchorCentersToCurrentPositions(anchorCenters);
        const targetPositions = overviewNodePositions();
        if (!isCurrentLayout()) {{
          lockedNodes.unlock();
          return;
        }}
        stabilizeOverviewCompoundCenters(targetPositions, anchorCenters);
        stabilizeOverviewLayoutCenter(startPositions, targetPositions, {{ fit, immediate, anchorCenters }});
        restoreOverviewNodePositions(startPositions);
        lockedNodes.unlock();
        if (immediate || instantPositions) {{
          restoreOverviewNodePositions(targetPositions);
          if (fit) fitOverviewGraph();
          if (onComplete) onComplete();
          return;
        }}
        animateOverviewPositions(startPositions, targetPositions, {{ fit, onComplete }});
        return;
      }}
      applyOverviewUserMovedPositions(startPositions, anchorCenters);
      if (!(await applyOverviewAnchorCentersToCurrentPositionsAsync(anchorCenters, syncToken))) {{
        lockedNodes.unlock();
        return;
      }}
      const targetPositions = await overviewNodePositionsAsync(syncToken);
      if (!targetPositions || !isCurrentLayout()) {{
        lockedNodes.unlock();
        return;
      }}
      stabilizeOverviewCompoundCenters(targetPositions, anchorCenters);
      stabilizeOverviewLayoutCenter(startPositions, targetPositions, {{ fit, immediate, anchorCenters }});
      lockedNodes.unlock();
      if (fit) fitOverviewGraph();
      if (onComplete) onComplete();
    }};
    // ここから実レイアウト (cola / cose) を起動する。テスト検証用に起動回数と
    // 投入ノード数を記録する (投入ノード数はスコープ化の効果を測る指標)。
    overviewLayoutRunCount += 1;
    overviewLastLayoutNodeCount = layoutTarget.nodes().length;
    if (typeof cytoscapeCola === "function") {{
      lockedNodes.lock();
      const layout = layoutTarget.layout({{
        name: "cola",
        animate: false,
        deferPositions: manual || immediate || deferPositions,
        // ファイル (compound) の grab をシミュレーションへ伝えない。webcola はグループの
        // dragstart で全 leaf (関数) を fixed にするため、計算中にファイルを押下保持しただけで
        // 降下計算が「収束」と誤判定して早期終了し、中途半端な配置が正常完了として採用される
        // (control 784ms に対し押下ありで 153ms 終了を実測)。ファイル位置の反映は finishLayout
        // 以降の anchor と live アンカーが担うため、cola 側での固定は不要。
        // see: https://github.com/tgdwyer/WebCola/blob/master/WebCola/src/layout.ts
        ignoreCompoundDrags: true,
        refresh: 1,
        maxSimulationTime: manual ? 450 : (fullConvergence ? 2000 : 900),
        fit: false,
        padding: 30,
        randomize: false,
        avoidOverlap: true,
        handleDisconnected: true,
        nodeSpacing: function (node) {{ return node.isParent() ? 22 : 14; }},
        centerGraph: fullConvergence,
        edgeLength: function (edge) {{ return overviewFileEdgeLength(edge, 140, 128); }},
        convergenceThreshold: manual ? 0.12 : (fullConvergence ? 0.01 : 0.08),
        unconstrIter: fullConvergence ? undefined : (manual ? 4 : 8),
        userConstIter: fullConvergence ? undefined : (manual ? 4 : 8),
        allConstIter: fullConvergence ? undefined : (manual ? 6 : 12)
      }});
      startedLayout = layout;
      activeHandle = {{ layout, lockedNodes, movingNodeIds, aborted: false }};
      overviewActiveLayout = activeHandle;
      layout.one("layoutstop", () => {{
        finishLayout();
      }});
      layoutStartMs = performance.now();
      layout.run();
      return;
    }}
    lockedNodes.lock();
    const layout = layoutTarget.layout({{
      name: "cose",
      animate: false,
      fit: false,
      padding: 30,
      nodeRepulsion: function (node) {{ return node.isParent() ? 14400 : 3000; }},
      idealEdgeLength: function (edge) {{ return overviewFileEdgeLength(edge, 128, 116); }},
      edgeElasticity: function (edge) {{ return edge.hasClass("dep-pull-edge") ? 200 : 100; }},
      nestingFactor: 0.4,
      gravity: 120,
      numIter: manual ? 500 : 1500,
      randomize: false
    }});
    startedLayout = layout;
    activeHandle = {{ layout, lockedNodes, aborted: false }};
    overviewActiveLayout = activeHandle;
    layout.one("layoutstop", () => {{
      finishLayout();
    }});
    layoutStartMs = performance.now();
    layout.run();
  }}

  function overviewNodePositions() {{
    const positions = new Map();
    if (!overviewCy) return positions;
    overviewCy.nodes().forEach((node) => {{
      positions.set(node.id(), {{ x: node.position("x"), y: node.position("y") }});
    }});
    return positions;
  }}

  async function overviewNodePositionsAsync(token) {{
    const positions = new Map();
    if (!overviewCy) return positions;
    const nodes = overviewCy.nodes().toArray();
    if (!(await processOverviewChunks(nodes, token, (chunk) => {{
      for (const node of chunk) {{
        positions.set(node.id(), {{ x: node.position("x"), y: node.position("y") }});
      }}
    }}))) return null;
    return positions;
  }}

  function overviewNodeCenter(positions, referencePositions) {{
    let count = 0;
    let x = 0;
    let y = 0;
    for (const [id, position] of positions) {{
      if (referencePositions && !referencePositions.has(id)) continue;
      x += position.x;
      y += position.y;
      count += 1;
    }}
    if (count === 0) return null;
    return {{ x: x / count, y: y / count }};
  }}

  function translateOverviewPositions(positions, dx, dy) {{
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
    for (const position of positions.values()) {{
      position.x += dx;
      position.y += dy;
    }}
  }}

  function stabilizeOverviewLayoutCenter(startPositions, targetPositions, opts) {{
    if (!opts || opts.fit || opts.immediate) return;
    if (opts.anchorCenters && opts.anchorCenters.size > 0) return;
    const startCenter = overviewNodeCenter(startPositions, targetPositions);
    const targetCenter = overviewNodeCenter(targetPositions, startPositions);
    if (!startCenter || !targetCenter) return;
    translateOverviewPositions(targetPositions, startCenter.x - targetCenter.x, startCenter.y - targetCenter.y);
  }}

  function stabilizeOverviewCompoundCenters(targetPositions, anchorCenters) {{
    if (!overviewCy || !anchorCenters || anchorCenters.size === 0) return;
    for (const [parentId, anchor] of anchorCenters) {{
      const parent = overviewCy.getElementById(parentId);
      if (!parent || !parent.length || isOverviewNodeDragging(parent)) continue;
      const targetParent = targetPositions.get(parentId);
      if (!targetParent) continue;
      const dx = anchor.x - targetParent.x;
      const dy = anchor.y - targetParent.y;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
      targetParent.x += dx;
      targetParent.y += dy;
      parent.descendants().nodes().forEach((child) => {{
        if (isOverviewNodeDragging(child)) return;
        const position = targetPositions.get(child.id());
        if (!position) return;
        position.x += dx;
        position.y += dy;
      }});
    }}
  }}

  function overviewNodeDragIds(node) {{
    const ids = new Set();
    if (!node || !node.length) return ids;
    ids.add(node.id());
    node.descendants().nodes().forEach((child) => ids.add(child.id()));
    return ids;
  }}

  function isOverviewNodeDragging(nodeOrId) {{
    const id = typeof nodeOrId === "string" ? nodeOrId : nodeOrId.id();
    return overviewDraggingNodeIds.has(id);
  }}

  function hasOverviewDraggingNodes() {{
    return overviewDraggingNodeIds.size > 0;
  }}

  function markOverviewFunctionLayoutInterrupted(node) {{
    if (!overviewCy || !node || !node.length || !node.data("parent")) return;
    const parent = node.parent();
    if (!parent || !parent.length) return;
    parent.children().nodes().forEach((child) => overviewPendingRelayoutNodeIds.add(child.id()));
  }}

  function rememberOverviewUserMovedPositions(node) {{
    if (!overviewCy || !node || !node.length) return;
    for (const id of overviewNodeDragIds(node)) {{
      const element = overviewCy.getElementById(id);
      if (!element || !element.length) continue;
      if (element.data("parent")) continue;
      const position = element.position();
      overviewUserMovedNodePositions.set(id, {{ x: position.x, y: position.y }});
    }}
  }}

  function forgetOverviewNodeRuntimeState(node) {{
    if (!node || !node.length || !node.isNode()) return;
    const ids = overviewNodeDragIds(node);
    for (const id of ids) {{
      overviewUserMovedNodePositions.delete(id);
      overviewDraggingNodeIds.delete(id);
      overviewPendingRelayoutNodeIds.delete(id);
    }}
  }}

  function applyOverviewUserMovedPositions(startPositions, anchorCenters) {{
    if (!overviewCy || overviewUserMovedNodePositions.size === 0) return;
    for (const [id, position] of overviewUserMovedNodePositions) {{
      const element = overviewCy.getElementById(id);
      if (!element || !element.length) continue;
      const previous = startPositions.get(id);
      startPositions.set(id, {{ x: position.x, y: position.y }});
      if (anchorCenters && anchorCenters.has(id)) {{
        anchorCenters.set(id, {{ x: position.x, y: position.y }});
      }}
      // ファイル (compound) がドラッグされた分、その子 (関数) の start 座標も同じだけずらす。
      // これをしないと、finishLayout の restoreOverviewNodePositions が子を古い seed 座標
      // (ドラッグ前のファイル位置基準) へ戻し、seed 配置窓でドラッグした直後のアニメーションが
      // 一瞬戻るように見える。ファイルのみのドラッグでは子の相対位置は変わらないため、同じ
      // 並進を子の start にも適用するのが正しい。
      if (previous && element.isParent()) {{
        const dx = position.x - previous.x;
        const dy = position.y - previous.y;
        if (dx !== 0 || dy !== 0) {{
          element.descendants().nodes().forEach((child) => {{
            const childStart = startPositions.get(child.id());
            if (childStart) startPositions.set(child.id(), {{ x: childStart.x + dx, y: childStart.y + dy }});
          }});
        }}
      }}
    }}
    overviewUserMovedNodePositions.clear();
  }}

  function applyOverviewDeferredDragPositions(deferred) {{
    if (!overviewCy || !deferred || overviewUserMovedNodePositions.size === 0) return;
    for (const [id] of overviewUserMovedNodePositions) {{
      const node = overviewCy.getElementById(id);
      if (!node || !node.length || node.data("parent")) continue;
      const current = node.position();
      deferred.startPositions.set(id, {{ x: current.x, y: current.y }});
      const targetParent = deferred.targetPositions.get(id);
      let dx = 0;
      let dy = 0;
      if (targetParent) {{
        dx = current.x - targetParent.x;
        dy = current.y - targetParent.y;
        targetParent.x += dx;
        targetParent.y += dy;
      }}
      node.descendants().nodes().forEach((child) => {{
        const childCurrent = child.position();
        deferred.startPositions.set(child.id(), {{ x: childCurrent.x, y: childCurrent.y }});
        const targetChild = deferred.targetPositions.get(child.id());
        if (targetChild) {{
          targetChild.x += dx;
          targetChild.y += dy;
        }}
      }});
    }}
    overviewUserMovedNodePositions.clear();
  }}

  function restoreOverviewNodePositions(positions) {{
    if (!overviewCy) return;
    overviewCy.nodes().forEach((node) => {{
      if (isOverviewNodeDragging(node)) return;
      const position = positions.get(node.id());
      if (position) node.position(position);
    }});
  }}

  function applyOverviewAnchorCentersToCurrentPositions(anchorCenters) {{
    if (!overviewCy || !anchorCenters || anchorCenters.size === 0) return;
    for (const [id, anchor] of anchorCenters) {{
      const node = overviewCy.getElementById(id);
      if (!node || !node.length) continue;
      // ドラッグ中のファイルもアンカーへ再センタリングする。anchor は
      // applyOverviewUserMovedPositions が最新のドラッグ位置 (カーソル) へ更新済み。
      // ここでスキップすると、保持ドラッグ中に cola が完了したとき、書き込まれた
      // シミュレーション座標のままクラスタ (と子から導出されるファイル位置) が
      // カーソルから離れた場所へ飛ぶ。子レベルのドラッグ スキップは直接ドラッグ
      // された関数を守るためのもので、ファイル ドラッグで伝播登録された子は
      // 移動対象とする。
      const nodeDragging = isOverviewNodeDragging(node);
      const current = node.position();
      const dx = anchor.x - current.x;
      const dy = anchor.y - current.y;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
      const movable = node.descendants().nodes(":unlocked");
      movable.positions((child) => {{
        if (!nodeDragging && isOverviewNodeDragging(child)) return undefined;
        const position = child.position();
        return {{ x: position.x + dx, y: position.y + dy }};
      }});
    }}
  }}

  async function applyOverviewAnchorCentersToCurrentPositionsAsync(anchorCenters, token) {{
    if (!overviewCy || !anchorCenters || anchorCenters.size === 0) return true;
    const anchors = Array.from(anchorCenters.entries());
    return processOverviewChunks(anchors, token, (chunk) => {{
      overviewCy.batch(() => {{
        for (const [id, anchor] of chunk) {{
          const node = overviewCy.getElementById(id);
          if (!node || !node.length) continue;
          // 同期版 (applyOverviewAnchorCentersToCurrentPositions) と同じ理由で、
          // ドラッグ中のファイルも再センタリングし、直接ドラッグされた子のみ守る。
          const nodeDragging = isOverviewNodeDragging(node);
          const current = node.position();
          const dx = anchor.x - current.x;
          const dy = anchor.y - current.y;
          if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
          const movable = node.descendants().nodes(":unlocked");
          movable.positions((child) => {{
            if (!nodeDragging && isOverviewNodeDragging(child)) return undefined;
            const position = child.position();
            return {{ x: position.x + dx, y: position.y + dy }};
          }});
        }}
      }});
    }});
  }}

  function exponentialEaseOutProgress(t, impact) {{
    const clamped = Math.max(0, Math.min(1, t));
    if (clamped >= 1) return 1;
    const rate = 5.2 + Math.max(0, Math.min(1, impact)) * 2.0;
    const endValue = 1 - Math.exp(-rate);
    if (endValue <= 0) return 1;
    const value = 1 - Math.exp(-rate * clamped);
    return Math.max(0, Math.min(1, value / endValue));
  }}

  function stopOverviewPositionAnimation() {{
    if (!overviewPositionAnimation) return;
    overviewPositionAnimation.active = false;
    if (overviewPositionAnimation.frameId !== null) {{
      const caf = window.cancelAnimationFrame || window.webkitCancelAnimationFrame || window.clearTimeout;
      caf(overviewPositionAnimation.frameId);
    }}
    overviewPositionAnimation = null;
  }}

  function animateOverviewPositions(startPositions, targetPositions, opts) {{
    if (!overviewCy) return;
    stopOverviewPositionAnimation();
    if (overviewFunctionGrabInterruptedLayout) {{
      const onComplete = opts && typeof opts.onComplete === "function" ? opts.onComplete : null;
      if (onComplete) onComplete();
      return;
    }}
    if (hasOverviewDraggingNodes()) {{
      overviewDeferredPositionAnimation = {{
        startPositions,
        targetPositions,
        opts: Object.assign({{}}, opts || {{}})
      }};
      overviewSyncAfterDrag = true;
      return;
    }}
    overviewDeferredPositionAnimation = null;
    const duration = OVERVIEW_ANIMATION_MS;
    const distances = new Map();
    let maxDistance = 1;
    for (const [id, target] of targetPositions) {{
      const start = startPositions.get(id) || target;
      const distance = Math.hypot(target.x - start.x, target.y - start.y);
      distances.set(id, distance);
      maxDistance = Math.max(maxDistance, distance);
    }}
    const raf = window.requestAnimationFrame || window.webkitRequestAnimationFrame || ((callback) => window.setTimeout(() => callback(Date.now()), 16));
    const startedAt = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
    overviewPositionAnimation = {{ active: true, frameId: null, targetPositions, opts: Object.assign({{}}, opts || {{}}) }};
    // 与えた座標マップ上の「親ファイルからの相対オフセット」を親ファイルの最新位置へ加えて求める。
    // start (補間の起点) と target (移動目標) の双方に使う。親ファイルが実際にドラッグされているか
    // ユーザー移動済みのときだけ live アンカーし、関数はファイルへ追従しつつレイアウト結果へ収束する。
    // start も live アンカーするのが要点で、これによりドラッグ後の補間がドラッグ前 (seed) の座標から
    // 始まって「一瞬戻る」動きになるのを防ぎ、常に現在のファイル位置を基準に補間する。通常 (非ドラッグ)
    // は従来どおり絶対座標を使い挙動を変えない。ドラッグ済みのルート ファイルは現在位置に留める。
    // 判定は grabbed() ではなくドラッグ集合 (実際の drag イベント) で行う。純タップの静止 grab を
    // アンカーにすると、compound の位置が子から導出されるために錨が子の移動で毎フレーム流れ、
    // クラスタ全体が漂流して重心がファイルから離れる。
    const frameParentPositions = new Map();
    const snapshotParentPositions = () => {{
      frameParentPositions.clear();
      overviewCy.nodes(":parent").forEach((parent) => {{
        frameParentPositions.set(parent.id(), {{ x: parent.position("x"), y: parent.position("y") }});
      }});
    }};
    const liveAnchored = (node, posMap) => {{
      const id = node.id();
      const c = posMap.get(id);
      const parent = node.parent();
      const parentAnchored = parent && parent.length
        && (isOverviewNodeDragging(parent.id()) || overviewUserMovedNodePositions.has(parent.id()))
        && posMap.has(parent.id()) && c;
      if (parentAnchored) {{
        const pc = posMap.get(parent.id());
        // 錨となる親位置はフレーム冒頭のスナップショットを使う。子を再配置しながら
        // parent.position() を読むと、同一フレーム内で導出位置が変わり相対配置が歪む。
        const pp = frameParentPositions.get(parent.id()) || parent.position();
        return {{ x: pp.x + (c.x - pc.x), y: pp.y + (c.y - pc.y) }};
      }}
      if ((!parent || !parent.length) && overviewUserMovedNodePositions.has(id)) {{
        const cur = node.position();
        return {{ x: cur.x, y: cur.y }};
      }}
      return c;
    }};
    const liveTarget = (node) => liveAnchored(node, targetPositions);
    const liveStart = (node) => liveAnchored(node, startPositions);
    const frame = (now) => {{
      if (!overviewPositionAnimation || !overviewPositionAnimation.active) return;
      const elapsed = Math.max(0, now - startedAt);
      const t = Math.min(1, elapsed / duration);
      snapshotParentPositions();
      overviewCy.nodes().positions((node) => {{
        // ドラッグ中のルート ファイルだけはカーソル追従に任せて触らない。compound の子 (関数) は
        // grabbed() が伝播するが、ここでは live アンカーで動かしたいのでスキップ対象から外す。
        // 純タップ (grab のみでドラッグなし) のルート ファイルはスキップせず通常どおり動かす。
        if (node.grabbed() && !node.data("parent") && isOverviewNodeDragging(node.id())) return undefined;
        const target = liveTarget(node);
        if (!target) return undefined;
        const start = liveStart(node) || target;
        const impact = (distances.get(node.id()) || 0) / maxDistance;
        const p = exponentialEaseOutProgress(t, impact);
        return {{
          x: start.x + (target.x - start.x) * p,
          y: start.y + (target.y - start.y) * p
        }};
      }});
      if (t < 1) {{
        overviewPositionAnimation.frameId = raf(frame);
        return;
      }}
      snapshotParentPositions();
      overviewCy.nodes().positions((node) => {{
        if (node.grabbed() && !node.data("parent") && isOverviewNodeDragging(node.id())) return undefined;
        return liveTarget(node) || undefined;
      }});
      const shouldFit = Boolean(opts && opts.fit);
      const onComplete = opts && typeof opts.onComplete === "function" ? opts.onComplete : null;
      stopOverviewPositionAnimation();
      if (shouldFit) fitOverviewGraph();
      if (onComplete) onComplete();
    }};
    overviewPositionAnimation.frameId = raf(frame);
  }}

  function isEdgeElement(element) {{
    return element.data && element.data.source && element.data.target;
  }}

  function currentDataDiffers(element, targetData) {{
    for (const key of Object.keys(targetData || {{}})) {{
      if (element.data(key) !== targetData[key]) return true;
    }}
    return false;
  }}

  function classText(classes) {{
    return text(classes)
      .split(/\\s+/)
      .filter(Boolean)
      .sort()
      .join(" ");
  }}

  function currentClassesDiffer(element, targetClasses) {{
    return classText(element.classes().join(" ")) !== classText(targetClasses || "");
  }}

  const OVERVIEW_STATE_CLASSES = new Set([
    "dep-center-node",
    "dep-selected-file",
    "dep-selected-edge",
    "dep-emphasis-edge",
    "dep-file-node-muted",
    "dep-base-edge-muted",
    // 選択解除時のフェード用 (transition 定義のみ、色を持たない)。構造クラス比較から除外する。
    "dep-overview-fade"
  ]);
  const OVERVIEW_DEFERRED_STATE_CLASSES = new Set([
    "dep-file-node-muted",
    "dep-base-edge-muted"
  ]);

  function overviewStructuralClasses(classes) {{
    return classText(classes || "")
      .split(/\\s+/)
      .filter((name) => name && !OVERVIEW_STATE_CLASSES.has(name))
      .join(" ");
  }}

  function overviewStateClasses(classes) {{
    return classText(classes || "")
      .split(/\\s+/)
      .filter((name) => name && OVERVIEW_STATE_CLASSES.has(name))
      .join(" ");
  }}

  function overviewImmediateStateClasses(classes) {{
    return classText(classes || "")
      .split(/\\s+/)
      .filter((name) => name && OVERVIEW_STATE_CLASSES.has(name) && !OVERVIEW_DEFERRED_STATE_CLASSES.has(name))
      .join(" ");
  }}

  function overviewDeferredStateClasses(classes) {{
    return classText(classes || "")
      .split(/\\s+/)
      .filter((name) => name && OVERVIEW_DEFERRED_STATE_CLASSES.has(name))
      .join(" ");
  }}

  function overviewPhaseAClasses(targetClasses, currentClasses) {{
    return classText([
      overviewStructuralClasses(targetClasses),
      overviewImmediateStateClasses(targetClasses),
      overviewDeferredStateClasses(currentClasses)
    ].filter(Boolean).join(" "));
  }}

  function overviewStructureElement(element) {{
    const result = {{ data: Object.assign({{}}, element.data || {{}}) }};
    const classes = overviewStructuralClasses(element.classes || "");
    if (classes) result.classes = classes;
    if (element.position) result.position = {{ x: element.position.x, y: element.position.y }};
    return result;
  }}

  function seedOverviewInitialPositions(elements) {{
    const rootNodes = elements.filter((element) => (
      !isEdgeElement(element) && element.data && !element.data.parent
    ));
    if (rootNodes.length === 0) return;
    const columns = Math.ceil(Math.sqrt(rootNodes.length));
    const rows = Math.ceil(rootNodes.length / columns);
    const gap = 220;
    const rootPositions = new Map();
    for (let index = 0; index < rootNodes.length; index++) {{
      const node = rootNodes[index];
      const column = index % columns;
      const row = Math.floor(index / columns);
      const position = {{
        x: (column - (columns - 1) / 2) * gap,
        y: (row - (rows - 1) / 2) * gap
      }};
      node.position = position;
      rootPositions.set(node.data.id, position);
    }}
    const childCounts = new Map();
    for (const element of elements) {{
      if (isEdgeElement(element) || !element.data || !element.data.parent) continue;
      childCounts.set(element.data.parent, (childCounts.get(element.data.parent) || 0) + 1);
    }}
    const childIndexes = new Map();
    for (const element of elements) {{
      if (isEdgeElement(element) || !element.data || !element.data.parent) continue;
      const center = rootPositions.get(element.data.parent);
      if (!center) continue;
      const index = childIndexes.get(element.data.parent) || 0;
      const count = childCounts.get(element.data.parent) || 1;
      childIndexes.set(element.data.parent, index + 1);
      const radius = 72 + Math.min(88, count * 5);
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count;
      element.position = {{
        x: center.x + Math.cos(angle) * radius,
        y: center.y + Math.sin(angle) * radius
      }};
    }}
  }}

  async function seedOverviewInitialPositionsAsync(elements, token) {{
    const rootNodes = elements.filter((element) => (
      !isEdgeElement(element) && element.data && !element.data.parent
    ));
    if (rootNodes.length === 0) return isLatestOverviewSync(token);
    const columns = Math.ceil(Math.sqrt(rootNodes.length));
    const rows = Math.ceil(rootNodes.length / columns);
    const gap = 220;
    const rootPositions = new Map();
    let rootIndex = 0;
    if (!(await processOverviewChunks(rootNodes, token, (chunk) => {{
      for (const node of chunk) {{
        const index = rootIndex;
        rootIndex += 1;
        const column = index % columns;
        const row = Math.floor(index / columns);
        const position = {{
          x: (column - (columns - 1) / 2) * gap,
          y: (row - (rows - 1) / 2) * gap
        }};
        node.position = position;
        rootPositions.set(node.data.id, position);
      }}
    }}))) return false;
    const childCounts = new Map();
    const childElements = [];
    if (!(await processOverviewChunks(elements, token, (chunk) => {{
      for (const element of chunk) {{
        if (isEdgeElement(element) || !element.data || !element.data.parent) continue;
        childElements.push(element);
        childCounts.set(element.data.parent, (childCounts.get(element.data.parent) || 0) + 1);
      }}
    }}))) return false;
    const childIndexes = new Map();
    if (!(await processOverviewChunks(childElements, token, (chunk) => {{
      for (const element of chunk) {{
        const center = rootPositions.get(element.data.parent);
        if (!center) continue;
        const index = childIndexes.get(element.data.parent) || 0;
        const count = childCounts.get(element.data.parent) || 1;
        childIndexes.set(element.data.parent, index + 1);
        const radius = 72 + Math.min(88, count * 5);
        const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count;
        element.position = {{
          x: center.x + Math.cos(angle) * radius,
          y: center.y + Math.sin(angle) * radius
        }};
      }}
    }}))) return false;
    return isLatestOverviewSync(token);
  }}

  function anchorOverviewChildPositions(targetElements, anchorCenters) {{
    if (!anchorCenters || anchorCenters.size === 0) return;
    const childrenByParent = new Map();
    for (const element of targetElements) {{
      if (isEdgeElement(element) || !element.data || !element.data.parent) continue;
      if (!anchorCenters.has(element.data.parent)) continue;
      if (!childrenByParent.has(element.data.parent)) childrenByParent.set(element.data.parent, []);
      childrenByParent.get(element.data.parent).push(element);
    }}
    for (const [parentId, children] of childrenByParent) {{
      const anchor = anchorCenters.get(parentId);
      if (!anchor || children.length === 0) continue;
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;
      for (const child of children) {{
        const position = child.position || anchor;
        minX = Math.min(minX, position.x);
        maxX = Math.max(maxX, position.x);
        minY = Math.min(minY, position.y);
        maxY = Math.max(maxY, position.y);
      }}
      const center = {{ x: (minX + maxX) / 2, y: (minY + maxY) / 2 }};
      const dx = anchor.x - center.x;
      const dy = anchor.y - center.y;
      for (const child of children) {{
        const position = child.position || anchor;
        child.position = {{ x: position.x + dx, y: position.y + dy }};
      }}
    }}
  }}

  function collectOverviewAnchorCenters(previousPositions, targetElements) {{
    const anchorCenters = new Map();
    for (const element of targetElements) {{
      if (isEdgeElement(element) || !element.data || element.data.parent) continue;
      if (previousPositions.has(element.data.id)) {{
        anchorCenters.set(element.data.id, previousPositions.get(element.data.id));
      }}
    }}
    if (selectedFilePath && previousPositions.has(selectedFilePath)) {{
      anchorCenters.set(selectedFilePath, previousPositions.get(selectedFilePath));
    }}
    for (const element of targetElements) {{
      if (isEdgeElement(element) || !element.data || !element.data.parent) continue;
      const parentId = element.data.parent;
      if (previousPositions.has(parentId)) {{
        anchorCenters.set(parentId, previousPositions.get(parentId));
      }}
    }}
    // 非表示から復活したファイルは previousPositions に存在しない。保存した元位置を
    // アンカーに加え、再表示後もレイアウトで流されず元の場所へ戻るようにする。
    for (const [path, position] of overviewRestorePositions) {{
      if (position) anchorCenters.set(path, position);
    }}
    return anchorCenters;
  }}

  function nextOverviewFrame() {{
    return new Promise((resolve) => requestOverviewFrame(resolve));
  }}

  function isLatestOverviewSync(token) {{
    return token === overviewSyncToken;
  }}

  function isOverviewSyncTokenActive(token) {{
    return token === null || token === undefined || isLatestOverviewSync(token);
  }}

  function selectionSignatureHasSelection(signature) {{
    if (!signature) return false;
    try {{
      const values = JSON.parse(signature);
      return Array.isArray(values) && values.some((value) => Boolean(value));
    }} catch (err) {{
      return false;
    }}
  }}

  function targetElementIdSet(targetElements) {{
    return new Set(targetElements.map((element) => element.data.id));
  }}

  function overviewSyncDiffPlan(targetElements) {{
    const targetIds = targetElementIdSet(targetElements);
    const targetById = new Map(targetElements.map((element) => [element.data.id, element]));
    const stale = overviewCy.elements().toArray().filter((element) => !targetIds.has(element.id()));
    const missing = targetElements.filter((element) => !overviewCy.getElementById(element.data.id).length);
    const parentNodes = missing.filter((element) => !isEdgeElement(element) && !element.data.parent);
    const childNodes = missing.filter((element) => !isEdgeElement(element) && element.data.parent);
    const edgeElements = missing.filter(isEdgeElement);
    return {{
      targetById: targetById,
      stale: stale,
      missingOrdered: parentNodes.concat(childNodes, edgeElements)
    }};
  }}

  // Phase B (cola) が実際に必要かを判定する。ファイル位置は anchor で固定されるため、
  // 移動対象がすべて「兄弟を持たない子」であればファイル内配置は自明 (親中心) で、
  // cola を走らせても視覚結果は変わらない。次のいずれかを満たす移動対象があるときのみ
  // レイアウトが要る:
  //   - 親を持たない (ファイル ノード自体の追加/移動 -> 全体配置が要る)
  //   - 親の子数が 2 以上 (兄弟あり -> ファイル内配置に cola が要る)
  function overviewMovingNodesNeedLayout(movingNodeIds, targetElements) {{
    if (!movingNodeIds || movingNodeIds.size === 0) return false;
    const childCountByParent = new Map();
    for (const element of targetElements) {{
      if (isEdgeElement(element) || !element.data || !element.data.parent) continue;
      childCountByParent.set(
        element.data.parent,
        (childCountByParent.get(element.data.parent) || 0) + 1
      );
    }}
    for (const id of movingNodeIds) {{
      const node = overviewCy.getElementById(id);
      const parent = node && node.length ? node.data("parent") : null;
      if (!parent) return true;
      if ((childCountByParent.get(parent) || 0) >= 2) return true;
    }}
    return false;
  }}

  // 100 件単位のチャンクを、1 フレームあたり OVERVIEW_CHUNK_FRAME_BUDGET_MS の時間予算内で
  // 連続処理する。予算を使い切ったら次フレームへ譲る (応答性の担保)。フレームごとに最低
  // 1 チャンクは処理するため、コールバックが予算より重くても必ず前進する。
  // token 失効チェックはチャンクごとに従来どおり行う。
  async function processOverviewChunks(items, token, callback) {{
    let index = 0;
    while (index < items.length) {{
      const frameStart = performance.now();
      while (index < items.length) {{
        if (!isOverviewSyncTokenActive(token)) return false;
        callback(items.slice(index, index + OVERVIEW_SYNC_CHUNK_SIZE));
        index += OVERVIEW_SYNC_CHUNK_SIZE;
        if (performance.now() - frameStart >= OVERVIEW_CHUNK_FRAME_BUDGET_MS) break;
      }}
      // 従来実装は最終チャンク後にもフレーム待機していたため、末尾の待機も維持する
      // (追加直後の描画・スタイル確定タイミングに依存する呼び出し元への互換)。
      await nextOverviewFrame();
    }}
    return isOverviewSyncTokenActive(token);
  }}

  // クリックによるマップ更新を 3 フェーズで反映する。
  //   Phase A: 構造変化 (グループ化・関数ノード・関数間エッジの追加/削除/親移動)、
  //            data 更新、興味対象の強調/非強調、ファイル グループ ノードの座標補正を
  //            フレーム待機なしの単一 overviewCy.batch() で同期反映する。batch が中間状態の
  //            再描画を合体させるため、グラフを隠さずちらつかせず 1 回の連続描画になる。
  //   Phase B: グループ内関数のレイアウトを非同期計算し、アニメーションで反映する。
  //   Phase C: 興味対象外の非強調 (ミュート) を、レイアウト計算開始前までの描画完了後に
  //            全量を単一 batch で同時反映し、クリック応答を阻害しない。
  function syncOverviewElementsCore(targetElements, opts, token) {{
    if (!overviewCy || !isLatestOverviewSync(token)) return false;
    const immediate = Boolean(opts && opts.immediate);
    const onComplete = opts && typeof opts.onComplete === "function" ? opts.onComplete : null;
    const selectionSignature = opts && opts.selectionSignature ? opts.selectionSignature : overviewSelectionSignature();
    // この sync が目指す選択署名を進行中 (pending) として記録する。完了前 (Phase B/C 進行中)
    // でも「マップが現在の選択へ向かっているか」を判定できるようにし、選択が変わったら
    // 確実に再 sync させる。完了時に finishPhaseCIfReady が rendered と一致させる。
    overviewPendingSelectionSignature = selectionSignature;
    const previousPositions = overviewNodePositions();
    const movingNodeIds = new Set();
    const anchorCenters = collectOverviewAnchorCenters(previousPositions, targetElements);
    anchorOverviewChildPositions(targetElements, anchorCenters);
    // 復活させるファイル ノードは元位置に固定したい。movingNodeIds から除外することで
    // ロック対象 (非移動) となり、レイアウトで element.position (復活位置) から流されない。
    const restoredFilePaths = new Set(overviewRestorePositions.keys());
    // 復活位置はこの sync が消費した (要素 position とアンカーへ反映済み)。次回以降に
    // 残さないようクリアする。
    if (overviewRestorePositions.size > 0) overviewRestorePositions.clear();
    const plan = overviewSyncDiffPlan(targetElements);
    // 直前状態は「状態クラスが画面に適用済みの署名」(overviewVisualStateSignature) を使う。
    // rendered は Phase B/C の完了まで更新されないため、seed 窓 (Phase B 進行中) の割り込みでは
    // ミュート適用済みなのに「無選択」を指し、選択解除のフェードが失われる。pending は適用前
    // から目標を指すため、same-tick の連続選択で「未適用なのに適用済み」と誤る。
    const previousSelectionSignature = overviewVisualStateSignature || overviewRenderedSelectionSignature || JSON.stringify(["", "", ""]);
    const previousHasSelection = selectionSignatureHasSelection(previousSelectionSignature);
    const nextHasSelection = selectionSignatureHasSelection(selectionSignature);
    const deferStateClassChanges = previousHasSelection !== nextHasSelection;

    // --- Phase A (同期・単一 batch) ---
    let layoutNeeded = false;
    const dragRevision = overviewDragRevision;
    const deferredClassTargets = [];
    overviewLastClassUpdatePlan = {{
      previousHasSelection,
      nextHasSelection,
      deferStateClassChanges,
      phaseA: 0,
      phaseC: 0
    }};
    const parentsWithRemovedChildren = new Set();
    overviewCy.batch(() => {{
      if (plan.stale.length > 0) {{
        const staleCollection = overviewCy.collection(plan.stale);
        if (staleCollection.nodes().length > 0) layoutNeeded = true;
        staleCollection.nodes().forEach((node) => {{
          const parentId = node.data("parent");
          if (parentId) parentsWithRemovedChildren.add(parentId);
          forgetOverviewNodeRuntimeState(node);
        }});
        overviewCy.remove(staleCollection);
      }}
      if (plan.missingOrdered.length > 0) {{
        const missingElements = plan.missingOrdered
          .map((element) => plan.targetById.get(element.data.id))
          .filter(Boolean)
          .map((target) => {{
            const structureElement = overviewStructureElement(target);
            // 新規追加ノードは初回描画から最終状態 (ミュート等の遅延状態クラス含む) で生成する。
            // 構造クラスのみで生成すると、状態クラス適用までの 1 フレーム、非ミュートの素の見た目が
            // 露出する (再表示時のちらつき)。画面に存在しなかったノードは Phase C 遅延の対象外。
            const fullClasses = classText(target.classes || "");
            if (fullClasses) structureElement.classes = fullClasses;
            return structureElement;
          }});
        for (const element of missingElements) {{
          if (isEdgeElement(element)) continue;
          // 復活ファイル ノードはロックして元位置に固定する。
          if (restoredFilePaths.has(element.data.id)) continue;
          movingNodeIds.add(element.data.id);
        }}
        if (missingElements.length > 0) {{
          overviewCy.add(missingElements);
          layoutNeeded = true;
        }}
      }}
      for (const target of targetElements) {{
        const element = overviewCy.getElementById(target.data.id);
        if (!element.length) continue;
        if (target.data && target.data.parent && element.data("parent") !== target.data.parent) {{
          element.move({{ parent: target.data.parent }});
          movingNodeIds.add(target.data.id);
          layoutNeeded = true;
        }}
        if (currentDataDiffers(element, target.data)) {{
          element.data(target.data);
        }}
        const targetClasses = classText(target.classes || "");
        let phaseAClasses = targetClasses;
        if (deferStateClassChanges) {{
          phaseAClasses = overviewPhaseAClasses(targetClasses, element.classes().join(" "));
          if (classText(phaseAClasses) !== targetClasses) {{
            deferredClassTargets.push({{ id: target.data.id, classes: targetClasses }});
            overviewLastClassUpdatePlan.phaseC += 1;
          }}
        }}
        if (currentClassesDiffer(element, phaseAClasses)) {{
          overviewLastClassUpdatePlan.phaseA += 1;
          element.classes(phaseAClasses);
        }}
      }}
      applyOverviewAnchorCentersToCurrentPositions(anchorCenters);
    }});
    // 遅延なし (選択→選択など) の sync では、状態クラスは上の batch で全量適用済み。
    // 遅延ありの場合は Phase C (startPhaseC) の適用後に更新する。
    if (!deferStateClassChanges) overviewVisualStateSignature = selectionSignature;

    // 中止されたレイアウトで seed のまま取り残された関数を今回の移動対象へ再投入する。直前の
    // レイアウトが操作割り込み (reveal/hide、または seed 表示中の選択変更) で中止されたケースで、
    // 取り残された関数を Phase B で再レイアウトするための再開ロジック。
    // pending は「直前に中止されたレイアウトの移動対象」だけを保持する。割り込み種別 (force 経路か
    // 通常の選択 sync か) に依らず、Phase A 完了後も生存 (可視) している pending ノードは再レイアウト
    // 対象へ戻す。生存しない (stale で削除された) id は pending から取り除く。pending が空の通常 sync
    // では no-op となるため、選択操作の挙動・ノード位置には影響しない。
    // pending の登録は中止時 (stopOverviewActiveLayout)、削除は自然完了時 (finishLayout) と本ループの
    // stale 除去で行う (再投入した関数は新レイアウト完了時に finishLayout が pending から削除する)。
    if (overviewPendingRelayoutNodeIds.size > 0) {{
      for (const id of Array.from(overviewPendingRelayoutNodeIds)) {{
        const node = overviewCy.getElementById(id);
        if (node && node.length) {{
          movingNodeIds.add(id);
        }} else {{
          overviewPendingRelayoutNodeIds.delete(id);
        }}
      }}
      if (movingNodeIds.size > 0) layoutNeeded = true;
    }}

    // stale 除去で子を失った親 (ファイル) の生存子は、除去前の兄弟集合を前提とした配置のまま
    // 取り残される。ファイル選択 (全関数表示) から関数選択へ縮小する遷移で、新規追加が各ファイル
    // 単一子のみだと overviewMovingNodesNeedLayout の単一子スキップにより Phase B 全体が失火し、
    // 残存兄弟が旧座標のまま放置される。兄弟集合が縮小した親の生存子を移動対象へ加えることで、
    // 単一子スキップの前提 (レイアウト結果が自明) が崩れるケースを Phase B の対象に戻す。
    if (parentsWithRemovedChildren.size > 0) {{
      for (const parentId of parentsWithRemovedChildren) {{
        const parent = overviewCy.getElementById(parentId);
        if (!parent || !parent.length) continue;
        parent.children().forEach((child) => movingNodeIds.add(child.id()));
      }}
      if (movingNodeIds.size > 0) layoutNeeded = true;
    }}

    if (!isLatestOverviewSync(token)) return false;

    // --- Phase C 本体 ---
    // レイアウト入力へ影響しないミュート クラスを、レイアウト計算開始前までの描画
    // (Phase A の強調 + seed 配置) が確実に画面へ描画された後に、全量を単一 batch で
    // 同時反映する。完了通知は Phase B と Phase C の双方が終わってから行う。
    let phaseCStarted = false;
    let phaseCClassesDone = false;
    let phaseCLayoutDone = true;
    let phaseCFinalized = false;
    const finishPhaseCIfReady = () => {{
      if (phaseCFinalized || !phaseCClassesDone || !phaseCLayoutDone) return;
      phaseCFinalized = true;
      if (!overviewCy || !isLatestOverviewSync(token)) return;
      if (selectionSignature === overviewSelectionSignature()) {{
        overviewRenderedSelectionSignature = selectionSignature;
        overviewPendingSelectionSignature = selectionSignature;
      }}
      if (onComplete) onComplete();
    }};
    const markPhaseCLayoutDone = () => {{
      phaseCLayoutDone = true;
      finishPhaseCIfReady();
    }};
    const startPhaseC = () => {{
      if (phaseCStarted) return;
      phaseCStarted = true;
      if (!overviewCy || !isLatestOverviewSync(token)) return;
      if (deferredClassTargets.length === 0) {{
        overviewVisualStateSignature = selectionSignature;
        phaseCClassesDone = true;
        finishPhaseCIfReady();
        return;
      }}
      // 操作種別に応じてフェードの扱いを切り替える。
      //   suppressFade (タブ切替・初期化): fadeMode "none" のスタイルで適用して完全即時。
      //     適用後すぐ既定スタイルへ戻す (色が変化しないため補間は走らない)。
      //   選択解除 (選択中 -> 無選択): dep-overview-fade を併せて付与し、ミュート解除も
      //     通常表示へフェードで戻す。フェード完了後にクラスを除去する (タイマー)。
      //   それ以外 (選択変更・選択開始): 既定 "muted" のまま (ミュート化のみフェード)。
      const suppressFade = Boolean(opts && opts.suppressFade);
      const clearingSelection = !suppressFade && previousHasSelection && !nextHasSelection;
      if (suppressFade) {{
        applyOverviewFadeMode("none");
      }}
      overviewCy.batch(() => {{
        for (const target of deferredClassTargets) {{
          const element = overviewCy.getElementById(target.id);
          if (!element.length) continue;
          const nextClasses = clearingSelection
            ? classText((target.classes || "") + " dep-overview-fade")
            : (target.classes || "");
          if (currentClassesDiffer(element, nextClasses)) {{
            // 進行中のスタイル トランジション (ミュート化フェード等) は停止してから
            // クラスを変更する。cytoscape はトランジションをキューイングするため、
            // 停止しないと進行中のフェードが完走してから次の変化が始まり、
            // seed 窓中の選択解除で「ミュート化が続いた後に急に戻る」見た目になる。
            // stop(true, false) は現在色で凍結するため、そこから目標色へ補間される。
            if (clearingSelection) element.stop(true, false);
            element.classes(nextClasses);
          }}
        }}
      }});
      if (suppressFade) {{
        applyOverviewFadeMode("muted");
      }} else if (clearingSelection) {{
        scheduleOverviewFadeClassCleanup();
      }}
      overviewVisualStateSignature = selectionSignature;
      phaseCClassesDone = true;
      finishPhaseCIfReady();
    }};
    // rAF コールバックは「次の描画の直前」に走るため、rAF 1 回では直前フレームの内容が
    // 画面へ描画されたことを保証できない。rAF を 2 回連ねることで間に 1 回の paint が
    // 確実に挟まり、レイアウト計算開始前までの状態の描画完了後に全量適用できる。
    const schedulePhaseCAfterPaint = () => {{
      requestOverviewFrame(() => requestOverviewFrame(startPhaseC));
    }};

    // ドラッグ中はレイアウトを後回しにし、ドラッグ終了後 (handleOverviewNodeFree) に再同期する。
    if (layoutNeeded && (hasOverviewDraggingNodes() || dragRevision !== overviewDragRevision)) {{
      overviewSyncAfterDrag = true;
      startPhaseC();
      return true;
    }}

    // --- Phase B (非同期レイアウト + アニメーション) ---
    // 移動対象がすべて単一子 (兄弟なし) のときはファイル内配置が自明で cola は不要。
    // その場合は Phase B をスキップし、下の「構造変化なし」経路で Phase C を確定する。
    // 単一子は Phase A で親中心へ配置済みのため追加の座標処理は要らないが、pending な
    // ユーザー ドラッグの消費と anchorCenters 反映のため applyOverviewUserMovedPositions は
    // スキップ経路でも 1 回呼ぶ (レイアウトは起動しない)。
    const needsLayout = overviewMovingNodesNeedLayout(movingNodeIds, targetElements);
    if (layoutNeeded && movingNodeIds.size > 0 && needsLayout) {{
      applyOverviewUserMovedPositions(previousPositions, anchorCenters);
      restoreOverviewNodePositions(previousPositions);
      applyOverviewAnchorCentersToCurrentPositions(anchorCenters);
      if (opts) opts.layoutStarted = true;
      phaseCLayoutDone = false;
      runOverviewLayout({{
        movingNodeIds,
        anchorCenters,
        immediate,
        animatePositions: !(opts && opts.hideDuringUpdate),
        instantPositions: Boolean(opts && opts.hideDuringUpdate),
        onComplete: markPhaseCLayoutDone,
        deferPositions: true,
        fullConvergence: true,
        unlockAllDuringLayout: true,
        scopeToVisibleChildren: true,
        syncToken: token
      }});
      schedulePhaseCAfterPaint();
      return true;
    }}

    // 構造変化なし、または移動対象が単一子のみで Phase B スキップ: 興味対象の強調は
    // 反映済み。単一子スキップ時は pending ドラッグの消費と anchorCenters 反映を保つ。
    // ミュートがあれば強調の描画完了後に全量反映し、なければ即座に確定する。
    if (movingNodeIds.size > 0) {{
      applyOverviewUserMovedPositions(previousPositions, anchorCenters);
    }}
    if (deferredClassTargets.length > 0) {{
      schedulePhaseCAfterPaint();
    }} else {{
      startPhaseC();
    }}
    return true;
  }}

  function syncOverviewElements(targetElements, opts) {{
    if (opts) opts.layoutStarted = true;
    runLatestOverviewSync(opts, targetElements);
  }}

  function runLatestOverviewSync(opts, targetElements) {{
    if (!overviewCy) return;
    const token = ++overviewSyncToken;
    ++overviewLayoutToken;
    // 手動レイアウト (relayoutOverviewGraph) の実行中にこの sync が割り込むと、進めた
    // overviewLayoutToken により手動レイアウトの完了/watchdog の解除条件が二度と成立せず、
    // overviewLayoutRunning と操作ロック/controls-inert が孤児化して固着する。差し替える側で
    // 明示的に解放する。
    if (overviewLayoutRunning) setOverviewLayoutRunning(false);
    overviewDeferredPositionAnimation = null;
    stopOverviewPositionAnimation();
    stopOverviewActiveLayout();
    const completed = syncOverviewElementsCore(targetElements || buildOverviewElements(), opts || {{}}, token);
    if (completed && isLatestOverviewSync(token) && opts && opts.onSyncComplete) opts.onSyncComplete();
  }}

  // ファイル (compound) を掴むと、その子 (関数) ノードにも grab/drag が伝播する。親ファイルが
  // 掴まれている子のイベントは、ファイル ドラッグの副作用であって関数の直接操作ではない。これを
  // 関数の割り込みとして扱うと、ファイルを少し動かしただけで進行中の関数レイアウト (cola) が中止され、
  // 関数が seed 位置のまま取り残される。子のイベントは親ファイル側の grab/drag で処理されるため、
  // ここでは無視してよい。
  function isOverviewChildOfGrabbedFile(node) {{
    if (!node || !node.length || !node.data("parent")) return false;
    const parent = node.parent();
    return Boolean(parent && parent.length && parent.grabbed());
  }}

  function handleOverviewNodeGrab(node) {{
    if (isOverviewChildOfGrabbedFile(node)) return;
    // grab (mousedown) はタップでも発火する。ここでドラッグ集合へ登録すると、
    // タップ直後の選択 sync がドラッグ後回し分岐に入り Phase B (関数レイアウト) を
    // 取りこぼす。実際の移動 (drag) があって初めてドラッグ扱いとする。
    if (node && node.length && node.data("parent") && (overviewActiveLayout || overviewPositionAnimation)) {{
      if (overviewActiveLayout) stopOverviewActiveLayout();
      overviewDeferredPositionAnimation = null;
      markOverviewFunctionLayoutInterrupted(node);
      overviewFunctionGrabInterruptedLayout = true;
      stopOverviewPositionAnimation();
      return;
    }}
    // ファイル (ルート) ノードを cola 後の位置アニメーション中に掴んでも止めない。アニメーションは
    // 親ファイルの最新位置に追従して関数を動かすため、ドラッグ中もそのまま継続させる。止めると
    // 完了通知 (onComplete) が失われ、レイアウト結果が採用されないまま固着する。
    if (node && node.length && !node.data("parent")
        && overviewPositionAnimation && overviewPositionAnimation.active) {{
      return;
    }}
    stopOverviewPositionAnimation();
  }}

  function handleOverviewNodeDrag(node) {{
    if (isOverviewChildOfGrabbedFile(node)) return;
    if (node && node.length && node.data("parent") && (overviewActiveLayout || overviewFunctionGrabInterruptedLayout)) {{
      stopOverviewActiveLayout();
      markOverviewFunctionLayoutInterrupted(node);
      overviewSyncAfterDrag = true;
    }}
    rememberOverviewUserMovedPositions(node);
    let added = false;
    for (const id of overviewNodeDragIds(node)) {{
      if (!overviewDraggingNodeIds.has(id)) {{
        overviewDraggingNodeIds.add(id);
        added = true;
      }}
    }}
    if (added) overviewDragRevision += 1;
  }}

  function handleOverviewNodeFree(node) {{
    // 実ドラッグを伴わない free (純タップ) では userMoved を記録しない。タップで記録すると
    // ファイルが「ユーザー移動済み」と誤認され、以後の位置アニメーションが live アンカー経路に
    // 入り、静止した grab を錨とした帰還ループで配置が漂流する。
    if (isOverviewNodeDragging(node)) rememberOverviewUserMovedPositions(node);
    let removed = false;
    for (const id of overviewNodeDragIds(node)) {{
      if (overviewDraggingNodeIds.delete(id)) removed = true;
    }}
    if (removed) overviewDragRevision += 1;
    if (hasOverviewDraggingNodes()) return;
    if (overviewDeferredPositionAnimation && !overviewFunctionGrabInterruptedLayout) {{
      const deferred = overviewDeferredPositionAnimation;
      overviewDeferredPositionAnimation = null;
      overviewSyncAfterDrag = false;
      applyOverviewDeferredDragPositions(deferred);
      animateOverviewPositions(deferred.startPositions, deferred.targetPositions, deferred.opts);
      return;
    }}
    overviewFunctionGrabInterruptedLayout = false;
    overviewDeferredPositionAnimation = null;
    if (!overviewSyncAfterDrag) return;
    overviewSyncAfterDrag = false;
    runLatestOverviewSync({{ relayoutPending: true }}, buildOverviewElements());
  }}

  function overviewSelectionSignature() {{
    return JSON.stringify([selectedId, selectedFilePath, selectedEdgeKey]);
  }}

  function isOverviewRenderedSelectionCurrent() {{
    return (
      overviewCy &&
      overviewCy.elements().length > 0 &&
      overviewRenderedSelectionSignature === overviewSelectionSignature()
    );
  }}

  // 「マップが現在の選択を反映済み、または進行中の sync が現在の選択を対象にしているか」。
  // rendered だけを見る isOverviewRenderedSelectionCurrent と異なり、未完了 (Phase B/C 進行中) の
  // pending も考慮する。これにより、進行中 sync が現在選択と異なる対象を目指している間は、
  // 現在選択が偶然 rendered と一致しても再 sync をスキップせず、状態の食い違いを防ぐ。
  function isOverviewSelectionPendingOrRendered() {{
    return (
      overviewCy &&
      overviewCy.elements().length > 0 &&
      overviewPendingSelectionSignature === overviewSelectionSignature()
    );
  }}

  // 選択操作に応じて、非表示ファイルのうち復活条件を満たすものを再表示する。
  // 復活条件: 選択中ファイル自身、選択中関数の所属ファイル、循環参照の関数選択時に限り
  // 循環グループ各関数の所属ファイル。「関連ファイル」や「関連関数の所属ファイル」だけでは
  // 復活しない。戻り値は復活が発生したか。
  function reconcileHiddenOverviewFiles() {{
    if (hiddenOverviewFiles.size === 0) return false;
    const reveal = new Set();
    if (selectedFilePath && hiddenOverviewFiles.has(selectedFilePath)) {{
      reveal.add(selectedFilePath);
    }}
    if (selectedId) {{
      const fn = byId.get(selectedId);
      if (fn) {{
        if (hiddenOverviewFiles.has(fn.file)) reveal.add(fn.file);
        if (fn.dependencyClass === "cycle") {{
          for (const cycleId of cycleGroupFunctionIds(fn)) {{
            const cycleFn = byId.get(cycleId);
            if (cycleFn && hiddenOverviewFiles.has(cycleFn.file)) reveal.add(cycleFn.file);
          }}
        }}
      }}
    }}
    if (reveal.size === 0) return false;
    for (const path of reveal) {{
      const position = hiddenOverviewFiles.get(path);
      hiddenOverviewFiles.delete(path);
      if (position) overviewRestorePositions.set(path, position);
    }}
    updateOverviewHiddenNotice();
    return true;
  }}

  function forceRenderOverviewGraph() {{
    if (activeTab === "overviewPanel") renderOverviewGraph({{ force: true }});
  }}

  function renderOverviewGraph(opts) {{
    if (!overviewCy) return;
    if (overviewCy.elements().length === 0) {{
      resetOverviewGraph({{ initializeUnselectedFirst: Boolean(opts && opts.initializeUnselectedFirst) }});
      return true;
    }}
    if (!(opts && opts.force) && isOverviewSelectionPendingOrRendered()) {{
      return false;
    }}
    const selectionSignature = overviewSelectionSignature();
    const originalOnComplete = opts && typeof opts.onComplete === "function" ? opts.onComplete : null;
    const renderOpts = Object.assign({{}}, opts || {{}});
    const hideDuringUpdate = Boolean(renderOpts.hideDuringUpdate);
    const viewportBeforeUpdate = hideDuringUpdate ? overviewViewport() : null;
    renderOpts.selectionSignature = selectionSignature;
    renderOpts.hideDuringUpdate = hideDuringUpdate;
    renderOpts.onComplete = () => {{
      if (hideDuringUpdate) {{
        scheduleOverviewRelayoutReveal({{ viewport: viewportBeforeUpdate }});
      }}
      if (originalOnComplete) originalOnComplete();
    }};
    if (hideDuringUpdate) {{
      ++overviewRelayoutRevealToken;
      overviewGraph.classList.add("layout-relayouting");
      setOverviewControlsInert(true);
    }}
    syncOverviewElements(buildOverviewElements(), renderOpts);
    return false;
  }}

  async function resetOverviewGraphAsync(token, opts) {{
    await nextOverviewFrame();
    await nextOverviewFrame();
    if (!overviewCy || !isLatestOverviewSync(token)) return false;
    overviewCy.resize();
    overviewCy.elements().remove();
    await nextOverviewFrame();
    if (!overviewCy || !isLatestOverviewSync(token)) return false;
    const initializeUnselectedFirst = Boolean(opts && opts.initializeUnselectedFirst && selectionSignatureHasSelection(overviewSelectionSignature()));
    const initialSelection = initializeUnselectedFirst ? overviewEmptySelection() : null;
    const elements = await buildOverviewElementsAsync(token, initialSelection);
    if (!elements || !isLatestOverviewSync(token)) return false;
    if (!(await seedOverviewInitialPositionsAsync(elements, token))) return false;
    if (!(await processOverviewChunks(elements, token, (chunk) => {{
      overviewCy.add(chunk);
    }}))) return false;
    if (!overviewCy || !isLatestOverviewSync(token)) return false;
    runOverviewLayout({{
      immediate: true,
      fit: true,
      layoutPasses: 2,
      layoutToken: overviewLayoutToken,
      onComplete: () => {{
        finishOverviewInitialLayout(token, initializeUnselectedFirst);
      }}
    }});
    return true;
  }}

  async function revealOverviewGraphAfterFit(token) {{
    if (!overviewCy || !isLatestOverviewSync(token)) return;
    setOverviewGraphInteractionLocked(false);
    overviewCy.resize();
    fitOverviewGraph();
    await nextOverviewFrame();
    if (!overviewCy || !isLatestOverviewSync(token)) return;
    setOverviewGraphInteractionLocked(false);
    overviewCy.resize();
    fitOverviewGraph();
    overviewRenderedSelectionSignature = overviewSelectionSignature();
    overviewPendingSelectionSignature = overviewRenderedSelectionSignature;
    overviewGraph.classList.remove("layout-initializing");
    overviewGraph.classList.remove("layout-relayouting");
    setOverviewControlsInert(false);
  }}

  function finishOverviewInitialLayout(token, initializeUnselectedFirst) {{
    if (!overviewCy || !isLatestOverviewSync(token)) return;
    if (!initializeUnselectedFirst) {{
      revealOverviewGraphAfterFit(token);
      return;
    }}
    overviewGraph.classList.add("layout-relayouting");
    const renderOpts = {{
      immediate: false,
      hideDuringUpdate: false,
      selectionSignature: overviewSelectionSignature(),
      // 初期化はユーザーのクリック操作ではないため、状態クラスのフェードを行わない。
      suppressFade: true,
      onComplete: () => {{
        revealOverviewGraphAfterFit(token);
      }}
    }};
    syncOverviewElementsCore(buildOverviewElements(), renderOpts, token);
  }}

  function resetOverviewGraph(opts) {{
    if (!overviewCy) return;
    // 初期化では非表示を解除し、全ファイルを元の状態へ戻す。
    hiddenOverviewFiles.clear();
    overviewRestorePositions.clear();
    overviewPendingRelayoutNodeIds.clear();
    updateOverviewHiddenNotice();
    const token = ++overviewSyncToken;
    ++overviewLayoutToken;
    // 手動レイアウト実行中の初期化でも実行状態が孤児化しないよう、自前の再ロック前に解放する。
    if (overviewLayoutRunning) setOverviewLayoutRunning(false);
    stopOverviewActiveLayout();
    overviewRenderedSelectionSignature = null;
    overviewPendingSelectionSignature = null;
    overviewVisualStateSignature = null;
    overviewGraph.classList.add("layout-initializing");
    setOverviewControlsInert(true);
    setOverviewGraphInteractionLocked(true);
    ++overviewRelayoutRevealToken;
    overviewLayoutInitialized = false;
    stopOverviewPositionAnimation();
    resetOverviewGraphAsync(token, opts || {{}});
  }}

  function abortOverviewInitializationOnTabLeave(previousTab, nextTab) {{
    if (previousTab !== "overviewPanel" || nextTab === "overviewPanel") return;
    if (!overviewCy || !overviewGraph || !overviewGraph.classList.contains("layout-initializing")) return;
    ++overviewSyncToken;
    ++overviewLayoutToken;
    ++overviewRelayoutRevealToken;
    stopOverviewActiveLayout();
    stopOverviewPositionAnimation();
    setOverviewLayoutRunning(false);
    overviewCy.elements().remove();
    overviewRenderedSelectionSignature = null;
    overviewPendingSelectionSignature = null;
    overviewVisualStateSignature = null;
    overviewLayoutInitialized = false;
    overviewPendingRelayoutNodeIds.clear();
    setOverviewControlsInert(true);
    setOverviewGraphInteractionLocked(true);
  }}

  function initOverviewGraph() {{
    if (overviewCy || !overviewGraph) return;
    if (typeof cytoscape !== "function") {{
      graphUnavailable(overviewGraph, overviewDetail);
      return;
    }}
    overviewCy = cytoscape({{
      container: overviewGraph,
      elements: [],
      style: graphStyle(),
      wheelSensitivity: 0.18
    }});
    overviewCy.on("tap", "node", (event) => {{
      const id = event.target.id();
      if (functionsByFile.has(id)) {{
        selectFile(id);
      }} else {{
        selectFunction(id);
      }}
    }});
    overviewCy.on("tap", "edge", (event) => {{
      const edge = event.target;
      if (edge.data("kind") !== "file-edge") return;
      selectOverviewEdge(edge.id());
    }});
    overviewCy.on("tap", (event) => {{
      if (event.target !== overviewCy) return;
      if (isOverviewBackgroundTapSuppressed()) return;
      clearOverviewSelection();
    }});
    overviewCy.on("grab", "node", (event) => {{
      handleOverviewNodeGrab(event.target);
    }});
    overviewCy.on("drag", "node", (event) => {{
      handleOverviewNodeDrag(event.target);
    }});
    overviewCy.on("free", "node", (event) => {{
      handleOverviewNodeFree(event.target);
    }});
    function overviewCxtMenuCoords(event) {{
      const originalEvent = event.originalEvent || {{}};
      if (originalEvent.preventDefault) originalEvent.preventDefault();
      let clientX = Number(originalEvent.clientX);
      let clientY = Number(originalEvent.clientY);
      if ((!Number.isFinite(clientX) || !Number.isFinite(clientY)) && event.renderedPosition) {{
        const rect = overviewGraph.getBoundingClientRect();
        clientX = rect.left + event.renderedPosition.x;
        clientY = rect.top + event.renderedPosition.y;
      }}
      return {{ clientX, clientY }};
    }}
    overviewCy.on("cxttap", (event) => {{
      if (event.target !== overviewCy) return;
      const coords = overviewCxtMenuCoords(event);
      if (Number.isFinite(coords.clientX) && Number.isFinite(coords.clientY)) {{
        overviewMenuTargetFile = "";
        showOverviewGraphMenu(coords.clientX, coords.clientY, "background");
      }}
    }});
    overviewCy.on("cxttap", "node.dep-file-node", (event) => {{
      const coords = overviewCxtMenuCoords(event);
      if (Number.isFinite(coords.clientX) && Number.isFinite(coords.clientY)) {{
        overviewMenuTargetFile = event.target.id();
        showOverviewGraphMenu(coords.clientX, coords.clientY, "node");
      }}
    }});
    overviewGraph.addEventListener("contextmenu", (event) => {{
      event.preventDefault();
    }});
    overviewGraph.addEventListener("mousedown", (event) => {{
      if (event.button !== 1) return;
      event.preventDefault();
    }});
    overviewGraph.addEventListener("auxclick", (event) => {{
      if (event.button !== 1) return;
      event.preventDefault();
      fitOverviewGraph();
    }});
  }}

  function refreshActiveGraph(opts) {{
    if (activeTab === "overviewPanel") {{
      initOverviewGraph();
      // 他タブで選択変更後に全体マップへ遷移した場合も復活条件を評価する。
      const revealed = reconcileHiddenOverviewFiles();
      // 既にレイアウト済みの全体マップへ別タブから戻る場合は初期化用 immediate を落とすが、
      // マップは最終断面まで隠したまま非アニメーションで選択を反映する。
      // 未初期化 (要素が空) のときだけ immediate のまま resetOverviewGraph へ渡す。
      const alreadyLaidOut = Boolean(overviewLayoutInitialized && overviewCy && overviewCy.elements().length > 0);
      const requestedImmediate = Boolean(opts && opts.immediate);
      const immediate = requestedImmediate && !alreadyLaidOut;
      const hideDuringUpdate = requestedImmediate;
      if (!revealed && immediate && isOverviewSelectionPendingOrRendered()) {{
        return;
      }}
      if (immediate && overviewCy && overviewCy.elements().length > 0) {{
        ++overviewRelayoutRevealToken;
        overviewGraph.classList.add("layout-relayouting");
        setOverviewControlsInert(true);
      }}
      const requestFrame = window.requestAnimationFrame || window.webkitRequestAnimationFrame || ((callback) => window.setTimeout(() => callback(Date.now()), 16));
      const finishImmediateRefresh = () => {{
        if (!immediate) return;
        if (activeTab === "overviewPanel" && !isOverviewRenderedSelectionCurrent()) {{
          requestFrame(finishImmediateRefresh);
          return;
        }}
        scheduleOverviewRelayoutReveal();
      }};
      const refresh = () => {{
        if (activeTab !== "overviewPanel") {{
          finishImmediateRefresh();
          return;
        }}
        const renderOpts = {{ immediate, hideDuringUpdate, initializeUnselectedFirst: immediate && selectionSignatureHasSelection(overviewSelectionSignature()), onComplete: finishImmediateRefresh, selectionSignature: overviewSelectionSignature(), force: revealed, suppressFade: true }};
        const resetStarted = renderOverviewGraph(renderOpts);
        if (overviewCy && !resetStarted && !renderOpts.layoutStarted) {{
          finishImmediateRefresh();
        }}
      }};
      if (immediate) {{
        requestFrame(() => requestFrame(refresh));
      }} else {{
        requestFrame(refresh);
      }}
    }}
  }}

  function fillOptions() {{
    const levels = Array.from(new Set(functions.map(levelText))).sort((a, b) => {{
      if (a === "cycle") return 1;
      if (b === "cycle") return -1;
      return Number(a) - Number(b);
    }});
    for (const level of levels) {{
      const option = document.createElement("option");
      option.value = level;
      option.textContent = "level " + level;
      levelFilter.appendChild(option);
      fileLevelFilter.appendChild(option.cloneNode(true));
    }}
    for (const klass of Array.from(new Set(functions.map((fn) => fn.dependencyClass))).sort()) {{
      const option = document.createElement("option");
      option.value = klass;
      option.textContent = klass;
      classFilter.appendChild(option);
      fileClassFilter.appendChild(option.cloneNode(true));
    }}
    for (const area of Array.from(new Set(functions.map((fn) => fn.sourceArea))).sort()) {{
      const option = document.createElement("option");
      option.value = area;
      option.textContent = area;
      areaFilter.appendChild(option);
      fileAreaFilter.appendChild(option.cloneNode(true));
    }}
    for (const file of Array.from(new Set(functions.map((fn) => fn.file))).sort()) {{
      const option = document.createElement("option");
      option.value = file;
      option.textContent = file;
      fileFilter.appendChild(option);
    }}
  }}

  function matches(fn) {{
    const query = search.value.trim().toLowerCase();
    if (query && !(fn.name.toLowerCase().includes(query) || fn.file.toLowerCase().includes(query))) return false;
    if (levelFilter.value && levelText(fn) !== levelFilter.value) return false;
    if (classFilter.value && fn.dependencyClass !== classFilter.value) return false;
    if (exportFilter.value && (fn.isExported ? "yes" : "no") !== exportFilter.value) return false;
    if (staticFilter.value && (fn.isStatic ? "yes" : "no") !== staticFilter.value) return false;
    if (areaFilter.value && fn.sourceArea !== areaFilter.value) return false;
    if (fileFilter.value && fn.file !== fileFilter.value) return false;
    return true;
  }}

  function matchesFile(file) {{
    const query = fileSearch.value.trim().toLowerCase();
    const searchable = [
      file.path,
      file.brief,
      file.dominantArea,
      fileLevelText(file),
      fileClassText(file),
      fileAreasText(file)
    ].join(" ").toLowerCase();
    if (query && !searchable.includes(query)) return false;
    if (fileLevelFilter.value && !mapKeys(file.levels).includes(fileLevelFilter.value)) return false;
    if (fileClassFilter.value && !mapKeys(file.classes).includes(fileClassFilter.value)) return false;
    if (fileExportFilter.value && (Number(file.exportCount || 0) > 0 ? "yes" : "no") !== fileExportFilter.value) return false;
    if (fileStaticFilter.value && (Number(file.staticCount || 0) > 0 ? "yes" : "no") !== fileStaticFilter.value) return false;
    if (fileAreaFilter.value && !mapKeys(file.areas).includes(fileAreaFilter.value)) return false;
    return true;
  }}

  function selectedVisible() {{
    if (!selectedId) return true;
    const fn = byId.get(selectedId);
    return !fn || matches(fn);
  }}

  function selectedFileVisible() {{
    if (!selectedFilePath) return true;
    const file = fileByPath.get(selectedFilePath);
    return !file || matchesFile(file);
  }}

  function renderNotice() {{
    filterNotice.classList.toggle("visible", !selectedVisible());
  }}

  function renderFileNotice() {{
    fileFilterNotice.classList.toggle("visible", !selectedFileVisible());
  }}

  function centerSelectedRow(selectedRow) {{
    const wrap = selectedRow.closest(".dep-table-wrap");
    if (!wrap || wrap.clientHeight === 0) return false;
    const wrapRect = wrap.getBoundingClientRect();
    const rowRect = selectedRow.getBoundingClientRect();
    const currentRowCenter = rowRect.top + rowRect.height / 2;
    const targetCenter = wrapRect.top + wrap.clientHeight / 2;
    wrap.scrollTop += currentRowCenter - targetCenter;
    return true;
  }}

  function syncSelectedRowScroll(forceScroll) {{
    const selectedRow = rows.querySelector("tr.selected");
    if (!selectedRow) {{
      previousSelectedRowVisible = false;
      return;
    }}
    if (forceScroll || !previousSelectedRowVisible) {{
      if (!centerSelectedRow(selectedRow)) {{
        pendingFunctionListScroll = true;
        return;
      }}
      pendingFunctionListScroll = false;
    }}
    previousSelectedRowVisible = true;
  }}

  function syncSelectedFileRowScroll(forceScroll) {{
    const selectedRow = fileRows.querySelector("tr.selected");
    if (!selectedRow) {{
      previousSelectedFileRowVisible = false;
      return;
    }}
    if (forceScroll || !previousSelectedFileRowVisible) {{
      if (!centerSelectedRow(selectedRow)) {{
        pendingFileListScroll = true;
        return;
      }}
      pendingFileListScroll = false;
    }}
    previousSelectedFileRowVisible = true;
  }}

  function renderRows(opts) {{
    const fragment = document.createDocumentFragment();
    for (const fn of sortedFunctions(functions.filter(matches))) {{
      const tr = document.createElement("tr");
      tr.setAttribute("data-function-row-id", fn.id);
      if (fn.id === selectedId) tr.className = "selected";
      tr.innerHTML =
        "<td class=\\"dep-num\\">" + escapeHtml(levelText(fn)) + "</td>" +
        "<td><span class=\\"badge " + escapeHtml(fn.dependencyClass) + "\\">" + escapeHtml(fn.dependencyClass) + "</span></td>" +
        "<td>" + (fn.isExported ? "yes" : "") + "</td>" +
        "<td>" + (fn.isStatic ? "yes" : "") + "</td>" +
        "<td>" + areaBadge(fn.sourceArea) + "</td>" +
        "<td>" + escapeHtml(fn.name) + "</td>" +
        "<td class=\\"dep-file\\" title=\\"" + escapeHtml(fn.file) + "\\">" + escapeHtml(fn.file) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(fn.inScopeCalleeCount) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(fn.inScopeCallerCount) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(fn.crossFileCalleeCount) + "</td>";
      fragment.appendChild(tr);
    }}
    rows.replaceChildren(fragment);
    ensureFunctionRowSelectionRendered();
    renderNotice();
    renderSortMarks();
    syncSelectedRowScroll(Boolean(opts && opts.forceScroll));
  }}

  function renderFileRows(opts) {{
    const fragment = document.createDocumentFragment();
    for (const file of sortedFiles(files.filter(matchesFile))) {{
      const tr = document.createElement("tr");
      tr.setAttribute("data-file-row-path", file.path);
      if (file.path === selectedFilePath) tr.className = "selected";
      tr.innerHTML =
        "<td>" + areaBadge(file.dominantArea || "") + "</td>" +
        "<td class=\\"dep-file\\" title=\\"" + escapeHtml(file.path) + "\\">" + escapeHtml(file.path) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(file.functionCount || 0) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(file.exportCount || 0) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(file.staticCount || 0) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(file.edgeCount || 0) + "</td>" +
        "<td>" + escapeHtml(fileLevelText(file)) + "</td>" +
        "<td>" + escapeHtml(fileClassText(file)) + "</td>" +
        "<td>" + escapeHtml(fileAreasText(file)) + "</td>";
      fragment.appendChild(tr);
    }}
    fileRows.replaceChildren(fragment);
    ensureFileRowSelectionRendered();
    renderFileNotice();
    renderFileSortMarks();
    syncSelectedFileRowScroll(Boolean(opts && opts.forceScroll));
  }}

  function ensureFunctionRowSelectionRendered() {{
    for (const row of rows.querySelectorAll("[data-function-row-id]")) {{
      row.classList.toggle("selected", row.getAttribute("data-function-row-id") === selectedId);
    }}
  }}

  function ensureFileRowSelectionRendered() {{
    for (const row of fileRows.querySelectorAll("[data-file-row-path]")) {{
      row.classList.toggle("selected", row.getAttribute("data-file-row-path") === selectedFilePath);
    }}
  }}

  function linkFor(fn, label, source) {{
    const url = source ? fn.sourceUrl : fn.htmlUrl;
    if (!url) return "";
    const target = source ? "doxyfw-dependency-source" : "doxyfw-dependency-doxygen";
    return "<a href=\\"" + escapeHtml(url) + "\\" target=\\"" + target + "\\">" + escapeHtml(label) + "</a>";
  }}

  function neighborList(ids, emptyText) {{
    if (!ids || ids.length === 0) return "<p class=\\"dep-empty\\">" + emptyText + "</p>";
    const items = ids
      .map((id) => byId.get(id))
      .filter(Boolean)
      .sort((a, b) => a.file.localeCompare(b.file) || a.name.localeCompare(b.name))
      .map((fn) => "<li><button type=\\"button\\" class=\\"dep-neighbor-button\\" data-function-id=\\"" + escapeHtml(fn.id) + "\\">" + escapeHtml(fn.name) + "</button> <small>" + escapeHtml(fn.file) + "</small></li>");
    return "<ul>" + items.join("") + "</ul>";
  }}

  function cycleGroupFunctionIds(fn) {{
    if (!fn || fn.dependencyClass !== "cycle" || !fn.sccId) return [];
    const scc = sccById.get(fn.sccId);
    if (!scc || !Array.isArray(scc.functions)) return [];
    return scc.functions;
  }}

  function cycleGroupSection(fn) {{
    const ids = cycleGroupFunctionIds(fn);
    if (ids.length === 0) return "";
    return "<section><strong>循環グループ</strong>" + neighborList(ids, "同じ循環グループの関数はありません。") + "</section>";
  }}

  function externalCalleeList(externalCallees) {{
    if (!externalCallees || externalCallees.length === 0) return "";
    const items = externalCallees.map((ec) =>
      "<li><span class=\\"dep-external-callee\\">" + escapeHtml(ec.name) + "</span></li>"
    );
    return "<ul>" + items.join("") + "</ul>";
  }}

  function bindDetailActions() {{
    for (const button of detail.querySelectorAll("[data-function-id]")) {{
      button.addEventListener("click", () => selectFunction(button.getAttribute("data-function-id")));
    }}
    for (const link of detail.querySelectorAll("[data-file-path]")) {{
      link.addEventListener("click", (event) => {{
        event.preventDefault();
        selectFile(link.getAttribute("data-file-path"), {{ activateFileList: true }});
      }});
    }}
  }}

  function renderDetail(fn) {{
    if (!fn) {{
      detail.innerHTML = "<p class=\\"dep-empty\\">関数を選択してください。</p>";
      return;
    }}
    detail.innerHTML =
      "<h2>" + escapeHtml(fn.name) + "</h2>" +
      (fn.brief ? "<p class=\\"dep-brief\\">" + escapeHtml(fn.brief) + "</p>" : "") +
      "<dl>" +
      "<dt>分類</dt><dd><span class=\\"badge " + escapeHtml(fn.dependencyClass) + "\\">" + escapeHtml(fn.dependencyClass) + "</span></dd>" +
      "<dt>level</dt><dd>" + escapeHtml(levelText(fn)) + "</dd>" +
      "<dt>rank</dt><dd>" + escapeHtml(fn.dependencyRank) + "</dd>" +
      "<dt>depth</dt><dd>" + escapeHtml(fn.dependencyDepth === null || fn.dependencyDepth === undefined ? "cycle" : fn.dependencyDepth) + "</dd>" +
      "<dt>領域</dt><dd>" + areaBadge(fn.sourceArea) + "</dd>" +
      "<dt>呼び出し種別</dt><dd>" + escapeHtml(fn.dominantCallKind) + "</dd>" +
      "<dt>export</dt><dd>" + (fn.isExported ? "yes" : "no") + "</dd>" +
      "<dt>static</dt><dd>" + (fn.isStatic ? "yes" : "no") + "</dd>" +
      "<dt>ファイル</dt><dd>" + fileSelectionLink(fn.file, fn.file) + "</dd>" +
      "<dt>行</dt><dd>" + escapeHtml(fn.line) + "</dd>" +
      "<dt>リンク</dt><dd>" + [linkFor(fn, "Doxygen", false), linkFor(fn, "source", true)].filter(Boolean).join(" / ") + "</dd>" +
      "</dl>" +
      "<div class=\\"dep-neighbors\\">" +
      "<section><strong>呼び出し先 (ライブラリ内)</strong>" + neighborList(callees.get(fn.id), "対象範囲内の呼び出し先はありません。") + "</section>" +
      (fn.externalCallees && fn.externalCallees.length > 0 ? "<section><strong>呼び出し先 (外部)</strong>" + externalCalleeList(fn.externalCallees) + "</section>" : "") +
      "<section><strong>呼び出し元</strong>" + neighborList(callers.get(fn.id), "対象範囲内の呼び出し元はありません。") + "</section>" +
      cycleGroupSection(fn) +
      "</div>";
    bindDetailActions();
  }}

  function selectFunction(id, opts) {{
    const fn = byId.get(id);
    if (!fn) return;
    if (scheduleRenderRows) scheduleRenderRows.cancel();
    if (id === selectedId && !selectedEdgeKey) {{
      ensureFunctionRowSelectionRendered();
      renderNotice();
      if (reconcileHiddenOverviewFiles()) forceRenderOverviewGraph();
      if (opts && opts.activateFunctionList) {{
        pendingFunctionListScroll = true;
        activateTab("functionListPanel");
      }}
      return;
    }}
    const fromTableRow = Boolean(opts && opts.fromTableRow);
    if (fromTableRow) previousSelectedRowVisible = true;
    selectedId = id;
    selectedFilePath = fn.file;
    selectedEdgeKey = "";
    reconcileHiddenOverviewFiles();
    renderDetail(fn);
    renderFileDetail(fn.file);
    renderOverviewFunctionDetail(fn);
    renderRows({{ forceScroll: !fromTableRow }});
    renderFileRows({{ forceScroll: true }});
    if (opts && opts.activateFunctionList) {{
      activateTab("functionListPanel");
    }}
    if (activeTab === "overviewPanel") {{
      renderOverviewGraph();
    }}
    updateUrlHashFromState();
  }}

  function selectFile(path, opts) {{
    if (scheduleRenderFileRows) scheduleRenderFileRows.cancel();
    if (path === selectedFilePath && selectedId === "" && selectedEdgeKey === "") {{
      ensureFileRowSelectionRendered();
      renderFileNotice();
      if (reconcileHiddenOverviewFiles()) forceRenderOverviewGraph();
      if (opts && opts.activateFileList) {{
        pendingFileListScroll = true;
        activateTab("fileListPanel");
      }}
      return;
    }}
    const fromFileRow = Boolean(opts && opts.fromFileRow);
    if (fromFileRow) previousSelectedFileRowVisible = true;
    selectedFilePath = path;
    selectedId = "";
    selectedEdgeKey = "";
    reconcileHiddenOverviewFiles();
    renderDetail(null);
    renderFileDetail(path);
    renderOverviewDetail(path);
    renderRows({{ forceScroll: false }});
    renderFileRows({{ forceScroll: !fromFileRow }});
    if (opts && opts.activateFileList) {{
      activateTab("fileListPanel");
    }}
    if (activeTab === "overviewPanel") {{
      renderOverviewGraph();
    }}
    updateUrlHashFromState();
  }}

  function selectOverviewEdge(edgeKey) {{
    if (!edgeKey) return;
    selectedId = "";
    selectedFilePath = "";
    selectedEdgeKey = edgeKey;
    renderDetail(null);
    renderFileDetail("");
    renderOverviewEdgeDetail(edgeKey);
    renderRows({{ forceScroll: false }});
    renderFileRows({{ forceScroll: false }});
    if (activeTab === "overviewPanel") {{
      renderOverviewGraph();
    }}
    updateUrlHashFromState();
  }}

  function clearOverviewSelection() {{
    selectedId = "";
    selectedFilePath = "";
    selectedEdgeKey = "";
    renderDetail(null);
    renderFileDetail("");
    overviewDetail.innerHTML = "<p class=\\"dep-empty\\">ファイルまたは関数を選択してください。</p>";
    renderRows({{ forceScroll: false }});
    renderFileRows({{ forceScroll: false }});
    if (activeTab === "overviewPanel") {{
      renderOverviewGraph();
    }}
    updateUrlHashFromState();
  }}

  function clearSelection() {{
    selectedId = "";
    selectedFilePath = "";
    selectedEdgeKey = "";
    renderDetail(null);
    renderFileDetail("");
    overviewDetail.innerHTML = "<p class=\\"dep-empty\\">ファイルまたは関数を選択してください。</p>";
    renderRows({{ forceScroll: false }});
    renderFileRows({{ forceScroll: false }});
    if (activeTab === "overviewPanel") {{
      resetOverviewGraph();
    }}
    updateUrlHashFromState();
  }}

  function debounce(callback, delayMs) {{
    let timer = null;
    const debounced = () => {{
      if (timer !== null) window.clearTimeout(timer);
      timer = window.setTimeout(() => {{
        timer = null;
        callback();
      }}, delayMs);
    }};
    debounced.cancel = () => {{
      if (timer === null) return;
      window.clearTimeout(timer);
      timer = null;
    }};
    return debounced;
  }}

  addMetric("関数", data.summary.functionCount || 0);
  addMetric("呼び出し関係", data.summary.edgeCount || 0);
  addMetric("ファイル", data.summary.fileCount || 0);
  addMetric("export", data.summary.exportCount || 0);
  addMetric("static", data.summary.staticCount || 0);
  addMetric("leaf", data.summary.leafCount || 0);
  addMetric("循環グループ", data.summary.cycleGroupCount || 0);
  fillOptions();
  renderRows();
  renderFileRows();
  const scheduleRenderRows = debounce(() => renderRows(), 80);
  const scheduleRenderFileRows = debounce(() => renderFileRows(), 80);
  applyStateFromUrlHash();
  window.addEventListener("hashchange", () => {{
    if (applyingUrlHash) return;
    if (window.location.hash === currentUrlHashString()) return;
    applyStateFromUrlHash();
  }});
  const rowSelectEventName = window.PointerEvent ? "pointerdown" : "mousedown";
  rows.addEventListener(rowSelectEventName, (event) => {{
    const row = event.target.closest("[data-function-row-id]");
    if (!row || !rows.contains(row)) return;
    selectFunction(row.getAttribute("data-function-row-id"), {{ fromTableRow: true }});
  }});
  fileRows.addEventListener(rowSelectEventName, (event) => {{
    const row = event.target.closest("[data-file-row-path]");
    if (!row || !fileRows.contains(row)) return;
    selectFile(row.getAttribute("data-file-row-path"), {{ fromFileRow: true }});
  }});
  for (const control of [search, levelFilter, classFilter, exportFilter, staticFilter, areaFilter, fileFilter]) {{
    control.addEventListener("input", scheduleRenderRows);
    control.addEventListener("change", scheduleRenderRows);
  }}
  for (const control of [fileSearch, fileLevelFilter, fileClassFilter, fileExportFilter, fileStaticFilter, fileAreaFilter]) {{
    control.addEventListener("input", scheduleRenderFileRows);
    control.addEventListener("change", scheduleRenderFileRows);
  }}
  for (const button of sortButtons) {{
    button.addEventListener("click", () => {{
      const key = button.getAttribute("data-sort-key");
      if (sortState.key === key) {{
        sortState = {{ key, direction: sortState.direction === "asc" ? "desc" : "asc" }};
      }} else {{
        sortState = {{ key, direction: "asc" }};
      }}
      renderRows();
    }});
  }}
  for (const button of fileSortButtons) {{
    button.addEventListener("click", () => {{
      const key = button.getAttribute("data-file-sort-key");
      if (fileSortState.key === key) {{
        fileSortState = {{ key, direction: fileSortState.direction === "asc" ? "desc" : "asc" }};
      }} else {{
        fileSortState = {{ key, direction: "asc" }};
      }}
      renderFileRows();
    }});
  }}
  for (const button of tabButtons) {{
    button.addEventListener("click", () => {{
      activateTab(button.getAttribute("data-tab-target"));
    }});
  }}
  overviewFit.addEventListener("click", () => {{
    fitOverviewGraph();
  }});
  overviewRelayout.addEventListener("click", () => {{
    relayoutOverviewGraph();
  }});
  overviewReset.addEventListener("click", () => {{
    resetOverviewGraphState();
  }});
  if (overviewHiddenNotice) {{
    for (const eventName of ["pointerdown", "mousedown", "touchstart", "pointerup", "mouseup"]) {{
      overviewHiddenNotice.addEventListener(eventName, (event) => {{
        event.stopPropagation();
      }});
    }}
    overviewHiddenNotice.addEventListener("click", (event) => {{
      event.preventDefault();
      event.stopPropagation();
      suppressOverviewBackgroundTap();
      revealAllOverviewFiles();
    }});
  }}
  if (themeToggle) {{
    updateThemeToggle();
    themeToggle.addEventListener("click", () => {{
      applyTheme(currentTheme === "dark" ? "light" : "dark", true);
    }});
  }}
  if (overviewGraphMenu) {{
    overviewGraphMenu.addEventListener("contextmenu", (event) => {{
      event.preventDefault();
    }});
    overviewGraphMenu.addEventListener("click", (event) => {{
      const button = event.target.closest("button");
      if (!button) return;
      const scope = button.getAttribute("data-svg-scope");
      const pngScope = button.getAttribute("data-png-scope");
      const callerDepth = button.getAttribute("data-caller-depth");
      const calleeDepth = button.getAttribute("data-callee-depth");
      if (scope) {{
        downloadOverviewSvg(scope);
      }} else if (pngScope) {{
        downloadOverviewPng(pngScope);
      }} else if (callerDepth !== null) {{
        setOverviewDepth("caller", callerDepth);
      }} else if (calleeDepth !== null) {{
        setOverviewDepth("callee", calleeDepth);
      }} else {{
        if (!handleOverviewGraphMenuAction(button.getAttribute("data-action"))) return;
      }}
      hideOverviewGraphMenu();
    }});
    document.addEventListener("click", (event) => {{
      if (!overviewGraphMenu.contains(event.target)) hideOverviewGraphMenu();
    }});
    document.addEventListener("keydown", (event) => {{
      if (event.key === "Escape") hideOverviewGraphMenu();
    }});
    window.addEventListener("resize", hideOverviewGraphMenu);
    window.addEventListener("scroll", hideOverviewGraphMenu, true);
  }}
  function clearFunctionFilters() {{
    search.value = "";
    levelFilter.value = "";
    classFilter.value = "";
    exportFilter.value = "";
    staticFilter.value = "";
    areaFilter.value = "";
    fileFilter.value = "";
    renderRows();
  }}

  function clearFileListFilters() {{
    fileSearch.value = "";
    fileLevelFilter.value = "";
    fileClassFilter.value = "";
    fileExportFilter.value = "";
    fileStaticFilter.value = "";
    fileAreaFilter.value = "";
    renderFileRows();
  }}

  clearFilters.addEventListener("click", clearFunctionFilters);
  clearHiddenFunctionFilters.addEventListener("click", clearFunctionFilters);
  clearFileFilters.addEventListener("click", clearFileListFilters);
  clearHiddenFileFilters.addEventListener("click", clearFileListFilters);

  function closeDownloadMenus(exceptMenu) {{
    for (const menu of document.querySelectorAll(".dep-download-menu.open")) {{
      if (menu === exceptMenu) continue;
      menu.classList.remove("open");
      const button = menu.querySelector(".dep-download-menu-button");
      const items = menu.querySelector(".dep-download-menu-items");
      if (button) button.setAttribute("aria-expanded", "false");
      if (items) items.hidden = true;
    }}
  }}

  for (const menu of document.querySelectorAll(".dep-download-menu")) {{
    const button = menu.querySelector(".dep-download-menu-button");
    const items = menu.querySelector(".dep-download-menu-items");
    if (!button || !items) continue;
    button.addEventListener("click", () => {{
      const willOpen = !menu.classList.contains("open");
      closeDownloadMenus(menu);
      menu.classList.toggle("open", willOpen);
      button.setAttribute("aria-expanded", willOpen ? "true" : "false");
      items.hidden = !willOpen;
    }});
  }}

  document.addEventListener("click", (event) => {{
    if (event.target.closest(".dep-download-menu")) return;
    closeDownloadMenus(null);
  }});

  const FUNCTION_CSV_FIELDS = [
    "dependencyLevel",
    "dependencyRank",
    "dependencyDepth",
    "dependencyClass",
    "sourceArea",
    "maxCalleeArea",
    "dominantCallKind",
    "isExported",
    "isStatic",
    "name",
    "file",
    "line",
    "inScopeCalleeCount",
    "inScopeCallerCount",
    "sameFileCalleeCount",
    "crossFileCalleeCount",
    "sccId",
    "cycleGroupSize",
    "id",
    "htmlUrl",
    "sourceUrl",
    "brief"
  ];

  const FILE_CSV_FIELDS = [
    "path",
    "functionCount",
    "exportCount",
    "staticCount",
    "edgeCount",
    "dominantArea",
    "levels",
    "classes",
    "areas",
    "brief",
    "htmlUrl",
    "sourceUrl"
  ];

  function stableJsonText(value) {{
    const source = value && typeof value === "object" && !Array.isArray(value) ? value : {{}};
    const sorted = {{}};
    for (const key of Object.keys(source).sort()) {{
      sorted[key] = source[key];
    }}
    return JSON.stringify(sorted);
  }}

  function csvCell(value) {{
    if (value === null || value === undefined) return "";
    const textValue = String(value);
    if (/[",\\r\\n]/.test(textValue)) {{
      return "\\"" + textValue.replace(/"/g, "\\"\\"") + "\\"";
    }}
    return textValue;
  }}

  function csvText(fieldNames, rows) {{
    const lines = [fieldNames.map(csvCell).join(",")];
    for (const row of rows || []) {{
      lines.push(fieldNames.map((field) => csvCell(row[field])).join(","));
    }}
    return lines.join("\\r\\n") + "\\r\\n";
  }}

  function generatedFileCsvRows() {{
    return files.map((file) => ({{
      path: file.path,
      functionCount: file.functionCount,
      exportCount: file.exportCount,
      staticCount: file.staticCount,
      edgeCount: file.edgeCount,
      dominantArea: file.dominantArea,
      levels: stableJsonText(file.levels),
      classes: stableJsonText(file.classes),
      areas: stableJsonText(file.areas),
      brief: file.brief || "",
      htmlUrl: file.htmlUrl || "",
      sourceUrl: file.sourceUrl || ""
    }}));
  }}

  function generatedDownloadText(kind) {{
    if (kind === "json") {{
      return JSON.stringify(data, null, 2) + "\\n";
    }}
    if (kind === "functions-csv") {{
      return csvText(FUNCTION_CSV_FIELDS, functions);
    }}
    if (kind === "files-csv") {{
      return csvText(FILE_CSV_FIELDS, generatedFileCsvRows());
    }}
    return null;
  }}

  function generatedDownloadBlob(link) {{
    const kind = link.getAttribute("data-download-kind") || "";
    let text = generatedDownloadText(kind);
    if (text === null) return null;
    if (link.getAttribute("data-download-bom") === "true") {{
      text = "\\ufeff" + text;
    }}
    return new Blob([text], {{ type: "application/octet-stream" }});
  }}

  function triggerBlobDownload(blob, name) {{
    const url = URL.createObjectURL(new Blob([blob], {{ type: "application/octet-stream" }}));
    const tmp = document.createElement("a");
    tmp.href = url;
    tmp.setAttribute("download", name);
    document.body.appendChild(tmp);
    tmp.click();
    document.body.removeChild(tmp);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }}

  for (const link of document.querySelectorAll(".dep-download")) {{
    link.addEventListener("click", (ev) => {{
      const menu = link.closest(".dep-download-menu");
      if (menu) closeDownloadMenus(null);
      const href = link.getAttribute("href");
      if (!href) return;
      const name = link.getAttribute("data-download-name") || href.split("/").pop();
      const fallbackDownload = () => {{
        const generatedBlob = generatedDownloadBlob(link);
        if (generatedBlob) {{
          triggerBlobDownload(generatedBlob, name);
          return;
        }}
        window.location.href = href;
      }};
      ev.preventDefault();
      if (window.location.protocol !== "http:" && window.location.protocol !== "https:") {{
        fallbackDownload();
        return;
      }}
      fetch(href, {{ cache: "no-store" }})
        .then((res) => {{
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.blob();
        }})
        .then((blob) => {{
          triggerBlobDownload(blob, name);
        }})
        .catch(() => {{
          fallbackDownload();
        }});
    }});
  }}

  // テスト専用フック。読み込み前に window.__DEP_REPORT_TEST__ を true に設定した場合のみ
  // 公開する。通常の閲覧時はグローバルを汚さない。Puppeteer による全体マップの
  // インタラクション検証 (Phase A 同期反映 / Phase C 遅延) に用いる。
  if (window.__DEP_REPORT_TEST__) {{
    window.depReportOverviewTestApi = {{
      activateOverview: () => activateTab("overviewPanel"),
      isReady: () => Boolean(overviewCy) && overviewCy.elements().length > 0 && isOverviewRenderedSelectionCurrent(),
      isInitializing: () => Boolean(overviewGraph && overviewGraph.classList.contains("layout-initializing")),
      isLayoutRunning: () => Boolean(overviewLayoutRunning) || Boolean(overviewActiveLayout) || Boolean(overviewPositionAnimation && overviewPositionAnimation.active),
      layoutRunCount: () => overviewLayoutRunCount,
      lastLayoutNodeCount: () => overviewLastLayoutNodeCount,
      lastLayoutDurationMs: () => overviewLastLayoutDurationMs,
      totalNodeCount: () => (overviewCy ? overviewCy.nodes().length : 0),
      // 現在の可視状態で、全子ノードを対象に 1 回レイアウトを実行し、投入ノード数と
      // 純計算時間を返す。scope=true で部分コレクション経路、false で全グラフ経路。
      // 部分コレクション化の改善効果 (投入ノード数・時間の削減) を同一条件で比較するための
      // テスト専用フック。視覚結果は問わない (anchorCenters なしで走らせる)。
      measureLayoutForTest: (scope) => new Promise((resolve) => {{
        if (!overviewCy) {{ resolve(null); return; }}
        const movingNodeIds = new Set(overviewCy.nodes(":child").map((node) => node.id()));
        runOverviewLayout({{
          movingNodeIds,
          immediate: true,
          fullConvergence: true,
          unlockAllDuringLayout: true,
          scopeToVisibleChildren: Boolean(scope),
          onComplete: () => resolve({{
            nodeCount: overviewLastLayoutNodeCount,
            durationMs: overviewLastLayoutDurationMs
          }})
        }});
      }}),
      selectFile: (path) => selectFile(path),
      selectFunction: (id) => selectFunction(id),
      selectEdge: (id) => selectOverviewEdge(id),
      clearSelection: () => clearOverviewSelection(),
      hideFile: (path) => hideOverviewFile(path),
      revealAll: () => revealAllOverviewFiles(),
      hiddenFiles: () => Array.from(hiddenOverviewFiles.keys()),
      hiddenNoticeVisible: () => Boolean(overviewHiddenNotice && overviewHiddenNotice.classList.contains("visible")),
      hiddenNoticeRect: () => {{
        if (!overviewHiddenNotice) return null;
        const rect = overviewHiddenNotice.getBoundingClientRect();
        return {{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }};
      }},
      resetGraph: () => resetOverviewGraphState(),
      setOverviewDepth: (kind, value) => setOverviewDepth(kind, value),
      overviewDepthSettings: () => ({{ caller: overviewDepthAttrValue(overviewCallerDepth), callee: overviewDepthAttrValue(overviewCalleeDepth) }}),
      overviewDepthMenuChecked: () => {{
        if (!overviewGraphMenu) return null;
        applyOverviewGraphMenuScope("background");
        const checkedOf = (selector) => {{
          const el = overviewGraphMenu.querySelector(selector + ".checked");
          return el ? el.getAttribute(selector.startsWith("[data-caller") ? "data-caller-depth" : "data-callee-depth") : null;
        }};
        return {{ caller: checkedOf("[data-caller-depth]"), callee: checkedOf("[data-callee-depth]") }};
      }},
      renderedSignature: () => overviewRenderedSelectionSignature,
      pendingSignature: () => overviewPendingSelectionSignature,
      currentSignature: () => overviewSelectionSignature(),
      viewport: () => overviewViewport(),
      lastClassUpdatePlan: () => overviewLastClassUpdatePlan,
      activateFunctionList: () => activateTab("functionListPanel"),
      activateFileList: () => activateTab("fileListPanel"),
      isRelayoutHidden: () => Boolean(overviewGraph && overviewGraph.classList.contains("layout-relayouting")),
      isPositionAnimationActive: () => Boolean(overviewPositionAnimation && overviewPositionAnimation.active),
      classesOf: (id) => {{
        if (!overviewCy) return null;
        const element = overviewCy.getElementById(id);
        return element && element.length ? element.classes() : null;
      }},
      styleOf: (id, names) => {{
        if (!overviewCy) return null;
        const element = overviewCy.getElementById(id);
        if (!element || !element.length) return null;
        const result = {{}};
        for (const name of (names || [])) {{
          result[name] = graphStyleValue(element, name, "");
        }}
        return result;
      }},
      edgeIds: () => (overviewCy ? overviewCy.edges().map((edge) => edge.id()) : []),
      elementCount: () => (overviewCy ? overviewCy.elements().length : 0),
      buildSvg: (scope) => buildOverviewSvg(scope || "full"),
      svgDrawOrder: () => overviewSvgOrderedElements().map((element) => element.id()),
      applyThemeForTest: (theme) => applyTheme(theme, false),
      nodeIds: () => (overviewCy ? overviewCy.nodes().map((node) => node.id()) : []),
      childPositions: (parentId) => {{
        if (!overviewCy) return null;
        const parent = overviewCy.getElementById(parentId);
        if (!parent || !parent.length) return null;
        return parent.children().map((child) => {{
          const position = child.position();
          return {{ id: child.id(), x: Math.round(position.x), y: Math.round(position.y) }};
        }});
      }},
      renderedPositionOf: (id) => {{
        if (!overviewCy) return null;
        const element = overviewCy.getElementById(id);
        if (!element || !element.length) return null;
        const rendered = element.renderedPosition();
        const rect = overviewGraph.getBoundingClientRect();
        return {{ x: rect.left + rendered.x, y: rect.top + rendered.y }};
      }},
      renderedBoundingBoxOf: (id) => {{
        if (!overviewCy) return null;
        const element = overviewCy.getElementById(id);
        if (!element || !element.length) return null;
        const box = element.renderedBoundingBox({{ includeLabels: true, includeOverlays: false }});
        return {{ x1: box.x1, y1: box.y1, x2: box.x2, y2: box.y2, w: box.w, h: box.h }};
      }},
      graphSize: () => overviewCy ? {{ width: overviewCy.width(), height: overviewCy.height() }} : null,
      positionOf: (id) => {{
        if (!overviewCy) return null;
        const element = overviewCy.getElementById(id);
        if (!element || !element.length) return null;
        const position = element.position();
        return {{ x: position.x, y: position.y }};
      }}
    }};
  }}
}}());
</script>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html_text, encoding="utf-8")


def copy_graph_assets(output_dir: Path) -> None:
    for asset_name in GRAPH_ASSETS:
        source = SCRIPT_DIR / asset_name
        if not source.is_file():
            raise FileNotFoundError(f"graph asset not found: {source}")
        shutil.copyfile(source, output_dir / asset_name)


def generate_report(xml_dir: Path, output_dir: Path, category_id: str) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = build_report_data(xml_dir, output_dir, category_id)
    write_data_js(output_dir, data)
    write_data_json(output_dir, data)
    write_csv(output_dir, data)
    write_html(output_dir, category_id)
    copy_graph_assets(output_dir)
    return data


def main(argv: List[str]) -> int:
    if len(argv) not in (3, 4):
        print(
            "使用方法: generate-dependency-report.py <xml_directory> <output_directory> [category_id]",
            file=sys.stderr,
        )
        return 2

    xml_dir = Path(argv[1])
    output_dir = Path(argv[2])
    category_id = argv[3] if len(argv) == 4 else ""

    if not xml_dir.is_dir():
        print(f"ERROR: XML directory not found: {xml_dir}", file=sys.stderr)
        return 1

    data = generate_report(xml_dir, output_dir, category_id)
    print(
        "Generated dependency report: {} (functions={}, edges={})".format(
            output_dir,
            data["summary"]["functionCount"],
            data["summary"]["edgeCount"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
