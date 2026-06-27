#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate-dependency-report.py - Doxygen XML から関数依存度レポートを生成する

使用方法:
    python3 generate-dependency-report.py <xml_directory> <output_directory> [category_id]
"""

from __future__ import annotations

import csv
import html
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


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
    if compound_id == "":
        return ""
    return f"../{compound_id}.html#{func_id}"


def build_source_url(compound_id: str, line: Optional[int]) -> str:
    if compound_id == "" or line is None:
        return ""
    return f"../{compound_id}_source.html#l{line:05d}"


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


def collect_functions(xml_dir: Path) -> Dict[str, FunctionInfo]:
    return canonicalize_functions(collect_raw_functions(xml_dir))


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
    "libsrc-file-caller": 2,
    "src-file-caller": 3,
    "src-to-libsrc-caller": 4,
    "cross-area-caller": 5,
    "reverse-boundary-caller": 6,
}

DEPENDENCY_RANKS = {
    "leaf-static": 0,
    "leaf-global": 0,
    "file-local": 1,
    "libsrc-file-caller": 2,
    "src-file-caller": 3,
    "src-to-libsrc-caller": 4,
    "cross-area-caller": 5,
    "reverse-boundary-caller": 6,
    "cycle": 999,
}


def path_area(file_path: str) -> str:
    parts = [part for part in normalize_path(file_path).split("/") if part]
    if "libsrc" in parts:
        return "libsrc"
    if "src" in parts:
        return "src"
    if "include" in parts:
        return "include"
    return "other"


def classify_call_kind(caller: FunctionInfo, callee: FunctionInfo) -> str:
    if caller.file == callee.file:
        return "same-file"

    caller_area = path_area(caller.file)
    callee_area = path_area(callee.file)
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

    function_rows: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []
    file_groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    for func_id, info in functions.items():
        dependency_class = classify_function(info, functions, cycle_map)
        dependency_rank = DEPENDENCY_RANKS[dependency_class]
        dependency_depth = depths[func_id]
        dependency_level = None
        if dependency_depth is not None:
            dependency_level = dependency_rank * 1000 + dependency_depth
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
        for row in rows:
            level_key = "cycle" if row["dependencyLevel"] is None else str(row["dependencyLevel"])
            level_counts[level_key] += 1
            class_counts[str(row["dependencyClass"])] += 1
        file_rows.append(
            {
                "path": file_path,
                "functionCount": len(rows),
                "staticCount": sum(1 for row in rows if row["isStatic"]),
                "levels": dict(sorted(level_counts.items())),
                "classes": dict(sorted(class_counts.items())),
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
    ]
    with (output_dir / "dependency-functions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=function_fields)
        writer.writeheader()
        for row in data["functions"]:
            writer.writerow({field: row.get(field, "") for field in function_fields})

    file_fields = ["path", "functionCount", "staticCount", "levels", "classes"]
    with (output_dir / "dependency-files.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=file_fields)
        writer.writeheader()
        for row in data["files"]:
            writer.writerow(
                {
                    "path": row["path"],
                    "functionCount": row["functionCount"],
                    "staticCount": row["staticCount"],
                    "levels": json.dumps(row["levels"], ensure_ascii=False, sort_keys=True),
                    "classes": json.dumps(row["classes"], ensure_ascii=False, sort_keys=True),
                }
            )


def write_html(output_dir: Path, category_id: str) -> None:
    title = "関数依存度レポート"
    escaped_category = html.escape(category_id or "doxygen")
    html_text = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="../doxygen.css">
  <script src="dependency-data.js"></script>
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
      max-width: 1600px;
      margin: 0 auto;
      padding: 20px;
    }}
    h1 {{
      font-size: 1.6rem;
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
    tr:hover, tr.selected {{
      background: color-mix(in srgb, var(--dep-accent) 12%, transparent);
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
      font-size: 0.78rem;
    }}
    .badge.cycle {{
      border-color: var(--dep-danger);
      color: var(--dep-danger);
    }}
    .badge.libsrc-file-caller,
    .badge.src-file-caller,
    .badge.src-to-libsrc-caller,
    .badge.cross-area-caller,
    .badge.reverse-boundary-caller {{
      border-color: var(--dep-warning);
      color: var(--dep-warning);
    }}
    .badge.reverse-boundary-caller {{
      border-color: var(--dep-danger);
      color: var(--dep-danger);
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
    @media (max-width: 980px) {{
      main {{
        padding: 12px;
      }}
      .dep-controls, .dep-layout {{
        grid-template-columns: 1fr;
      }}
      .dep-table-wrap {{
        max-height: none;
      }}
    }}
  </style>
</head>
<body>
<main>
  <h1>{title}</h1>
  <p class="dep-meta">対象: {escaped_category}</p>
  <section class="dep-summary" id="summary"></section>
  <section class="dep-controls" aria-label="フィルター">
    <input id="search" type="search" placeholder="関数名またはファイル名で検索">
    <select id="levelFilter"><option value="">level すべて</option></select>
    <select id="classFilter"><option value="">分類すべて</option></select>
    <select id="fileFilter"><option value="">ファイルすべて</option></select>
  </section>
  <section class="dep-layout">
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
  </section>
</main>
<script>
(function () {{
  "use strict";
  const data = window.DoxyfwDependencyData || {{ summary: {{}}, functions: [], edges: [] }};
  const functions = data.functions || [];
  const edges = data.edges || [];
  const byId = new Map(functions.map((fn) => [fn.id, fn]));
  const baseOrder = new Map(functions.map((fn, index) => [fn.id, index]));
  const callees = new Map();
  const callers = new Map();
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
  let selectedId = "";
  let sortState = {{ key: "level", direction: "asc" }};

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

  function renderRows() {{
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
        selectFunction(fn.id);
      }});
      rows.appendChild(tr);
    }}
    renderNotice();
    renderSortMarks();
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
    detail.innerHTML =
      "<h2>" + escapeHtml(fn.name) + "</h2>" +
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

  function selectFunction(id) {{
    const fn = byId.get(id);
    if (!fn) return;
    selectedId = id;
    renderDetail(fn);
    renderRows();
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
    control.addEventListener("input", renderRows);
    control.addEventListener("change", renderRows);
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
  clearFilters.addEventListener("click", () => {{
    search.value = "";
    levelFilter.value = "";
    classFilter.value = "";
    fileFilter.value = "";
    renderRows();
  }});
}}());
</script>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html_text, encoding="utf-8")


def generate_report(xml_dir: Path, output_dir: Path, category_id: str) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = build_report_data(xml_dir, output_dir, category_id)
    write_data_js(output_dir, data)
    write_csv(output_dir, data)
    write_html(output_dir, category_id)
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
