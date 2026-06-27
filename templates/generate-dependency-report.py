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
    html_url: str = ""
    source_url: str = ""
    brief: str = ""
    callees: Set[str] = field(default_factory=set)
    callers: Set[str] = field(default_factory=set)


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


def find_definition_locations(
    xml_dir: Path,
    needed_ids: Set[str],
    canonical_alias_map: Dict[str, str],
) -> Dict[str, Tuple[str, int]]:
    if not needed_ids:
        return {}
    results: Dict[str, Tuple[str, int]] = {}
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
            text = "".join(codeline.itertext())
            if ";" in text:
                continue
            for ref in codeline.findall(".//ref"):
                refid = ref.get("refid", "")
                if refid == "":
                    continue
                target = canonical_alias_map.get(refid, refid)
                if target not in needed_ids:
                    continue
                current = results.get(target)
                if current is None or lineno < current[1]:
                    results[target] = (compound_file, lineno)
    return results


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
    for fid, (def_file, def_line) in definitions.items():
        info = functions[fid]
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
    "src-to-libsrc-caller": 5,
    "cross-area-caller": 6,
    "reverse-boundary-caller": 7,
}

DEPENDENCY_RANKS = {
    "leaf-static": 0,
    "leaf-global": 1,
    "file-local": 2,
    "include-callee": 2,
    "libsrc-file-caller": 3,
    "src-file-caller": 4,
    "src-to-libsrc-caller": 5,
    "cross-area-caller": 6,
    "reverse-boundary-caller": 7,
    "cycle": 999,
}

DEPENDENCY_LEVEL_BASES = {
    "leaf-static": 0,
    "leaf-global": 1,
    "file-local": 2000,
    "include-callee": 2000,
    "libsrc-file-caller": 3000,
    "src-file-caller": 4000,
    "src-to-libsrc-caller": 5000,
    "cross-area-caller": 6000,
    "reverse-boundary-caller": 7000,
}


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
    if caller_area == "src" and callee_area == "libsrc":
        return "src-to-libsrc-caller"
    if caller_area == "libsrc" and callee_area == "src":
        return "reverse-boundary-caller"
    return "cross-area-caller"


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


