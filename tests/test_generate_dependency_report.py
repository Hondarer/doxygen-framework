#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import contextlib
import io
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "templates" / "generate-dependency-report.py"
SPEC = importlib.util.spec_from_file_location("generate_dependency_report", SCRIPT_PATH)
generate_dependency_report = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generate_dependency_report
SPEC.loader.exec_module(generate_dependency_report)


def write_xml(directory, name, content):
    (directory / name).write_text(content, encoding="utf-8")


class GenerateDependencyReportTest(unittest.TestCase):
    def test_dependency_levels_and_classes(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "file_a.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__a_8c" kind="file">
    <compoundname>file_a.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="a_leaf" static="yes">
        <name>leaf</name>
        <location file="src/file_a.c" line="10" bodyfile="src/file_a.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="a_local" static="yes">
        <name>local_user</name>
        <references refid="a_leaf" compoundref="file__a_8c">leaf</references>
        <location file="src/file_a.c" line="20" bodyfile="src/file_a.c" bodystart="20"/>
      </memberdef>
      <memberdef kind="function" id="a_cross" static="no">
        <name>cross_user</name>
        <references refid="b_leaf" compoundref="file__b_8c">other_leaf</references>
        <location file="src/file_a.c" line="30" bodyfile="src/file_a.c" bodystart="30"/>
      </memberdef>
      <memberdef kind="function" id="a_to_lib" static="no">
        <name>app_user</name>
        <references refid="c_leaf" compoundref="file__c_8c">lib_leaf</references>
        <location file="src/file_a.c" line="40" bodyfile="src/file_a.c" bodystart="40"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "file_b.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__b_8c" kind="file">
    <compoundname>file_b.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="b_leaf" static="no">
        <name>other_leaf</name>
        <location file="src/file_b.c" line="10" bodyfile="src/file_b.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "file_c.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__c_8c" kind="file">
    <compoundname>file_c.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="c_leaf" static="no">
        <name>lib_leaf</name>
        <location file="libsrc/file_c.c" line="10" bodyfile="libsrc/file_c.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="c_user" static="no">
        <name>lib_user</name>
        <references refid="d_leaf" compoundref="file__d_8c">lib_other_leaf</references>
        <location file="libsrc/file_c.c" line="20" bodyfile="libsrc/file_c.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "api_8h.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api_8h" kind="file">
    <compoundname>api.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="api_export" static="no">
        <name>api_export</name>
        <location file="include/api.h" line="10" bodyfile="include/api.h" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="api_to_lib" static="no">
        <name>api_to_lib</name>
        <references refid="c_leaf" compoundref="file__c_8c">lib_leaf</references>
        <location file="include/api.h" line="20" bodyfile="include/api.h" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "internal_8h.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="internal_8h" kind="file">
    <compoundname>internal.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="internal_to_lib" static="no">
        <name>internal_to_lib</name>
        <references refid="c_leaf" compoundref="file__c_8c">lib_leaf</references>
        <location file="include_internal/internal.h" line="10" bodyfile="include_internal/internal.h" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "file_d.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__d_8c" kind="file">
    <compoundname>file_d.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="d_leaf" static="no">
        <name>lib_other_leaf</name>
        <location file="libsrc/file_d.c" line="10" bodyfile="libsrc/file_d.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(by_id["a_leaf"]["dependencyLevel"], 1)
            self.assertEqual(by_id["a_leaf"]["dependencyClass"], "leaf-static")
            self.assertEqual(by_id["b_leaf"]["dependencyLevel"], 1001)
            self.assertEqual(by_id["b_leaf"]["dependencyRank"], 1)
            self.assertEqual(by_id["b_leaf"]["dependencyClass"], "leaf-global")
            self.assertEqual(by_id["c_leaf"]["dependencyLevel"], 1003)
            self.assertEqual(by_id["a_local"]["dependencyLevel"], 2001)
            self.assertEqual(by_id["a_local"]["dependencyRank"], 2)
            self.assertEqual(by_id["a_local"]["dependencyDepth"], 1)
            self.assertEqual(by_id["a_local"]["dependencyClass"], "file-local")
            self.assertEqual(by_id["c_user"]["dependencyLevel"], 3001)
            self.assertEqual(by_id["c_user"]["dependencyClass"], "libsrc-file-caller")
            self.assertEqual(by_id["a_cross"]["dependencyLevel"], 4001)
            self.assertEqual(by_id["a_cross"]["dependencyClass"], "src-file-caller")
            self.assertEqual(by_id["a_to_lib"]["dependencyLevel"], 5001)
            self.assertEqual(by_id["a_to_lib"]["dependencyClass"], "other-to-libsrc-caller")
            self.assertEqual(by_id["a_to_lib"]["sourceArea"], "src")
            self.assertEqual(by_id["a_to_lib"]["maxCalleeArea"], "libsrc")
            self.assertEqual(by_id["a_to_lib"]["dominantCallKind"], "other-to-libsrc-caller")
            self.assertEqual(by_id["api_to_lib"]["dependencyClass"], "other-to-libsrc-caller")
            self.assertEqual(by_id["api_to_lib"]["sourceArea"], "include")
            self.assertEqual(by_id["api_to_lib"]["dominantCallKind"], "other-to-libsrc-caller")
            self.assertTrue(by_id["api_to_lib"]["isExported"])
            self.assertEqual(by_id["internal_to_lib"]["dependencyClass"], "other-to-libsrc-caller")
            self.assertEqual(by_id["internal_to_lib"]["sourceArea"], "include_internal")
            self.assertEqual(by_id["internal_to_lib"]["dominantCallKind"], "other-to-libsrc-caller")
            self.assertFalse(by_id["internal_to_lib"]["isExported"])
            self.assertEqual(by_id["a_cross"]["crossFileCalleeCount"], 1)
            self.assertTrue(by_id["api_export"]["isExported"])
            self.assertFalse(by_id["d_leaf"]["isExported"])
            self.assertEqual(data["summary"]["exportCount"], 2)
            self.assertIn("fileEdges", data)
            self.assertTrue(data["fileEdges"])
            self.assertTrue(all(edge["fromFile"] != edge["toFile"] for edge in data["fileEdges"]))
            self.assertTrue(all(edge["label"] == str(edge["weight"]) for edge in data["fileEdges"]))
            file_by_path = {row["path"]: row for row in data["files"]}
            self.assertEqual(file_by_path["include/api.h"]["exportCount"], 2)
            self.assertEqual(file_by_path["include_internal/internal.h"]["exportCount"], 0)
            self.assertTrue((output_dir / "index.html").is_file())
            self.assertTrue((output_dir / "dependency-data.js").is_file())
            self.assertTrue((output_dir / "dependency-functions.csv").is_file())
            self.assertTrue((output_dir / "dependency-files.csv").is_file())
            self.assertTrue((output_dir / "cytoscape.min.js").is_file())
            self.assertTrue((output_dir / "cytoscape.LICENSE.txt").is_file())
            self.assertTrue((output_dir / "webcola.min.js").is_file())
            self.assertTrue((output_dir / "webcola.LICENSE.txt").is_file())
            self.assertTrue((output_dir / "cytoscape-cola.js").is_file())
            self.assertTrue((output_dir / "cytoscape-cola.LICENSE.txt").is_file())
            cola_js = (output_dir / "cytoscape-cola.js").read_text(encoding="utf-8")
            self.assertIn("options.animate || options.deferPositions", cola_js)
            self.assertIn("deferPositions: false", cola_js)
            for file_row in data["files"]:
                self.assertNotIn("dominantClass", file_row)
                self.assertIn("classes", file_row)
            with (output_dir / "dependency-files.csv").open(encoding="utf-8", newline="") as f:
                fieldnames = csv.DictReader(f).fieldnames
            self.assertNotIn("dominantClass", fieldnames)
            self.assertIn("classes", fieldnames)
            self.assertIn("exportCount", fieldnames)
            with (output_dir / "dependency-functions.csv").open(encoding="utf-8", newline="") as f:
                fieldnames = csv.DictReader(f).fieldnames
            self.assertIn("isExported", fieldnames)
            self.assertIn("cycleGroupSize", fieldnames)

            data_js = (output_dir / "dependency-data.js").read_text(encoding="utf-8")
            self.assertTrue(data_js.startswith("window.DoxyfwDependencyData = "))
            payload = data_js.removeprefix("window.DoxyfwDependencyData = ").rstrip(";\n")
            payload_data = json.loads(payload)
            self.assertEqual(payload_data["summary"]["functionCount"], 11)
            self.assertIn("fileEdges", payload_data)

            index_html = (output_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn('<span class="dep-meta">対象: sample</span></h1>', index_html)
            self.assertNotIn('<p class="dep-meta">', index_html)
            self.assertIn("関数一覧", index_html)
            self.assertIn("ファイル一覧", index_html)
            self.assertIn('id="functionListPanel"', index_html)
            self.assertIn('id="fileListPanel"', index_html)
            self.assertIn('id="fileRows"', index_html)
            self.assertIn('id="fileDetail"', index_html)
            self.assertIn('id="fileSearch"', index_html)
            self.assertIn('id="clearHiddenFunctionFilters"', index_html)
            self.assertIn('id="clearHiddenFileFilters"', index_html)
            self.assertIn("function clearFunctionFilters()", index_html)
            self.assertIn("function clearFileListFilters()", index_html)
            self.assertIn('data-file-sort-key="path"', index_html)
            self.assertIn("function renderFileRows(opts)", index_html)
            self.assertIn("function syncSelectedFileRowScroll(forceScroll)", index_html)
            self.assertIn("function renderFileDetail(filePath)", index_html)
            self.assertIn("function activateTab(tabId)", index_html)
            self.assertIn('content: "初期化しています...";', index_html)
            self.assertIn('content: "レイアウトしています...";', index_html)
            self.assertIn('const immediateOverviewUpdate = tabId === "overviewPanel" && activeTab !== "overviewPanel";', index_html)
            self.assertIn("refreshActiveGraph({ immediate: immediateOverviewUpdate });", index_html)
            self.assertIn("function syncOverviewElements(targetElements, opts)", index_html)
            self.assertIn("animatePositions: !(opts && opts.hideDuringUpdate)", index_html)
            self.assertIn("function overviewSelectionSignature()", index_html)
            self.assertIn("function isOverviewRenderedSelectionCurrent()", index_html)
            self.assertIn("function renderOverviewGraph(opts)", index_html)
            self.assertIn("const renderOpts = { immediate, hideDuringUpdate: immediate, onComplete: finishImmediateRefresh, selectionSignature: overviewSelectionSignature() };", index_html)
            self.assertIn("const resetStarted = renderOverviewGraph(renderOpts);", index_html)
            self.assertIn("const viewportBeforeUpdate = hideDuringUpdate ? overviewViewport() : null;", index_html)
            self.assertIn("restoreOverviewViewport(viewportBeforeUpdate);", index_html)
            self.assertIn('overviewGraph.classList.add("layout-initializing");', index_html)
            self.assertIn('overviewGraph.classList.add("layout-relayouting");', index_html)
            self.assertIn("if (hideDuringUpdate) {", index_html)
            self.assertIn("if (immediate && isOverviewRenderedSelectionCurrent())", index_html)
            self.assertIn("if (isOverviewRenderedSelectionCurrent()) {\n      return false;\n    }", index_html)
            self.assertIn("if (immediate && isOverviewRenderedSelectionCurrent()) {\n        return;\n      }", index_html)
            self.assertNotIn(
                "if (isOverviewRenderedSelectionCurrent()) {\n      overviewCy.resize();",
                index_html,
            )
            self.assertNotIn(
                "if (immediate && isOverviewRenderedSelectionCurrent()) {\n        overviewCy.resize();",
                index_html,
            )
            self.assertIn("const finishImmediateRefresh = () =>", index_html)
            self.assertIn("requestFrame(() => requestFrame(refresh));", index_html)
            self.assertIn("activateFunctionList", index_html)
            self.assertIn("activateFileList", index_html)
            self.assertIn('id="overviewGraphMenu"', index_html)
            active_index_html = re.sub(r"<!--.*?-->", "", index_html, flags=re.DOTALL)
            self.assertNotIn('<button type="button" role="menuitem" data-svg-scope="viewport"', active_index_html)
            self.assertNotIn('<button type="button" role="menuitem" data-svg-scope="full"', active_index_html)
            self.assertIn("SVG 保存は要素数が多い場合に不安定", index_html)
            self.assertIn('data-png-scope="viewport"', index_html)
            self.assertIn('data-png-scope="full"', index_html)
            self.assertIn('data-action="fit"', index_html)
            self.assertIn('data-action="relayout"', index_html)
            self.assertIn('data-action="reset"', index_html)
            self.assertIn('role="separator"', index_html)
            self.assertIn("function buildOverviewSvg(scope)", index_html)
            self.assertIn("function downloadOverviewSvg(scope)", index_html)
            self.assertIn("function downloadOverviewPng(scope)", index_html)
            self.assertIn("overviewCy.png({", index_html)
            self.assertIn("padding: 2px 6px;", index_html)
            self.assertIn('"text-margin-y": -2', index_html)
            self.assertIn("Math.max(14, fontSize - 2)", index_html)
            self.assertIn("function overviewFitElements()", index_html)
            self.assertIn("function fitOverviewGraph()", index_html)
            self.assertIn("function overviewViewport()", index_html)
            self.assertIn("function restoreOverviewViewport(viewport)", index_html)
            self.assertIn("const OVERVIEW_STATE_CLASSES = new Set([", index_html)
            self.assertIn("function overviewStructuralClasses(classes)", index_html)
            self.assertIn("function overviewStructureElement(element)", index_html)
            self.assertIn("function requestOverviewFrame(callback)", index_html)
            self.assertIn("function setOverviewControlsInert(inert)", index_html)
            self.assertIn("function setOverviewGraphInteractionLocked(locked)", index_html)
            self.assertIn("function setOverviewLayoutRunning(running)", index_html)
            self.assertNotIn("function clearOverviewLayoutPendingLabel()", index_html)
            self.assertIn("function exponentialEaseOutProgress(t, impact)", index_html)
            self.assertIn("function overviewNodeDragIds(node)", index_html)
            self.assertIn("function isOverviewNodeDragging(nodeOrId)", index_html)
            self.assertIn("function hasOverviewDraggingNodes()", index_html)
            self.assertIn("function handleOverviewNodeGrab(node)", index_html)
            self.assertIn("function handleOverviewNodeFree(node)", index_html)
            self.assertIn('overviewCy.on("grab", "node"', index_html)
            self.assertIn('overviewCy.on("free", "node"', index_html)
            self.assertIn("Math.exp(-rate * clamped)", index_html)
            self.assertIn("const p = exponentialEaseOutProgress(t, impact);", index_html)
            self.assertIn("controls-inert", index_html)
            self.assertNotIn("onBeforeAnimation: clearOverviewLayoutPendingLabel", index_html)
            self.assertIn("layout-initializing", index_html)
            self.assertIn("layout-relayouting", index_html)
            self.assertIn(".dep-graph.layout-initializing canvas", index_html)
            self.assertIn(".dep-graph.layout-relayouting canvas", index_html)
            self.assertNotIn(".dep-graph.layout-pending canvas", index_html)
            self.assertIn("function handleOverviewGraphMenuAction(action)", index_html)
            self.assertIn("manual: true", index_html)
            self.assertIn("overviewLayoutRunning", index_html)
            self.assertIn("overviewLayoutToken", index_html)
            self.assertIn("let overviewRenderedSelectionSignature = null;", index_html)
            self.assertIn("let overviewInteractionStateBeforeLayout = null;", index_html)
            self.assertIn("let overviewDraggingNodeIds = new Set();", index_html)
            self.assertIn("let overviewDragRevision = 0;", index_html)
            self.assertIn("let overviewSyncAfterDrag = false;", index_html)
            self.assertIn("overviewCy.panningEnabled(false);", index_html)
            self.assertIn("overviewCy.zoomingEnabled(false);", index_html)
            self.assertIn("overviewCy.autoungrabify(true);", index_html)
            self.assertIn("overviewCy.boxSelectionEnabled(false);", index_html)
            self.assertIn("overviewCy.panningEnabled(overviewInteractionStateBeforeLayout.panningEnabled);", index_html)
            self.assertIn("function overviewFileEdgeLength(edge, maxLength, minLength)", index_html)
            self.assertIn("const fileEdges = (data.fileEdges && data.fileEdges.length > 0) ? data.fileEdges : buildFileEdges(edges);", index_html)
            self.assertIn("function buildFileEdges(sourceEdges)", index_html)
            self.assertNotIn("LARGE_GRAPH_FILE_LIMIT", index_html)
            self.assertNotIn("LARGE_GRAPH_EDGE_LIMIT", index_html)
            self.assertNotIn("largeGraphMode", index_html)
            self.assertNotIn("AUTO_LAYOUT", index_html)
            self.assertNotIn("LOCAL_LAYOUT_LIMIT", index_html)
            self.assertNotIn("function completeOverviewPresetLayout(fit, onComplete)", index_html)
            self.assertIn("deferPositions: manual || immediate || deferPositions", index_html)
            self.assertIn("const OVERVIEW_SYNC_CHUNK_SIZE = 25;", index_html)
            self.assertIn("let overviewSyncToken = 0;", index_html)
            self.assertIn("function nextOverviewFrame()", index_html)
            self.assertIn("function isLatestOverviewSync(token)", index_html)
            self.assertIn("function isOverviewSyncTokenActive(token)", index_html)
            self.assertIn("function targetElementIdSet(targetElements)", index_html)
            self.assertIn("function overviewSyncDiffPlan(targetElements)", index_html)
            self.assertIn("async function buildOverviewElementsAsync(token)", index_html)
            self.assertIn("async function seedOverviewInitialPositionsAsync(elements, token)", index_html)
            self.assertIn("async function resetOverviewGraphAsync(token)", index_html)
            self.assertIn("async function revealOverviewGraphAfterFit(token)", index_html)
            self.assertIn("async function overviewNodePositionsAsync(token)", index_html)
            self.assertIn("async function restoreOverviewNodePositionsAsync(positions, token)", index_html)
            self.assertIn("async function applyOverviewAnchorCentersToCurrentPositionsAsync(anchorCenters, token)", index_html)
            self.assertIn("async function anchorOverviewChildPositionsAsync(targetElements, anchorCenters, token)", index_html)
            self.assertIn("async function applyOverviewStructureDiffAsync(plan, targetElements, anchorCenters, movingNodeIds, token)", index_html)
            self.assertIn("async function processOverviewChunks(items, token, callback)", index_html)
            self.assertIn("async function applyOverviewDataAsync(targetElements, token)", index_html)
            self.assertIn("async function applyOverviewClassesAsync(targetElements, token)", index_html)
            self.assertIn("async function syncOverviewElementsAsync(targetElements, opts, token)", index_html)
            self.assertIn("function runLatestOverviewSync(opts, targetElements)", index_html)
            self.assertIn("const token = ++overviewSyncToken;", index_html)
            self.assertIn("++overviewLayoutToken;", index_html)
            self.assertIn("overviewRenderedSelectionSignature = selectionSignature;", index_html)
            self.assertIn("overviewRenderedSelectionSignature = overviewSelectionSignature();", index_html)
            self.assertIn("overviewRenderedSelectionSignature = null;", index_html)
            self.assertIn("if (!completed || !isLatestOverviewSync(token)) return;", index_html)
            self.assertIn("await nextOverviewFrame();", index_html)
            self.assertIn("const elements = await buildOverviewElementsAsync(token);", index_html)
            self.assertIn("await seedOverviewInitialPositionsAsync(elements, token)", index_html)
            self.assertIn("overviewCy.add(chunk);", index_html)
            self.assertIn("revealOverviewGraphAfterFit(token);", index_html)
            self.assertIn("setOverviewGraphInteractionLocked(false);\n    overviewCy.resize();\n    fitOverviewGraph();", index_html)
            self.assertIn("overviewCy.fit(overviewFitElements(), 30);", index_html)
            self.assertIn("resetOverviewGraphAsync(token);", index_html)
            self.assertIn("stale: stale", index_html)
            self.assertIn("missingOrdered: parentNodes.concat(childNodes, edgeElements)", index_html)
            self.assertIn("await anchorOverviewChildPositionsAsync(targetElements, anchorCenters, token)", index_html)
            self.assertIn("const structureResult = await applyOverviewStructureDiffAsync(plan, targetElements, anchorCenters, movingNodeIds, token);", index_html)
            self.assertIn("let layoutNeeded = structureResult.layoutNeeded;", index_html)
            self.assertIn("let positionDeferred = false;", index_html)
            self.assertIn("if (!isLatestOverviewSync(token)) return false;", index_html)
            self.assertIn("overviewCy.remove(overviewCy.collection(chunk));", index_html)
            self.assertIn("overviewCy.add(missingElements);", index_html)
            self.assertIn(".map(overviewStructureElement)", index_html)
            self.assertIn("await applyOverviewDataAsync(targetElements, token)", index_html)
            self.assertIn("await applyOverviewClassesAsync(targetElements, token)", index_html)
            self.assertIn("element.position(target.position);", index_html)
            self.assertIn("const layoutStartPositions = overviewNodePositions();", index_html)
            self.assertIn("const dragRevision = overviewDragRevision;", index_html)
            self.assertIn("await restoreOverviewNodePositionsAsync(layoutStartPositions, token)", index_html)
            self.assertIn("await applyOverviewAnchorCentersToCurrentPositionsAsync(anchorCenters, token)", index_html)
            self.assertIn("if (isOverviewNodeDragging(node)) return;", index_html)
            self.assertIn("if (isOverviewNodeDragging(element)) {", index_html)
            self.assertIn("positionDeferred = true;", index_html)
            self.assertIn("if (structureResult.positionDeferred || (layoutNeeded && (hasOverviewDraggingNodes() || dragRevision !== overviewDragRevision)))", index_html)
            self.assertIn("overviewSyncAfterDrag = true;", index_html)
            self.assertIn("runLatestOverviewSync({}, buildOverviewElements());", index_html)
            self.assertIn("const fragment = document.createDocumentFragment();", index_html)
            self.assertIn("function debounce(callback, delayMs)", index_html)
            self.assertIn('tr.setAttribute("data-function-row-id", fn.id);', index_html)
            self.assertIn('tr.setAttribute("data-file-row-path", file.path);', index_html)
            self.assertIn("function ensureFunctionRowSelectionRendered()", index_html)
            self.assertIn("function ensureFileRowSelectionRendered()", index_html)
            self.assertIn("const rowSelectEventName = window.PointerEvent ? \"pointerdown\" : \"mousedown\";", index_html)
            self.assertIn("rows.addEventListener(rowSelectEventName", index_html)
            self.assertIn("fileRows.addEventListener(rowSelectEventName", index_html)
            self.assertIn("debounced.cancel = () =>", index_html)
            self.assertIn("if (scheduleRenderRows) scheduleRenderRows.cancel();", index_html)
            self.assertIn("if (scheduleRenderFileRows) scheduleRenderFileRows.cancel();", index_html)
            self.assertIn("ensureFunctionRowSelectionRendered();", index_html)
            self.assertIn("ensureFileRowSelectionRendered();", index_html)
            self.assertNotIn('tr.addEventListener("click", () => {', index_html)
            self.assertIn("const scheduleRenderRows = debounce(() => renderRows(), 80);", index_html)
            self.assertIn('edgeLength: function (edge) { return overviewFileEdgeLength(edge, 140, 128); }', index_html)
            self.assertIn('idealEdgeLength: function (edge) { return overviewFileEdgeLength(edge, 128, 116); }', index_html)
            self.assertIn("function overviewSelectionState(edgeMap)", index_html)
            self.assertIn("dep-file-node-muted", index_html)
            self.assertIn('"opacity": 0.3', index_html)
            self.assertIn('"opacity": 0.25', index_html)
            self.assertIn("scrollbar-color:", index_html)
            self.assertIn('overviewGraph.addEventListener("auxclick"', index_html)
            self.assertIn('id="themeToggle"', index_html)
            self.assertIn("function applyTheme(theme, persist)", index_html)
            self.assertIn("const sccById = new Map(sccs.map((scc) => [scc.id, scc]));", index_html)
            self.assertIn("function cycleGroupFunctionIds(fn)", index_html)
            self.assertIn("function cycleGroupSection(fn)", index_html)
            self.assertIn("for (const c of cycleGroupFunctionIds(selectedFn)) ids.add(c);", index_html)

    def test_cycle_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "cycle.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="cycle_8c" kind="file">
    <compoundname>cycle.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="cycle_a" static="yes">
        <name>cycle_a</name>
        <references refid="cycle_b" compoundref="cycle_8c">cycle_b</references>
        <location file="src/cycle.c" line="10" bodyfile="src/cycle.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="cycle_b" static="yes">
        <name>cycle_b</name>
        <references refid="cycle_a" compoundref="cycle_8c">cycle_a</references>
        <location file="src/cycle.c" line="20" bodyfile="src/cycle.c" bodystart="20"/>
      </memberdef>
      <memberdef kind="function" id="cycle_c" static="yes">
        <name>cycle_c</name>
        <references refid="cycle_d" compoundref="cycle_8c">cycle_d</references>
        <location file="src/cycle.c" line="30" bodyfile="src/cycle.c" bodystart="30"/>
      </memberdef>
      <memberdef kind="function" id="cycle_d" static="yes">
        <name>cycle_d</name>
        <references refid="cycle_e" compoundref="cycle_8c">cycle_e</references>
        <location file="src/cycle.c" line="40" bodyfile="src/cycle.c" bodystart="40"/>
      </memberdef>
      <memberdef kind="function" id="cycle_e" static="yes">
        <name>cycle_e</name>
        <references refid="cycle_c" compoundref="cycle_8c">cycle_c</references>
        <location file="src/cycle.c" line="50" bodyfile="src/cycle.c" bodystart="50"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(data["summary"]["cycleGroupCount"], 2)
            self.assertEqual(by_id["cycle_a"]["dependencyLevel"], 9002)
            self.assertEqual(by_id["cycle_a"]["cycleGroupSize"], 2)
            self.assertEqual(by_id["cycle_a"]["dependencyClass"], "cycle")
            self.assertEqual(by_id["cycle_b"]["dependencyLevel"], 9002)
            self.assertEqual(by_id["cycle_b"]["cycleGroupSize"], 2)
            self.assertEqual(by_id["cycle_b"]["dependencyClass"], "cycle")
            self.assertEqual(by_id["cycle_c"]["dependencyLevel"], 9003)
            self.assertEqual(by_id["cycle_c"]["cycleGroupSize"], 3)
            self.assertLess(by_id["cycle_a"]["dependencyLevel"], by_id["cycle_c"]["dependencyLevel"])
            scc_sizes = sorted(scc["size"] for scc in data["sccs"])
            self.assertEqual(scc_sizes, [2, 3])

    def test_include_definition_prefers_libsrc_and_ignores_src_call(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "api.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api_8h" kind="file">
    <compoundname>api.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="api_decl" static="no">
        <name>api_func</name>
        <location file="include/api.h" line="10" bodyfile="include/api.h" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "api_linux.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api__linux_8c" kind="file">
    <compoundname>api_linux.c</compoundname>
    <location file="libsrc/api_linux.c"/>
    <programlisting>
      <codeline lineno="80"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="api_decl">api_func</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "api_windows.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api__windows_8c" kind="file">
    <compoundname>api_windows.c</compoundname>
    <location file="libsrc/api_windows.c"/>
    <programlisting>
      <codeline lineno="40"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="api_decl">api_func</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "tool.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="tool_8c" kind="file">
    <compoundname>tool.c</compoundname>
    <location file="src/tool.c"/>
    <sectiondef>
      <memberdef kind="function" id="tool_user" static="no">
        <name>tool_user</name>
        <references refid="api_decl" compoundref="api_8h">api_func</references>
        <location file="src/tool.c" line="20" bodyfile="src/tool.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
    <programlisting>
      <codeline lineno="20"><highlight class="normal">if (</highlight><ref refid="api_decl">api_func</ref><highlight class="normal">() == 0)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}
            edges = {(row["caller"], row["callee"]): row for row in data["edges"]}

            self.assertEqual(by_id["api_decl"]["file"], "libsrc/api_linux.c")
            self.assertEqual(by_id["api_decl"]["line"], 80)
            self.assertTrue(by_id["api_decl"]["isExported"])
            self.assertEqual(edges[("tool_user", "api_decl")]["calleeFile"], "libsrc/api_linux.c")
            self.assertNotIn("include function definition fallback to src", stderr.getvalue())

    def test_include_definition_src_fallback_warns(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "api.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="api_8h" kind="file">
    <compoundname>api.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="tool_api" static="no">
        <name>tool_api</name>
        <location file="include/api.h" line="10" bodyfile="include/api.h" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "tool.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="tool_8c" kind="file">
    <compoundname>tool.c</compoundname>
    <location file="src/tool.c"/>
    <programlisting>
      <codeline lineno="30"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="tool_api">tool_api</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(by_id["tool_api"]["file"], "src/tool.c")
            self.assertEqual(by_id["tool_api"]["line"], 30)
            self.assertIn("Warning: include function definition fallback to src", stderr.getvalue())
            self.assertIn("tool_api", stderr.getvalue())

    def test_src_header_definition_src_fallback_does_not_warn(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "svc_8h.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="svc_8h" kind="file">
    <compoundname>svc.h</compoundname>
    <sectiondef>
      <memberdef kind="function" id="svc_api" static="no">
        <name>svc_api</name>
        <location file="src/svc.h" line="10" bodyfile="src/svc.h" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "svc.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="svc_8c" kind="file">
    <compoundname>svc.c</compoundname>
    <location file="src/svc.c"/>
    <programlisting>
      <codeline lineno="30"><highlight class="keywordtype">int</highlight><highlight class="normal"><sp/></highlight><ref refid="svc_api">svc_api</ref><highlight class="normal">(void)</highlight></codeline>
    </programlisting>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "tool.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="tool_8c" kind="file">
    <compoundname>tool.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="tool_user" static="no">
        <name>tool_user</name>
        <references refid="svc_api" compoundref="svc_8h">svc_api</references>
        <location file="src/tool.c" line="20" bodyfile="src/tool.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}
            edges = {(row["caller"], row["callee"]): row for row in data["edges"]}

            self.assertEqual(by_id["svc_api"]["file"], "src/svc.c")
            self.assertEqual(by_id["svc_api"]["line"], 30)
            self.assertEqual(by_id["tool_user"]["dependencyClass"], "src-file-caller")
            self.assertEqual(by_id["tool_user"]["dominantCallKind"], "src-file-caller")
            self.assertEqual(edges[("tool_user", "svc_api")]["calleeFile"], "src/svc.c")
            self.assertNotIn("include function definition fallback to src", stderr.getvalue())

    def test_reverse_boundary_call_warns_and_uses_cross_area(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "lib.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="lib_8c" kind="file">
    <compoundname>lib.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="lib_to_src" static="no">
        <name>lib_to_src</name>
        <references refid="src_leaf" compoundref="src_8c">src_leaf</references>
        <location file="libsrc/lib.c" line="10" bodyfile="libsrc/lib.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            write_xml(
                xml_dir,
                "src.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="src_8c" kind="file">
    <compoundname>src.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="src_leaf" static="no">
        <name>src_leaf</name>
        <location file="src/src.c" line="20" bodyfile="src/src.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            self.assertEqual(by_id["lib_to_src"]["dependencyClass"], "cross-area-caller")
            self.assertEqual(by_id["lib_to_src"]["dominantCallKind"], "cross-area-caller")
            self.assertIn("Warning: reverse-boundary-caller detected", stderr.getvalue())
            self.assertIn("lib_to_src", stderr.getvalue())
            self.assertIn("src_leaf", stderr.getvalue())


    def test_c_keyword_phantom_excluded(self):
        """C キーワード (if, for など) が phantom memberdef として生成された場合に除外されることを確認する。

        Doxygen は EXTRACT_ALL=YES のとき、ソース内の制御構文 (if, for など) を
        「関数」として memberdef に出力することがある。この場合 bodyfile がソースファイルを
        指すため body_file == "" チェックでは除外できない。name が C キーワードかどうかで判定する。
        """
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "cmamng.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="cmamng_8c" kind="file">
    <compoundname>cmamng.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="cmamng_main" static="no">
        <name>main</name>
        <references refid="cmamng_if">if</references>
        <references refid="cmamng_for">for</references>
        <location file="src/prc/cmamng/cmamng.c" line="800" bodyfile="src/prc/cmamng/cmamng.c" bodystart="800"/>
      </memberdef>
      <memberdef kind="function" id="cmamng_if" static="no">
        <name>if</name>
        <location file="src/prc/cmamng/cmamng.c" line="926" bodyfile="src/prc/cmamng/cmamng.c" bodystart="926"/>
      </memberdef>
      <memberdef kind="function" id="cmamng_for" static="no">
        <name>for</name>
        <location file="src/prc/cmamng/cmamng.c" line="941" bodyfile="src/prc/cmamng/cmamng.c" bodystart="941"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            # C キーワードは function_rows に含まれない
            self.assertNotIn("cmamng_if", by_id)
            self.assertNotIn("cmamng_for", by_id)

            # main は function_rows に含まれる
            self.assertIn("cmamng_main", by_id)

            # if/for は inScopeCalleeCount にカウントされない
            self.assertEqual(by_id["cmamng_main"]["inScopeCalleeCount"], 0)

            # edges にキーワードへのエッジが生成されない
            edge_callees = {e["callee"] for e in data["edges"]}
            self.assertNotIn("cmamng_if", edge_callees)
            self.assertNotIn("cmamng_for", edge_callees)

            # reverse-boundary-caller 警告は出力されない
            self.assertNotIn("Warning: reverse-boundary-caller detected", stderr.getvalue())


    def test_external_callee_excluded(self):
        """bodyfile を持たない phantom な外部関数が正しく扱われることを確認する。

        Doxygen が標準ライブラリ関数などを呼び出し箇所を location とした phantom な
        memberdef として生成した場合 (bodyfile なし)、その関数は外部関数として扱われ:
        - 関数一覧表 (functions) に含まれない
        - 呼び出し元関数の externalCallees に名前が現れる
        - edges にエッジが生成されない
        - Warning: reverse-boundary-caller が出力されない
        """
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            xml_dir = temp_dir / "xml"
            output_dir = temp_dir / "out"
            xml_dir.mkdir()
            write_xml(
                xml_dir,
                "lib.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="lib_8c" kind="file">
    <compoundname>lib.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="lib_caller" static="no">
        <name>lib_caller</name>
        <references refid="ext_memcpy">memcpy</references>
        <references refid="ext_memset">memset</references>
        <location file="libsrc/lib.c" line="10" bodyfile="libsrc/lib.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )
            # phantom な外部関数: bodyfile/bodystart なし (call site の location のみ)
            write_xml(
                xml_dir,
                "src_phantom.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="src_8c" kind="file">
    <compoundname>src.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="ext_memcpy" static="no">
        <name>memcpy</name>
        <location file="src/src.c" line="100"/>
      </memberdef>
      <memberdef kind="function" id="ext_memset" static="no">
        <name>memset</name>
        <location file="src/src.c" line="200"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
            )

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                data = generate_dependency_report.generate_report(xml_dir, output_dir, "sample")
            by_id = {row["id"]: row for row in data["functions"]}

            # 外部関数は function_rows に含まれない
            self.assertNotIn("ext_memcpy", by_id)
            self.assertNotIn("ext_memset", by_id)

            # lib_caller は function_rows に含まれる
            self.assertIn("lib_caller", by_id)

            # externalCallees に外部関数名が現れる (名前順・重複排除)
            external_names = [ec["name"] for ec in by_id["lib_caller"]["externalCallees"]]
            self.assertEqual(external_names, ["memcpy", "memset"])

            # externalCalleeCount が正しい
            self.assertEqual(by_id["lib_caller"]["externalCalleeCount"], 2)

            # 外部関数への edges は生成されない
            edge_callees = {e["callee"] for e in data["edges"]}
            self.assertNotIn("ext_memcpy", edge_callees)
            self.assertNotIn("ext_memset", edge_callees)

            # inScopeCalleeCount は外部関数を含まない
            self.assertEqual(by_id["lib_caller"]["inScopeCalleeCount"], 0)

            # reverse-boundary-caller 警告は出力されない
            self.assertNotIn("Warning: reverse-boundary-caller detected", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