def build_report_data(xml_dir: Path, output_dir: Path, category_id: str) -> Dict[str, object]:
    functions = collect_functions(xml_dir)
    cycle_map, sccs = detect_cycle_groups(functions)
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
        dependency_level = None
        if dependency_depth is not None:
            dependency_level = DEPENDENCY_LEVEL_BASES[dependency_class] + dependency_depth
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
            "sccId": cycle_map.get(func_id),
            "htmlUrl": info.html_url,
            "sourceUrl": info.source_url,
            "brief": info.brief,
        }
        function_rows.append(row)
        file_groups[info.file].append(row)

        for callee_id in sorted(info.callees):
            callee = functions[callee_id]
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
    function_fields = [
        "dependencyLevel",
        "dependencyRank",
        "dependencyDepth",
        "dependencyClass",
        "sourceArea",
        "maxCalleeArea",
        "dominantCallKind",
        "isStatic",
        "name",
        "file",
        "line",
        "inScopeCalleeCount",
        "inScopeCallerCount",
        "sameFileCalleeCount",
        "crossFileCalleeCount",
        "sccId",
        "id",
        "htmlUrl",
        "sourceUrl",
        "brief",
    ]
    with (output_dir / "dependency-functions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=function_fields)
        writer.writeheader()
        for row in data["functions"]:
            writer.writerow({field: row.get(field, "") for field in function_fields})

    file_fields = [
        "path",
        "functionCount",
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
    with (output_dir / "dependency-files.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=file_fields)
        writer.writeheader()
        for row in data["files"]:
            writer.writerow(
                {
                    "path": row["path"],
                    "functionCount": row["functionCount"],
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


def write_html(output_dir: Path, category_id: str) -> None:
    title = "依存関係レポート"
    escaped_category = html.escape(category_id or "doxygen")
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
  <style>
    :root {{
      color-scheme: light dark;
      --dep-border: #d8dee8;
      --dep-bg: #f7f9fc;
      --dep-accent: #0f766e;
      --dep-warning: #a16207;
      --dep-danger: #b91c1c;
      --dep-input-bg: #ffffff;
      --dep-input-text: #1f2937;
      --dep-input-border: #b8c2d1;
      --dep-input-focus: #0f766e;
    }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
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
      margin: 0 0 4px;
    }}
    .dep-meta {{
      color: #596579;
      margin: 0 0 18px;
    }}
    .dep-summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 8px;
      margin-bottom: 18px;
    }}
    .dep-metric {{
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      padding: 10px;
      background: var(--dep-bg);
    }}
    .dep-metric strong {{
      display: block;
      font-size: 1.35rem;
    }}
    .dep-controls {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) repeat(3, minmax(140px, 220px));
      gap: 8px;
      margin-bottom: 12px;
    }}
    .dep-downloads {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .dep-download {{
      display: inline-block;
      padding: 4px 10px;
      border: 1px solid var(--dep-border);
      border-radius: 4px;
      background: var(--dep-bg);
      color: var(--dep-input-text);
      text-decoration: none;
      font-size: 0.9rem;
    }}
    .dep-download:hover {{
      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-bg));
      border-color: var(--dep-accent);
      color: var(--dep-accent);
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
      color-scheme: light;
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
      background: color-mix(in srgb, var(--dep-warning) 10%, white);
      color: #713f12;
    }}
    .dep-filter-notice.visible {{
      display: flex;
    }}
    .dep-filter-notice button,
    .dep-neighbor-button {{
      border: 1px solid var(--dep-input-border);
      border-radius: 4px;
      background: var(--dep-input-bg);
      color: var(--dep-input-text);
      cursor: pointer;
      font: inherit;
    }}
    .dep-filter-notice button {{
      flex: 0 0 auto;
      min-height: 30px;
      padding: 4px 8px;
    }}
    .dep-filter-notice button:hover {{
      border-color: var(--dep-input-focus);
      color: var(--dep-input-focus);
    }}
    .dep-table-wrap {{
      overflow: auto;
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      max-height: calc(100vh - 250px);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    th, td {{
      padding: 7px 8px;
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
      padding: 2px 7px;
      border: 1px solid var(--dep-border);
      background: var(--dep-bg);
      color: #111827;
      font-size: 0.78rem;
    }}
    .badge.leaf-static,
    .badge.leaf-global {{
      background: #dcfce7;
      border-color: #16a34a;
    }}
    .badge.file-local {{
      background: #e0f2fe;
      border-color: #0284c7;
    }}
    .badge.cycle {{
      background: #fee2e2;
      border-color: #dc2626;
    }}
    .badge.libsrc-file-caller,
    .badge.src-file-caller,
    .badge.src-to-libsrc-caller,
    .badge.cross-area-caller {{
      background: #fef3c7;
      border-color: #d97706;
    }}
    .badge.reverse-boundary-caller {{
      background: #fee2e2;
      border-color: #dc2626;
    }}
    .dep-detail {{
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      padding: 12px;
      min-height: 240px;
      background: var(--dep-bg);
    }}
    .dep-detail h2 {{
      margin: 0 0 8px;
      font-size: 1.05rem;
    }}
    .dep-detail .dep-brief {{
      margin: 0 0 12px;
      color: #333;
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
      color: #596579;
    }}
    .dep-detail dd {{
      margin: 0;
      overflow-wrap: anywhere;
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
    }}
    .dep-neighbor-button:hover {{
      border-color: transparent;
      color: var(--dep-accent);
      text-decoration: none;
    }}
    .dep-neighbors small {{
      overflow-wrap: anywhere;
    }}
    .dep-empty {{
      color: #596579;
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
    .dep-graph-toolbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
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
      border-color: var(--dep-input-focus);
      color: var(--dep-input-focus);
    }}
    .dep-graph {{
      width: 100%;
      height: calc(100vh - 260px);
      min-height: 520px;
      border: 1px solid var(--dep-border);
      border-radius: 6px;
      background: #ffffff;
    }}
    .dep-graph-note {{
      color: #596579;
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
    }}
  </style>
</head>
<body>
<main>
  <div class="dep-title-row">
    <h1>{title}</h1>
    <section class="dep-downloads" role="group" aria-label="ダウンロード">
      <a class="dep-download" href="dependency-data.json" download data-download-name="dependency-data.json" title="JSON 形式の全データをダウンロード">JSON</a>
      <a class="dep-download" href="dependency-functions.csv" download data-download-name="dependency-functions.csv" title="関数一覧の CSV をダウンロード">関数 CSV</a>
      <a class="dep-download" href="dependency-files.csv" download data-download-name="dependency-files.csv" title="ファイル一覧の CSV をダウンロード">ファイル CSV</a>
    </section>
  </div>
  <p class="dep-meta">対象: {escaped_category}</p>
  <section class="dep-summary" id="summary"></section>
  <nav class="dep-tabs" aria-label="表示切り替え">
    <button type="button" class="dep-tab active" data-tab-target="listPanel">一覧</button>
    <button type="button" class="dep-tab" data-tab-target="overviewPanel">全体マップ</button>
  </nav>
  <section class="dep-panel active" id="listPanel">
    <section class="dep-controls" aria-label="フィルター">
      <input id="search" type="search" placeholder="関数名またはファイル名で検索">
      <select id="levelFilter"><option value="">level すべて</option></select>
      <select id="classFilter"><option value="">分類すべて</option></select>
      <select id="fileFilter"><option value="">ファイルすべて</option></select>
    </section>
    <div class="dep-layout">
    <div class="dep-table-panel">
      <div class="dep-filter-notice" id="filterNotice">
        <span>現在のフィルターでは選択行は非表示です。</span>
        <button type="button" id="clearFilters">フィルター解除</button>
      </div>
      <div class="dep-table-wrap">
        <table>
          <thead>
            <tr>
              <th class="dep-num"><button type="button" class="dep-sort-button" data-sort-key="level">level <span class="dep-sort-mark"></span></button></th>
              <th><button type="button" class="dep-sort-button" data-sort-key="class">分類 <span class="dep-sort-mark"></span></button></th>
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
  <section class="dep-panel" id="overviewPanel">
    <div class="dep-graph-toolbar">
      <button type="button" id="overviewFit">Fit</button>
      <button type="button" id="overviewRelayout">レイアウト再実行</button>
      <button type="button" id="overviewReset">初期化</button>
    </div>
    <div class="dep-graph-layout">
      <div id="overviewGraph" class="dep-graph"></div>
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
  const byId = new Map(functions.map((fn) => [fn.id, fn]));
  const baseOrder = new Map(functions.map((fn, index) => [fn.id, index]));
  const fileByPath = new Map(files.map((file) => [file.path, file]));
  const functionsByFile = new Map();
  const callees = new Map();
  const callers = new Map();
  for (const fn of functions) {{
    if (!functionsByFile.has(fn.file)) functionsByFile.set(fn.file, []);
    functionsByFile.get(fn.file).push(fn);
  }}
  for (const edge of edges) {{
    if (!callees.has(edge.caller)) callees.set(edge.caller, []);
    if (!callers.has(edge.callee)) callers.set(edge.callee, []);
    callees.get(edge.caller).push(edge.callee);
    callers.get(edge.callee).push(edge.caller);
  }}

  const summary = document.getElementById("summary");
  const rows = document.getElementById("functionRows");
  const detail = document.getElementById("detail");
  const search = document.getElementById("search");
  const levelFilter = document.getElementById("levelFilter");
  const classFilter = document.getElementById("classFilter");
  const fileFilter = document.getElementById("fileFilter");
  const filterNotice = document.getElementById("filterNotice");
  const clearFilters = document.getElementById("clearFilters");
  const sortButtons = Array.from(document.querySelectorAll("[data-sort-key]"));
  const tabButtons = Array.from(document.querySelectorAll("[data-tab-target]"));
  const tabPanels = Array.from(document.querySelectorAll(".dep-panel"));
  const overviewGraph = document.getElementById("overviewGraph");
  const overviewDetail = document.getElementById("overviewDetail");
  const overviewFit = document.getElementById("overviewFit");
  const overviewRelayout = document.getElementById("overviewRelayout");
  const overviewReset = document.getElementById("overviewReset");
  let selectedId = "";
  let selectedFilePath = "";
  let sortState = {{ key: "level", direction: "asc" }};
  let activeTab = "listPanel";
  let overviewCy = null;
  let overviewLayoutInitialized = false;
  let overviewAnchorCorrection = null;
  let previousSelectedRowVisible = false;
  let pendingListScroll = false;

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

  function levelText(fn) {{
    return fn.dependencyLevel === null || fn.dependencyLevel === undefined ? "cycle" : String(fn.dependencyLevel);
  }}

  function levelSortValue(fn) {{
    if (fn.dependencyLevel === null || fn.dependencyLevel === undefined) return Number.POSITIVE_INFINITY;
    return Number(fn.dependencyLevel);
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
    if (key === "static") return Number(a.isStatic) - Number(b.isStatic);
    if (key === "area") return compareText(a.sourceArea, b.sourceArea);
    if (key === "name") return compareText(a.name, b.name);
    if (key === "file") return compareText(a.file, b.file);
    if (key === "calleeCount") return compareNumbers(a.inScopeCalleeCount, b.inScopeCalleeCount);
    if (key === "callerCount") return compareNumbers(a.inScopeCallerCount, b.inScopeCallerCount);
    if (key === "crossFileCount") return compareNumbers(a.crossFileCalleeCount, b.crossFileCalleeCount);
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
    if (klass === "cycle" || klass === "reverse-boundary-caller") return "dep-danger-node";
    if (klass === "leaf-static" || klass === "leaf-global") return "dep-leaf-node";
    if (klass === "file-local") return "dep-local-node";
    return "dep-caller-node";
  }}

  function graphFileClassFor(area) {{
    if (area === "include" || area === "include_internal" || area === "libsrc") return "dep-file-library-node";
    if (area === "src") return "dep-file-source-node";
    return "";
  }}

  function graphStyle() {{
    return [
      {{
        selector: "node",
        style: {{
          "label": "data(label)",
          "font-size": 11,
          "text-wrap": "wrap",
          "text-max-width": 120,
          "text-valign": "center",
          "text-halign": "center",
          "background-color": "#dbeafe",
          "border-color": "#2563eb",
          "border-width": 1,
          "color": "#111827",
          "width": "mapData(weight, 1, 12, 42, 86)",
          "height": "mapData(weight, 1, 12, 42, 86)"
        }}
      }},
      {{
        selector: "edge",
        style: {{
          "curve-style": "bezier",
          "target-arrow-shape": "triangle",
          "target-arrow-color": "#64748b",
          "line-color": "#94a3b8",
          "width": "mapData(weight, 1, 8, 1, 5)",
          "label": "data(label)",
          "font-size": 10,
          "text-background-color": "#ffffff",
          "text-background-opacity": 0.85,
          "text-background-padding": 2
        }}
      }},
      {{ selector: ".dep-leaf-node", style: {{ "background-color": "#dcfce7", "border-color": "#16a34a" }} }},
      {{ selector: ".dep-local-node", style: {{ "background-color": "#e0f2fe", "border-color": "#0284c7" }} }},
      {{ selector: ".dep-caller-node", style: {{ "background-color": "#fef3c7", "border-color": "#d97706" }} }},
      {{ selector: ".dep-danger-node", style: {{ "background-color": "#fee2e2", "border-color": "#dc2626" }} }},
      {{ selector: ".dep-file-node", style: {{ "background-color": "#f8fafc", "border-color": "#64748b" }} }},
      {{ selector: ".dep-center-node", style: {{ "border-width": 2 }} }},
      {{ selector: ".dep-upstream-node", style: {{ "shape": "round-rectangle" }} }},
      {{ selector: ".dep-downstream-node", style: {{ "shape": "ellipse" }} }},
      {{ selector: ".dep-both-node", style: {{ "shape": "diamond" }} }},
      {{
        selector: "$node > node",
        style: {{
          "shape": "round-rectangle",
          "background-color": "#f1f5f9",
          "background-opacity": 0.5,
          "border-color": "#64748b",
          "border-width": 1,
          "label": "data(label)",
          "text-valign": "top",
          "text-halign": "center",
          "font-size": 12,
          "padding": 16,
          "color": "#1f2937"
        }}
      }},
      {{ selector: ".dep-file-library-node", style: {{ "background-color": "#eef2ff", "border-color": "#4f46e5" }} }},
      {{ selector: ".dep-file-source-node", style: {{ "background-color": "#f3e8ff", "border-color": "#9333ea" }} }},
      {{
        selector: ".dep-base-edge-muted",
        style: {{
          "line-color": "#cbd5e1",
          "target-arrow-color": "#cbd5e1",
          "opacity": 0.4
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
      "<dt>領域</dt><dd>" + escapeHtml(file.dominantArea || "") + "</dd>" +
      "<dt>ファイル</dt><dd>" + escapeHtml(filePath) + "</dd>" +
      "<dt>関数</dt><dd>" + escapeHtml(file.functionCount || rows.length) + "</dd>" +
      "<dt>リンク</dt><dd>" + [linkFor(file, "Doxygen", false), linkFor(file, "source", true)].filter(Boolean).join(" / ") + "</dd>" +
      "</dl>" +
      (items ? "<strong>関数</strong><ul>" + items + "</ul>" : "<p class=\\"dep-empty\\">関数はありません。</p>");
    bindOverviewActions();
  }}

  function renderOverviewFunctionDetail(fn) {{
    overviewDetail.innerHTML =
      "<h2>" + escapeHtml(fn.name) + "</h2>" +
      (fn.brief ? "<p class=\\"dep-brief\\">" + escapeHtml(fn.brief) + "</p>" : "") +
      "<dl>" +
      "<dt>分類</dt><dd><span class=\\"badge " + escapeHtml(fn.dependencyClass) + "\\">" + escapeHtml(fn.dependencyClass) + "</span></dd>" +
      "<dt>level</dt><dd>" + escapeHtml(levelText(fn)) + "</dd>" +
      "<dt>領域</dt><dd>" + escapeHtml(fn.sourceArea) + "</dd>" +
      "<dt>呼び出し種別</dt><dd>" + escapeHtml(fn.dominantCallKind) + "</dd>" +
      "<dt>static</dt><dd>" + (fn.isStatic ? "yes" : "no") + "</dd>" +
      "<dt>ファイル</dt><dd>" + escapeHtml(fn.file) + "</dd>" +
      "<dt>行</dt><dd>" + escapeHtml(fn.line) + "</dd>" +
      "<dt>リンク</dt><dd>" + [linkFor(fn, "Doxygen", false), linkFor(fn, "source", true)].filter(Boolean).join(" / ") + "</dd>" +
      "</dl>" +
      "<div class=\\"dep-neighbors\\">" +
      "<section><strong>呼び出し先</strong>" + neighborList(callees.get(fn.id), "対象範囲内の呼び出し先はありません。") + "</section>" +
      "<section><strong>呼び出し元</strong>" + neighborList(callers.get(fn.id), "対象範囲内の呼び出し元はありません。") + "</section>" +
      "</div>";
    bindOverviewActions();
  }}

  function bindOverviewActions() {{
    for (const button of overviewDetail.querySelectorAll("[data-function-id]")) {{
      button.addEventListener("click", () => selectFunction(button.getAttribute("data-function-id")));
    }}
  }}

  function overviewBaseElements() {{
    const edgeMap = new Map();
    for (const edge of edges) {{
      if (edge.callerFile === edge.calleeFile) continue;
      const key = edge.callerFile + "\\n" + edge.calleeFile;
      const current = edgeMap.get(key) || {{
        data: {{
          id: key,
          source: edge.callerFile,
          target: edge.calleeFile,
          label: "",
          weight: 0
        }}
      }};
      current.data.weight += 1;
      current.data.label = String(current.data.weight);
      edgeMap.set(key, current);
    }}
    const elements = [];
    for (const file of files) {{
      const classes = ["dep-file-node"];
      const areaClass = graphFileClassFor(file.dominantArea);
      if (areaClass) classes.push(areaClass);
      if (!selectedId && file.path === selectedFilePath) classes.push("dep-selected-file");
      elements.push({{
        data: {{
          id: file.path,
          label: shortPath(file.path),
          weight: Math.max(1, Number(file.functionCount || 1)),
          path: file.path
        }},
        classes: classes.join(" ")
      }});
    }}
    for (const edge of edgeMap.values()) {{
      if (selectedId) edge.classes = "dep-base-edge-muted";
      elements.push(edge);
    }}
    return elements;
  }}

  function visibleFunctionIdsForOverview() {{
    if (selectedId) {{
      const ids = new Set([selectedId]);
      for (const c of (callers.get(selectedId) || [])) ids.add(c);
      for (const c of (callees.get(selectedId) || [])) ids.add(c);
      return ids;
    }}
    if (selectedFilePath) {{
      const ids = new Set();
      for (const fn of (functionsByFile.get(selectedFilePath) || [])) ids.add(fn.id);
      return ids;
    }}
    return new Set();
  }}

  function buildOverviewElements() {{
    const elements = overviewBaseElements();
    const visibleFnIds = visibleFunctionIdsForOverview();
    const visibleFns = Array.from(visibleFnIds)
      .map((id) => byId.get(id))
      .filter(Boolean)
      .sort((a, b) => {{
        if (a.id === selectedId) return -1;
        if (b.id === selectedId) return 1;
        return compareBaseOrder(a, b);
      }});
    const childrenByFile = new Map();
    for (let index = 0; index < visibleFns.length; index++) {{
      const fn = visibleFns[index];
      const classes = [graphClassFor(fn.dependencyClass)];
      if (fn.id === selectedId) classes.push("dep-center-node");
      elements.push({{
        data: {{
          id: fn.id,
          label: fn.name,
          parent: fn.file,
          weight: fn.id === selectedId ? 8 : 3
        }},
        position: overviewFunctionPosition(fn, index, visibleFns.length),
        classes: classes.join(" ")
      }});
      if (!childrenByFile.has(fn.file)) childrenByFile.set(fn.file, []);
      childrenByFile.get(fn.file).push(fn.id);
    }}
    if (selectedId) {{
      for (const edge of edges) {{
        if (!visibleFnIds.has(edge.caller) || !visibleFnIds.has(edge.callee)) continue;
        elements.push({{
          data: {{
            id: edge.caller + "->" + edge.callee,
            source: edge.caller,
            target: edge.callee,
            weight: 1
          }}
        }});
      }}
    }} else if (selectedFilePath) {{
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

  function overviewFunctionPosition(fn, index, count) {{
    if (!overviewCy) return {{ x: 0, y: 0 }};
    const parent = overviewCy.getElementById(fn.file);
    const center = parent && parent.length > 0 ? parent.position() : {{ x: 0, y: 0 }};
    if (fn.id === selectedId) return {{ x: center.x, y: center.y }};
    const ringIndex = selectedId ? Math.max(0, index - 1) : index;
    const ringCount = selectedId ? Math.max(1, count - 1) : Math.max(1, count);
    const radius = 56 + Math.min(72, ringCount * 4);
    const angle = -Math.PI / 2 + (Math.PI * 2 * ringIndex) / ringCount;
    return {{
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius
    }};
  }}

  function runOverviewLayout(opts) {{
    if (!overviewCy) return;
    const animate = overviewLayoutInitialized;
    const fit = Boolean(opts && opts.fit);
    const movingNodeIds = opts && opts.movingNodeIds ? opts.movingNodeIds : null;
    const anchorCenters = opts && opts.anchorCenters ? opts.anchorCenters : new Map();
    const lockedNodes = movingNodeIds ? overviewCy.nodes().filter((node) => !movingNodeIds.has(node.id())) : overviewCy.collection();
    overviewLayoutInitialized = true;
    if (typeof cytoscapeCola === "function") {{
      lockedNodes.lock();
      startOverviewAnchorCorrection(anchorCenters);
      const layout = overviewCy.layout({{
        name: "cola",
        animate,
        refresh: 1,
        maxSimulationTime: fit ? 2000 : 900,
        fit,
        padding: 30,
        randomize: false,
        avoidOverlap: true,
        handleDisconnected: true,
        nodeSpacing: function (node) {{ return node.isParent() ? 22 : 14; }},
        centerGraph: fit,
        edgeLength: function (edge) {{ return edge.hasClass("dep-pull-edge") ? 48 : 132; }},
        convergenceThreshold: fit ? 0.01 : 0.08,
        unconstrIter: fit ? undefined : 8,
        userConstIter: fit ? undefined : 8,
        allConstIter: fit ? undefined : 12
      }});
      layout.one("layoutready", () => {{
        restoreOverviewAnchorCenters(anchorCenters);
      }});
      layout.one("layoutstop", () => {{
        stopOverviewAnchorCorrection();
        restoreOverviewAnchorCenters(anchorCenters);
        lockedNodes.unlock();
      }});
      layout.run();
      restoreOverviewAnchorCenters(anchorCenters);
      return;
    }}
    lockedNodes.lock();
    startOverviewAnchorCorrection(anchorCenters);
    const layout = overviewCy.layout({{
      name: "cose",
      animate,
      animationDuration: 600,
      animationEasing: "ease-in-out",
      fit,
      padding: 30,
      nodeRepulsion: function (node) {{ return node.isParent() ? 14400 : 3000; }},
      idealEdgeLength: function (edge) {{ return edge.hasClass("dep-pull-edge") ? 48 : 120; }},
      edgeElasticity: function (edge) {{ return edge.hasClass("dep-pull-edge") ? 200 : 100; }},
      nestingFactor: 0.4,
      gravity: 120,
      numIter: 1500,
      randomize: false
    }});
    layout.one("layoutready", () => {{
      restoreOverviewAnchorCenters(anchorCenters);
    }});
    layout.one("layoutstop", () => {{
      stopOverviewAnchorCorrection();
      restoreOverviewAnchorCenters(anchorCenters);
      lockedNodes.unlock();
    }});
    layout.run();
    restoreOverviewAnchorCenters(anchorCenters);
  }}

  function overviewNodePositions() {{
    const positions = new Map();
    if (!overviewCy) return positions;
    overviewCy.nodes().forEach((node) => {{
      positions.set(node.id(), {{ x: node.position("x"), y: node.position("y") }});
    }});
    return positions;
  }}

  function restoreOverviewNodePositions(positions) {{
    if (!overviewCy) return;
    overviewCy.nodes().forEach((node) => {{
      const position = positions.get(node.id());
      if (position) node.position(position);
    }});
  }}

  function restoreOverviewAnchorCenters(anchorCenters) {{
    if (!overviewCy || !anchorCenters || anchorCenters.size === 0) return;
    for (const [id, anchor] of anchorCenters) {{
      const node = overviewCy.getElementById(id);
      if (!node || !node.length) continue;
      const current = node.position();
      const dx = anchor.x - current.x;
      const dy = anchor.y - current.y;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
      const movable = node.descendants().nodes(":unlocked");
      movable.positions((child) => {{
        const position = child.position();
        return {{ x: position.x + dx, y: position.y + dy }};
      }});
    }}
  }}

  function startOverviewAnchorCorrection(anchorCenters) {{
    stopOverviewAnchorCorrection();
    if (!anchorCenters || anchorCenters.size === 0) return;
    let active = true;
    const frame = () => {{
      if (!active) return;
      restoreOverviewAnchorCenters(anchorCenters);
      const raf = window.requestAnimationFrame || window.webkitRequestAnimationFrame || ((callback) => window.setTimeout(callback, 16));
      overviewAnchorCorrection.frameId = raf(frame);
    }};
    overviewAnchorCorrection = {{
      stop: () => {{ active = false; }},
      frameId: null
    }};
    frame();
  }}

  function stopOverviewAnchorCorrection() {{
    if (!overviewAnchorCorrection) return;
    overviewAnchorCorrection.stop();
    overviewAnchorCorrection = null;
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

  function anchorOverviewChildPositions(targetElements, anchorCenters) {{
    if (!anchorCenters || anchorCenters.size === 0) return;
    for (const [parentId, anchor] of anchorCenters) {{
      const children = targetElements.filter((element) => (
        !isEdgeElement(element) && element.data && element.data.parent === parentId
      ));
      if (children.length === 0) continue;
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

  function addMissingOverviewElements(targetElements, targetById, movingNodeIds) {{
    const missing = targetElements.filter((element) => !overviewCy.getElementById(element.data.id).length);
    const parentNodes = missing.filter((element) => !isEdgeElement(element) && !element.data.parent);
    const childNodes = missing.filter((element) => !isEdgeElement(element) && element.data.parent);
    const edgeElements = missing.filter(isEdgeElement);
    const ordered = parentNodes.concat(childNodes, edgeElements);
    if (ordered.length === 0) return false;
    for (const element of parentNodes.concat(childNodes)) {{
      movingNodeIds.add(element.data.id);
    }}
    overviewCy.add(ordered.map((element) => targetById.get(element.data.id)));
    return true;
  }}

  function syncOverviewElements(targetElements) {{
    if (!overviewCy) return;
    const previousPositions = overviewNodePositions();
    const movingNodeIds = new Set();
    const anchorCenters = new Map();
    if (selectedFilePath && previousPositions.has(selectedFilePath)) {{
      anchorCenters.set(selectedFilePath, previousPositions.get(selectedFilePath));
    }}
    anchorOverviewChildPositions(targetElements, anchorCenters);
    const targetById = new Map(targetElements.map((element) => [element.data.id, element]));
    let layoutNeeded = false;
    overviewCy.batch(() => {{
      const stale = overviewCy.elements().filter((element) => !targetById.has(element.id()));
      if (stale.length > 0) {{
        if (stale.nodes().length > 0) layoutNeeded = true;
        overviewCy.remove(stale);
      }}
      if (addMissingOverviewElements(targetElements, targetById, movingNodeIds)) {{
        layoutNeeded = true;
      }}
      for (const target of targetElements) {{
        const element = overviewCy.getElementById(target.data.id);
        if (!element.length) continue;
        if (target.data.parent && element.data("parent") !== target.data.parent) {{
          element.move({{ parent: target.data.parent }});
          movingNodeIds.add(target.data.id);
          layoutNeeded = true;
        }}
        if (currentDataDiffers(element, target.data)) {{
          element.data(target.data);
        }}
        if (currentClassesDiffer(element, target.classes)) {{
          element.classes(target.classes || "");
        }}
      }}
      restoreOverviewAnchorCenters(anchorCenters);
    }});
    if (layoutNeeded) {{
      restoreOverviewNodePositions(previousPositions);
      restoreOverviewAnchorCenters(anchorCenters);
      if (movingNodeIds.size > 0) {{
        runOverviewLayout({{ movingNodeIds, anchorCenters }});
      }}
    }}
  }}

  function renderOverviewGraph() {{
    if (!overviewCy) return;
    if (overviewCy.elements().length === 0) {{
      resetOverviewGraph();
      return;
    }}
    syncOverviewElements(buildOverviewElements());
  }}

  function resetOverviewGraph() {{
    if (!overviewCy) return;
    overviewLayoutInitialized = false;
    overviewCy.elements().remove();
    const elements = buildOverviewElements();
    seedOverviewInitialPositions(elements);
    overviewCy.add(elements);
    runOverviewLayout({{ fit: true }});
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
  }}

  function refreshActiveGraph() {{
    if (activeTab === "overviewPanel") {{
      initOverviewGraph();
      renderOverviewGraph();
      if (overviewCy) {{
        overviewCy.resize();
        overviewCy.fit(undefined, 30);
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
    }}
    for (const klass of Array.from(new Set(functions.map((fn) => fn.dependencyClass))).sort()) {{
      const option = document.createElement("option");
      option.value = klass;
      option.textContent = klass;
      classFilter.appendChild(option);
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
    if (fileFilter.value && fn.file !== fileFilter.value) return false;
    return true;
  }}

  function selectedVisible() {{
    if (!selectedId) return true;
    const fn = byId.get(selectedId);
    return !fn || matches(fn);
  }}

  function renderNotice() {{
    filterNotice.classList.toggle("visible", !selectedVisible());
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
        pendingListScroll = true;
        return;
      }}
      pendingListScroll = false;
    }}
    previousSelectedRowVisible = true;
  }}

  function renderRows(opts) {{
    rows.replaceChildren();
    for (const fn of sortedFunctions(functions.filter(matches))) {{
      const tr = document.createElement("tr");
      if (fn.id === selectedId) tr.className = "selected";
      tr.innerHTML =
        "<td class=\\"dep-num\\">" + escapeHtml(levelText(fn)) + "</td>" +
        "<td><span class=\\"badge " + escapeHtml(fn.dependencyClass) + "\\">" + escapeHtml(fn.dependencyClass) + "</span></td>" +
        "<td>" + (fn.isStatic ? "yes" : "") + "</td>" +
        "<td>" + escapeHtml(fn.sourceArea) + "</td>" +
        "<td>" + escapeHtml(fn.name) + "</td>" +
        "<td class=\\"dep-file\\" title=\\"" + escapeHtml(fn.file) + "\\">" + escapeHtml(fn.file) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(fn.inScopeCalleeCount) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(fn.inScopeCallerCount) + "</td>" +
        "<td class=\\"dep-num\\">" + escapeHtml(fn.crossFileCalleeCount) + "</td>";
      tr.addEventListener("click", () => {{
        selectFunction(fn.id, {{ fromTableRow: true }});
      }});
      rows.appendChild(tr);
    }}
    renderNotice();
    renderSortMarks();
    syncSelectedRowScroll(Boolean(opts && opts.forceScroll));
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

  function bindDetailActions() {{
    for (const button of detail.querySelectorAll("[data-function-id]")) {{
      button.addEventListener("click", () => selectFunction(button.getAttribute("data-function-id")));
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
      "<dt>領域</dt><dd>" + escapeHtml(fn.sourceArea) + "</dd>" +
      "<dt>呼び出し種別</dt><dd>" + escapeHtml(fn.dominantCallKind) + "</dd>" +
      "<dt>static</dt><dd>" + (fn.isStatic ? "yes" : "no") + "</dd>" +
      "<dt>ファイル</dt><dd>" + escapeHtml(fn.file) + "</dd>" +
      "<dt>行</dt><dd>" + escapeHtml(fn.line) + "</dd>" +
      "<dt>リンク</dt><dd>" + [linkFor(fn, "Doxygen", false), linkFor(fn, "source", true)].filter(Boolean).join(" / ") + "</dd>" +
      "</dl>" +
      "<div class=\\"dep-neighbors\\">" +
      "<section><strong>呼び出し先</strong>" + neighborList(callees.get(fn.id), "対象範囲内の呼び出し先はありません。") + "</section>" +
      "<section><strong>呼び出し元</strong>" + neighborList(callers.get(fn.id), "対象範囲内の呼び出し元はありません。") + "</section>" +
      "</div>";
    bindDetailActions();
  }}

  function selectFunction(id, opts) {{
    const fn = byId.get(id);
    if (!fn) return;
    if (id === selectedId) return;
    selectedId = id;
    selectedFilePath = fn.file;
    renderDetail(fn);
    renderOverviewFunctionDetail(fn);
    const fromTableRow = Boolean(opts && opts.fromTableRow);
    renderRows({{ forceScroll: !fromTableRow }});
    if (activeTab === "overviewPanel") {{
      renderOverviewGraph();
    }}
  }}

  function selectFile(path) {{
    if (path === selectedFilePath && selectedId === "") return;
    selectedFilePath = path;
    selectedId = "";
    renderDetail(null);
    renderOverviewDetail(path);
    renderRows({{ forceScroll: false }});
    if (activeTab === "overviewPanel") {{
      renderOverviewGraph();
    }}
  }}

  function clearSelection() {{
    selectedId = "";
    selectedFilePath = "";
    renderDetail(null);
    overviewDetail.innerHTML = "<p class=\\"dep-empty\\">ファイルまたは関数を選択してください。</p>";
    renderRows({{ forceScroll: false }});
    if (activeTab === "overviewPanel") {{
      resetOverviewGraph();
    }}
  }}

  addMetric("関数", data.summary.functionCount || 0);
  addMetric("呼び出し関係", data.summary.edgeCount || 0);
  addMetric("ファイル", data.summary.fileCount || 0);
  addMetric("static", data.summary.staticCount || 0);
  addMetric("leaf", data.summary.leafCount || 0);
  addMetric("循環グループ", data.summary.cycleGroupCount || 0);
  fillOptions();
  renderRows();
  for (const control of [search, levelFilter, classFilter, fileFilter]) {{
    control.addEventListener("input", () => renderRows());
    control.addEventListener("change", () => renderRows());
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
  for (const button of tabButtons) {{
    button.addEventListener("click", () => {{
      activeTab = button.getAttribute("data-tab-target");
      for (const item of tabButtons) {{
        item.classList.toggle("active", item === button);
      }}
      for (const panel of tabPanels) {{
        panel.classList.toggle("active", panel.id === activeTab);
      }}
      refreshActiveGraph();
      if (activeTab === "listPanel" && pendingListScroll) {{
        syncSelectedRowScroll(true);
      }}
    }});
  }}
  overviewFit.addEventListener("click", () => {{
    if (overviewCy) overviewCy.fit(undefined, 30);
  }});
  overviewRelayout.addEventListener("click", () => {{
    runOverviewLayout();
  }});
  overviewReset.addEventListener("click", () => {{
    clearSelection();
  }});
  clearFilters.addEventListener("click", () => {{
    search.value = "";
    levelFilter.value = "";
    classFilter.value = "";
    fileFilter.value = "";
    renderRows();
  }});
  for (const link of document.querySelectorAll(".dep-download")) {{
    link.addEventListener("click", (ev) => {{
      if (window.location.protocol !== "http:" && window.location.protocol !== "https:") return;
      const href = link.getAttribute("href");
      if (!href) return;
      const name = link.getAttribute("data-download-name") || href.split("/").pop();
      ev.preventDefault();
      fetch(href, {{ cache: "no-store" }})
        .then((res) => {{
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.blob();
        }})
        .then((blob) => {{
          const url = URL.createObjectURL(new Blob([blob], {{ type: "application/octet-stream" }}));
          const tmp = document.createElement("a");
          tmp.href = url;
          tmp.setAttribute("download", name);
          document.body.appendChild(tmp);
          tmp.click();
          document.body.removeChild(tmp);
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        }})
        .catch(() => {{
          window.location.href = href;
        }});
    }});
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
