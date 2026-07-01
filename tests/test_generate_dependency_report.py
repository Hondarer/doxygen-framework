#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import contextlib
import io
import importlib.util
import json
import os
import re
import shutil
import subprocess
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
            self.assertTrue((output_dir / "dependency-functions-utf8-bom.csv").is_file())
            self.assertTrue((output_dir / "dependency-files.csv").is_file())
            self.assertTrue((output_dir / "dependency-files-utf8-bom.csv").is_file())
            self.assertTrue((output_dir / "cytoscape.min.js").is_file())
            self.assertTrue((output_dir / "cytoscape.LICENSE.txt").is_file())
            self.assertTrue((output_dir / "webcola.min.js").is_file())
            self.assertTrue((output_dir / "webcola.LICENSE.txt").is_file())
            self.assertTrue((output_dir / "cytoscape-cola.js").is_file())
            self.assertTrue((output_dir / "cytoscape-cola.LICENSE.txt").is_file())
            self.assertFalse((output_dir / "dependency-functions.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertFalse((output_dir / "dependency-files.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertTrue((output_dir / "dependency-functions-utf8-bom.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertTrue((output_dir / "dependency-files-utf8-bom.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
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
            self.assertIn('<div class="dep-download-menu">', index_html)
            self.assertIn(
                '<button type="button" class="dep-download-menu-button" aria-expanded="false" title="関数一覧の CSV をダウンロード">関数 CSV</button>',
                index_html,
            )
            self.assertIn(
                '<button type="button" class="dep-download-menu-button" aria-expanded="false" title="ファイル一覧の CSV をダウンロード">ファイル CSV</button>',
                index_html,
            )
            self.assertIn(".dep-download-menu-items .dep-download", index_html)
            self.assertIn(".dep-download-menu-items .dep-download:hover", index_html)
            self.assertIn("border-color: transparent;", index_html)
            self.assertIn('function closeDownloadMenus(exceptMenu)', index_html)
            self.assertIn('if (event.target.closest(".dep-download-menu")) return;', index_html)
            self.assertIn('href="dependency-functions-utf8-bom.csv"', index_html)
            self.assertIn('href="dependency-functions.csv"', index_html)
            self.assertIn('href="dependency-files-utf8-bom.csv"', index_html)
            self.assertIn('href="dependency-files.csv"', index_html)
            self.assertLess(
                index_html.index('href="dependency-functions-utf8-bom.csv"'),
                index_html.index('href="dependency-functions.csv"'),
            )
            self.assertLess(
                index_html.index('href="dependency-files-utf8-bom.csv"'),
                index_html.index('href="dependency-files.csv"'),
            )
            self.assertIn('data-download-kind="json"', index_html)
            self.assertIn('data-download-kind="functions-csv" data-download-bom="true"', index_html)
            self.assertIn('data-download-kind="functions-csv"', index_html)
            self.assertIn('data-download-kind="files-csv" data-download-bom="true"', index_html)
            self.assertIn('data-download-kind="files-csv"', index_html)
            self.assertIn("const FUNCTION_CSV_FIELDS = [", index_html)
            self.assertIn("const FILE_CSV_FIELDS = [", index_html)
            self.assertIn("function csvCell(value)", index_html)
            self.assertIn("function generatedDownloadBlob(link)", index_html)
            self.assertIn("function triggerBlobDownload(blob, name)", index_html)
            self.assertIn('if (window.location.protocol !== "http:" && window.location.protocol !== "https:") {\n        fallbackDownload();', index_html)
            self.assertIn('text = "\\ufeff" + text;', index_html)
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
            self.assertIn("instantPositions: Boolean(opts && opts.hideDuringUpdate)", index_html)
            self.assertIn("const instantPositions = Boolean(opts && opts.instantPositions);", index_html)
            self.assertIn("function overviewSelectionSignature()", index_html)
            self.assertIn("function isOverviewRenderedSelectionCurrent()", index_html)
            self.assertIn("function renderOverviewGraph(opts)", index_html)
            self.assertIn("const requestedImmediate = Boolean(opts && opts.immediate);", index_html)
            self.assertIn("const immediate = requestedImmediate && !alreadyLaidOut;", index_html)
            self.assertIn("const hideDuringUpdate = requestedImmediate;", index_html)
            self.assertIn("const renderOpts = { immediate, hideDuringUpdate, initializeUnselectedFirst: immediate && selectionSignatureHasSelection(overviewSelectionSignature()), onComplete: finishImmediateRefresh, selectionSignature: overviewSelectionSignature(), force: revealed };", index_html)
            self.assertIn("const resetStarted = renderOverviewGraph(renderOpts);", index_html)
            self.assertIn("const viewportBeforeUpdate = hideDuringUpdate ? overviewViewport() : null;", index_html)
            self.assertIn("function scheduleOverviewRelayoutReveal(opts)", index_html)
            self.assertIn("scheduleOverviewRelayoutReveal({ viewport: viewportBeforeUpdate });", index_html)
            self.assertIn("restoreOverviewViewport(viewport);", index_html)
            self.assertIn("onComplete: markPhaseCLayoutDone,", index_html)
            self.assertIn('overviewGraph.classList.add("layout-initializing");', index_html)
            self.assertIn('overviewGraph.classList.add("layout-relayouting");', index_html)
            self.assertIn("if (hideDuringUpdate) {", index_html)
            # 選択変更のスキップ判定は、完了済み (rendered) だけでなく進行中 (pending) の
            # 対象も考慮する。これにより seed 窓内の選択変更で再 sync が確実に走る。
            self.assertIn("function isOverviewSelectionPendingOrRendered()", index_html)
            self.assertIn("overviewPendingSelectionSignature === overviewSelectionSignature()", index_html)
            # 初期化済みの全体マップへ別タブから戻る場合は初期化用 immediate を落とすが、
            # hideDuringUpdate により最終断面まで隠したまま非アニメーションで選択を反映する。
            self.assertIn(
                "const alreadyLaidOut = Boolean(overviewLayoutInitialized && overviewCy && overviewCy.elements().length > 0);",
                index_html,
            )
            self.assertIn("const requestedImmediate = Boolean(opts && opts.immediate);", index_html)
            self.assertIn("const immediate = requestedImmediate && !alreadyLaidOut;", index_html)
            self.assertIn("const hideDuringUpdate = requestedImmediate;", index_html)
            # 「レイアウト再実行」実行中に選択が変わると relayout の実行状態が孤児化して固着する。
            # 差し替え経路 (runLatestOverviewSync / resetOverviewGraph) で明示的に解放する。
            self.assertIn(
                "if (overviewLayoutRunning) setOverviewLayoutRunning(false);",
                index_html,
            )
            # inert 時はツールバー コンテナでなくボタンに pointer-events:none を当て、クリックが
            # 背後のグラフへ貫通して背景タップ (選択解除) を発火しないようにする。
            self.assertIn(
                ".dep-graph-shell.controls-inert .dep-graph-toolbar button {",
                index_html,
            )
            # 復活発生時 (revealed) はスキップせず再 sync を強制する。
            self.assertIn("if (!revealed && immediate && isOverviewSelectionPendingOrRendered())", index_html)
            self.assertIn("if (!(opts && opts.force) && isOverviewSelectionPendingOrRendered()) {\n      return false;\n    }", index_html)
            self.assertIn("if (!revealed && immediate && isOverviewSelectionPendingOrRendered()) {\n        return;\n      }", index_html)
            # reveal 待ちは完了 (rendered) を待つ必要があるため rendered ベースのまま。
            self.assertIn("function isOverviewRenderedSelectionCurrent()", index_html)
            # 進行中レイアウトの実停止 (旧 cola の churn を止める)。
            self.assertIn("function stopOverviewActiveLayout()", index_html)
            self.assertIn("overviewPendingSelectionSignature = selectionSignature;", index_html)
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
            self.assertNotIn("function fitSelectedOverviewFileIfNeeded()", index_html)
            self.assertIn("function overviewViewport()", index_html)
            self.assertIn("function restoreOverviewViewport(viewport)", index_html)
            self.assertIn("const OVERVIEW_STATE_CLASSES = new Set([", index_html)
            self.assertIn("function overviewStructuralClasses(classes)", index_html)
            self.assertIn("function overviewStructureElement(element)", index_html)
            self.assertIn("function requestOverviewFrame(callback)", index_html)
            self.assertIn("function setOverviewControlsInert(inert)", index_html)
            self.assertIn("function setOverviewGraphInteractionLocked(locked)", index_html)
            self.assertIn("function setOverviewLayoutRunning(running)", index_html)
            self.assertIn("isRelayoutHidden: () => Boolean(overviewGraph && overviewGraph.classList.contains(\"layout-relayouting\")),", index_html)
            self.assertIn("isPositionAnimationActive: () => Boolean(overviewPositionAnimation && overviewPositionAnimation.active),", index_html)
            self.assertNotIn("function clearOverviewLayoutPendingLabel()", index_html)
            self.assertIn("function exponentialEaseOutProgress(t, impact)", index_html)
            self.assertIn("function overviewNodeDragIds(node)", index_html)
            self.assertIn("function isOverviewNodeDragging(nodeOrId)", index_html)
            self.assertIn("function hasOverviewDraggingNodes()", index_html)
            self.assertIn("let overviewFunctionGrabInterruptedLayout = false;", index_html)
            self.assertIn("let overviewDeferredPositionAnimation = null;", index_html)
            self.assertIn("function markOverviewFunctionLayoutInterrupted(node)", index_html)
            self.assertIn("parent.children().nodes().forEach((child) => overviewPendingRelayoutNodeIds.add(child.id()));", index_html)
            self.assertIn('node.data("parent")', index_html)
            self.assertIn("function rememberOverviewUserMovedPositions(node)", index_html)
            self.assertIn('if (element.data("parent")) continue;', index_html)
            self.assertIn("function forgetOverviewNodeRuntimeState(node)", index_html)
            self.assertIn("function applyOverviewUserMovedPositions(startPositions, anchorCenters)", index_html)
            self.assertIn("function applyOverviewDeferredDragPositions(deferred)", index_html)
            self.assertIn("function handleOverviewNodeGrab(node)", index_html)
            self.assertIn("function handleOverviewNodeDrag(node)", index_html)
            self.assertIn("function handleOverviewNodeFree(node)", index_html)
            self.assertIn('overviewCy.on("grab", "node"', index_html)
            self.assertIn('overviewCy.on("drag", "node"', index_html)
            self.assertIn('overviewCy.on("free", "node"', index_html)
            # タップ起因の grab はドラッグ扱いしない (登録は drag で行う)。
            self.assertNotIn("for (const id of overviewNodeDragIds(node)) overviewDraggingNodeIds.add(id);", index_html)
            self.assertIn("Math.exp(-rate * clamped)", index_html)
            self.assertIn("const p = exponentialEaseOutProgress(t, impact);", index_html)
            # seed 配置窓のアニメーション中にファイルを掴んでも、アニメーションを破棄せず親ファイルの
            # 最新位置にアンカーした目標で関数を動かす (固着の修正)。
            self.assertIn(
                "overviewPositionAnimation = { active: true, frameId: null, targetPositions, opts: Object.assign({}, opts || {}) };",
                index_html,
            )
            self.assertIn("const parentAnchored = parent && parent.length", index_html)
            self.assertIn("return { x: pp.x + (c.x - pc.x), y: pp.y + (c.y - pc.y) };", index_html)
            # start も live アンカーし、ドラッグ後の補間が「一瞬戻る」のを防ぐ。
            self.assertIn("const liveStart = (node) => liveAnchored(node, startPositions);", index_html)
            self.assertIn("const start = liveStart(node) || target;", index_html)
            # 掴まれたルート ファイルだけをアニメーション対象から外す (compound の子は live アンカー)。
            self.assertIn('if (node.grabbed() && !node.data("parent")) return undefined;', index_html)
            # ファイルを seed 配置窓でドラッグして cola 完了前に離した場合、finishLayout の
            # restoreOverviewNodePositions が子を古い seed 座標へ戻して「一瞬戻る」のを防ぐため、
            # ユーザー移動分だけ子の start 座標も並進させる。
            self.assertIn("if (previous && element.isParent()) {", index_html)
            self.assertIn(
                "if (childStart) startPositions.set(child.id(), { x: childStart.x + dx, y: childStart.y + dy });",
                index_html,
            )
            # compound 親のドラッグで伝播する子イベントは関数操作と区別して無視する。
            self.assertIn("function isOverviewChildOfGrabbedFile(node)", index_html)
            self.assertIn("if (isOverviewChildOfGrabbedFile(node)) return;", index_html)
            self.assertIn("if (overviewFunctionGrabInterruptedLayout) {", index_html)
            self.assertIn("if (hasOverviewDraggingNodes()) {", index_html)
            self.assertIn("overviewDeferredPositionAnimation = {", index_html)
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
            self.assertIn("let overviewUserMovedNodePositions = new Map();", index_html)
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
            self.assertIn("const OVERVIEW_SYNC_CHUNK_SIZE = 100;", index_html)
            self.assertIn("let overviewSyncToken = 0;", index_html)
            self.assertIn("function nextOverviewFrame()", index_html)
            self.assertIn("function isLatestOverviewSync(token)", index_html)
            self.assertIn("function isOverviewSyncTokenActive(token)", index_html)
            self.assertIn("function targetElementIdSet(targetElements)", index_html)
            self.assertIn("function overviewSyncDiffPlan(targetElements)", index_html)
            self.assertIn("function overviewSelectionContext(selection)", index_html)
            self.assertIn("function overviewEmptySelection()", index_html)
            self.assertIn("async function buildOverviewElementsAsync(token, selection)", index_html)
            self.assertIn("async function seedOverviewInitialPositionsAsync(elements, token)", index_html)
            self.assertIn("async function resetOverviewGraphAsync(token, opts)", index_html)
            self.assertIn("async function revealOverviewGraphAfterFit(token)", index_html)
            self.assertIn("function abortOverviewInitializationOnTabLeave(previousTab, nextTab)", index_html)
            self.assertIn("async function overviewNodePositionsAsync(token)", index_html)
            self.assertIn("async function applyOverviewAnchorCentersToCurrentPositionsAsync(anchorCenters, token)", index_html)
            self.assertIn("function stabilizeOverviewCompoundCenters(targetPositions, anchorCenters)", index_html)
            self.assertIn("async function processOverviewChunks(items, token, callback)", index_html)
            # クリック反映は 3 フェーズの同期オーケストレータに集約 (クラス分離・同期ヘルパーを伴う)。
            self.assertIn("function syncOverviewElementsCore(targetElements, opts, token)", index_html)
            self.assertIn("function anchorOverviewChildPositions(targetElements, anchorCenters)", index_html)
            self.assertIn("function overviewStateClasses(classes)", index_html)
            self.assertIn("const OVERVIEW_DEFERRED_STATE_CLASSES = new Set([", index_html)
            self.assertIn("function overviewImmediateStateClasses(classes)", index_html)
            self.assertIn("function overviewDeferredStateClasses(classes)", index_html)
            self.assertIn("function overviewPhaseAClasses(targetClasses, currentClasses)", index_html)
            self.assertIn("function selectionSignatureHasSelection(signature)", index_html)
            self.assertNotIn("function overviewFocusClasses(classes)", index_html)
            # 旧非同期パス (チャンク化された構造 diff / クラス適用) は Phase A 同期化に統合し廃止。
            self.assertNotIn("async function syncOverviewElementsAsync", index_html)
            self.assertNotIn("async function applyOverviewStructureDiffAsync", index_html)
            self.assertNotIn("async function applyOverviewDataAsync", index_html)
            self.assertNotIn("async function applyOverviewClassesAsync", index_html)
            self.assertNotIn("async function anchorOverviewChildPositionsAsync", index_html)
            self.assertNotIn("async function restoreOverviewNodePositionsAsync", index_html)
            self.assertIn("function runLatestOverviewSync(opts, targetElements)", index_html)
            self.assertIn("const token = ++overviewSyncToken;", index_html)
            self.assertIn("++overviewLayoutToken;", index_html)
            self.assertIn("overviewRenderedSelectionSignature = selectionSignature;", index_html)
            self.assertIn("overviewRenderedSelectionSignature = overviewSelectionSignature();", index_html)
            self.assertIn("overviewRenderedSelectionSignature = null;", index_html)
            self.assertIn("const completed = syncOverviewElementsCore(", index_html)
            self.assertIn("await nextOverviewFrame();", index_html)
            self.assertIn("const initializeUnselectedFirst = Boolean(opts && opts.initializeUnselectedFirst && selectionSignatureHasSelection(overviewSelectionSignature()));", index_html)
            self.assertIn("const initialSelection = initializeUnselectedFirst ? overviewEmptySelection() : null;", index_html)
            self.assertIn("const elements = await buildOverviewElementsAsync(token, initialSelection);", index_html)
            self.assertIn("finishOverviewInitialLayout(token, initializeUnselectedFirst);", index_html)
            self.assertIn("initializeUnselectedFirst: immediate && selectionSignatureHasSelection(overviewSelectionSignature())", index_html)
            self.assertIn("await seedOverviewInitialPositionsAsync(elements, token)", index_html)
            self.assertIn("overviewCy.add(chunk);", index_html)
            self.assertIn("revealOverviewGraphAfterFit(token);", index_html)
            self.assertIn("setOverviewGraphInteractionLocked(false);\n    overviewCy.resize();\n    fitOverviewGraph();", index_html)
            self.assertIn("overviewCy.fit(overviewFitElements(), 30);", index_html)
            self.assertIn("resetOverviewGraphAsync(token, opts || {});", index_html)
            self.assertIn("abortOverviewInitializationOnTabLeave(previousTab, activeTab);", index_html)
            self.assertIn("overviewGraph.classList.contains(\"layout-initializing\")", index_html)
            self.assertIn("overviewCy.elements().remove();", index_html)
            self.assertIn("stale: stale", index_html)
            self.assertIn("missingOrdered: parentNodes.concat(childNodes, edgeElements)", index_html)
            # Phase A は単一 batch の同期処理 (フレーム待機なし)。
            self.assertIn("anchorOverviewChildPositions(targetElements, anchorCenters);", index_html)
            self.assertIn("const plan = overviewSyncDiffPlan(targetElements);", index_html)
            self.assertIn("let layoutNeeded = false;", index_html)
            self.assertIn("if (isEdgeElement(element) || !element.data || element.data.parent) continue;", index_html)
            self.assertIn("anchorCenters.set(element.data.id, previousPositions.get(element.data.id));", index_html)
            self.assertIn("const previousSelectionSignature = overviewRenderedSelectionSignature || JSON.stringify([\"\", \"\", \"\"]);", index_html)
            self.assertIn("const deferStateClassChanges = previousHasSelection !== nextHasSelection;", index_html)
            self.assertIn("let overviewLastClassUpdatePlan = null;", index_html)
            self.assertIn("const deferredClassTargets = [];", index_html)
            self.assertIn("let phaseCStarted = false;", index_html)
            self.assertIn("let phaseCClassesDone = false;", index_html)
            self.assertIn("let phaseCLayoutDone = true;", index_html)
            self.assertIn("const finishPhaseCIfReady = () =>", index_html)
            self.assertIn("const startPhaseC = () =>", index_html)
            self.assertIn("await processOverviewChunks(deferredClassTargets, token", index_html)
            self.assertIn("if (!isLatestOverviewSync(token)) return false;", index_html)
            self.assertIn("overviewCy.remove(staleCollection);", index_html)
            self.assertIn("staleCollection.nodes().forEach((node) => forgetOverviewNodeRuntimeState(node));", index_html)
            self.assertIn("overviewCy.add(missingElements);", index_html)
            self.assertIn("const structureElement = overviewStructureElement(target);", index_html)
            # 新規追加ノードは初回描画から最終状態クラス (ミュート等) で生成し、再表示ちらつきを防ぐ。
            self.assertIn("const fullClasses = classText(target.classes || \"\");", index_html)
            self.assertIn("if (fullClasses) structureElement.classes = fullClasses;", index_html)
            # 選択有無の境界をまたぐ場合でも、active class は Phase A、muted class は Phase C へ送る。
            self.assertIn("if (deferStateClassChanges) {", index_html)
            self.assertIn("phaseAClasses = overviewPhaseAClasses(targetClasses, element.classes().join(\" \"));", index_html)
            self.assertIn("deferredClassTargets.push({ id: target.data.id, classes: targetClasses });", index_html)
            # Phase B 前に元位置へ戻し、グループ ノードをアンカーで固定する。
            self.assertIn("restoreOverviewNodePositions(previousPositions);", index_html)
            self.assertIn("applyOverviewAnchorCentersToCurrentPositions(anchorCenters);", index_html)
            self.assertIn("applyOverviewUserMovedPositions(startPositions, anchorCenters);", index_html)
            self.assertIn("stabilizeOverviewCompoundCenters(targetPositions, anchorCenters);", index_html)
            self.assertIn("const dragRevision = overviewDragRevision;", index_html)
            self.assertIn("if (isOverviewNodeDragging(node)) return;", index_html)
            # ドラッグ中はレイアウトを後回し。
            self.assertIn("if (layoutNeeded && (hasOverviewDraggingNodes() || dragRevision !== overviewDragRevision)) {", index_html)
            # 構造変化なしのミュートは次フレームへ遅延し、強調描画を先行させる。
            self.assertIn("requestOverviewFrame(startPhaseC);", index_html)
            self.assertIn("phaseCLayoutDone = false;", index_html)
            self.assertIn("onComplete: markPhaseCLayoutDone,", index_html)
            self.assertIn("fullConvergence: true,", index_html)
            self.assertIn("unlockAllDuringLayout: true,", index_html)
            self.assertIn("const unlockAllDuringLayout = Boolean(opts && opts.unlockAllDuringLayout);", index_html)
            # Phase C は Phase B の cola tick とフレーム単位で並行処理する。
            self.assertNotIn("onBeforeAnimation: (opts && opts.hideDuringUpdate) ? null : runPhaseC,", index_html)
            # 旧 structureResult / positionDeferred ベースの分岐・位置パスは廃止。
            self.assertNotIn("structureResult.positionDeferred", index_html)
            self.assertNotIn("element.position(target.position);", index_html)
            self.assertIn("overviewSyncAfterDrag = true;", index_html)
            self.assertIn("overviewFunctionGrabInterruptedLayout = true;", index_html)
            self.assertIn("markOverviewFunctionLayoutInterrupted(node);", index_html)
            self.assertIn('if (node && node.length && node.data("parent") && (overviewActiveLayout || overviewFunctionGrabInterruptedLayout)) {', index_html)
            self.assertIn("stopOverviewActiveLayout();", index_html)
            # 中止レイアウトの pending 再投入は割り込み種別に依らず全 sync で行い、生存ノードを
            # 再投入し、stale な id は pending から取り除く (seed 表示中の選択変更でも再発火させる)。
            self.assertIn("if (overviewPendingRelayoutNodeIds.size > 0) {", index_html)
            self.assertIn("for (const id of Array.from(overviewPendingRelayoutNodeIds)) {", index_html)
            self.assertIn("overviewPendingRelayoutNodeIds.delete(id);", index_html)
            self.assertNotIn("opts && (opts.force || opts.relayoutPending) && overviewPendingRelayoutNodeIds.size > 0", index_html)
            self.assertIn("if (movingNodeIds.size > 0) layoutNeeded = true;", index_html)
            self.assertIn("runLatestOverviewSync({ relayoutPending: true }, buildOverviewElements());", index_html)
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
            self.assertIn("function overviewSelectionState(edgeMap, selection)", index_html)
            self.assertIn("dep-file-node-muted", index_html)
            self.assertIn("dep-emphasis-edge", index_html)
            self.assertIn("--dep-graph-muted-file-bg", index_html)
            self.assertIn("--dep-graph-muted-library-bg", index_html)
            self.assertIn("--dep-graph-muted-source-bg", index_html)
            self.assertIn("--dep-graph-muted-library-bg: #171526;", index_html)
            self.assertIn("--dep-graph-muted-library-border: #26233e;", index_html)
            self.assertIn("--dep-graph-muted-source-bg: #1e1526;", index_html)
            self.assertIn("--dep-graph-muted-source-border: #31233e;", index_html)
            self.assertIn("emphasisFileEdges", index_html)
            self.assertIn("function overviewSvgOrderedElements()", index_html)
            self.assertIn("styleOf: (id, names) =>", index_html)
            self.assertIn("svgDrawOrder: () => overviewSvgOrderedElements().map((element) => element.id()),", index_html)
            self.assertNotIn('"opacity": 0.3', index_html)
            self.assertNotIn('"opacity": 0.25', index_html)
            # エッジはアルファでなく背景との混色で不透明に描く。矢印が下地を切り抜くのを防ぐため。
            self.assertIn("function blendColor(fg, bg, alpha)", index_html)
            self.assertIn("const flatEdge = (name, fallback) => blendColor(", index_html)
            self.assertIn("scrollbar-color:", index_html)
            self.assertIn("--dep-table-scrollbar-thumb: #888888;", index_html)
            self.assertIn("--dep-table-scrollbar-thumb-hover: #757575;", index_html)
            self.assertIn("--dep-table-scrollbar-thumb: #676767;", index_html)
            self.assertIn("--dep-table-scrollbar-thumb-hover: #787878;", index_html)
            self.assertIn("scrollbar-color: var(--dep-table-scrollbar-thumb) var(--dep-input-bg);", index_html)
            self.assertIn(".dep-table-wrap::-webkit-scrollbar-thumb,\n    .dep-detail::-webkit-scrollbar-thumb {\n      background: var(--dep-table-scrollbar-thumb);", index_html)
            self.assertIn(".dep-table-wrap::-webkit-scrollbar-thumb:hover,\n    .dep-detail::-webkit-scrollbar-thumb:hover {\n      background: var(--dep-table-scrollbar-thumb-hover);", index_html)
            self.assertIn(".dep-filter-clear:hover {\n      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-bg));", index_html)
            self.assertIn(".dep-graph-toolbar button:hover {\n      background: color-mix(in srgb, var(--dep-accent) 12%, var(--dep-bg));", index_html)
            self.assertIn('overviewGraph.addEventListener("auxclick"', index_html)
            self.assertIn('id="themeToggle"', index_html)
            self.assertIn("function applyTheme(theme, persist)", index_html)
            self.assertIn("const sccById = new Map(sccs.map((scc) => [scc.id, scc]));", index_html)
            self.assertIn("function cycleGroupFunctionIds(fn)", index_html)
            self.assertIn("function cycleGroupSection(fn)", index_html)
            self.assertIn("for (const c of cycleGroupFunctionIds(selectedFn)) ids.add(c);", index_html)
            # ファイル非表示 (右クリック) 機能の埋め込み確認。
            self.assertIn("function hideOverviewFile(filePath)", index_html)
            self.assertIn("function reconcileHiddenOverviewFiles()", index_html)
            self.assertIn("function updateOverviewHiddenNotice()", index_html)
            self.assertIn('overviewCy.on("cxttap", "node.dep-file-node"', index_html)
            self.assertIn('data-action="hide-file"', index_html)
            # 非表示ファイルの再表示ボタン (押せるボタンとして全件復活する)。
            self.assertIn('<button type="button" id="overviewHiddenNotice"', index_html)
            self.assertIn("非表示ファイルの再表示", index_html)
            self.assertIn(".dep-graph-hidden-notice", index_html)
            self.assertIn("function revealAllOverviewFiles()", index_html)
            self.assertIn("revealAll: () => revealAllOverviewFiles(),", index_html)
            self.assertIn("function suppressOverviewBackgroundTap()", index_html)
            self.assertIn("function isOverviewBackgroundTapSuppressed()", index_html)
            self.assertIn("revealAllOverviewFiles();", index_html)
            self.assertIn("event.stopPropagation();", index_html)
            self.assertIn("if (isOverviewBackgroundTapSuppressed()) return;", index_html)
            # 非表示ファイルは要素生成から除外する。
            self.assertIn("if (hiddenOverviewFiles.has(file.path)) continue;", index_html)
            self.assertIn(".filter((fn) => !hiddenOverviewFiles.has(fn.file))", index_html)
            # 初期化で全復活。
            self.assertIn("hiddenOverviewFiles.clear();", index_html)

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


PROBE_SCRIPT = Path(__file__).resolve().parent / "overview_interaction_probe.js"
LARGE_LAYOUT_PROBE_SCRIPT = Path(__file__).resolve().parent / "overview_large_layout_probe.js"
SCOPE_LAYOUT_PROBE_SCRIPT = Path(__file__).resolve().parent / "overview_scope_layout_probe.js"
RESELECT_PROBE_SCRIPT = Path(__file__).resolve().parent / "overview_reselect_probe.js"
PUPPETEER_DIR = (
    Path(__file__).resolve().parents[2] / "docsfw" / "bin" / "node_modules" / "puppeteer"
)


def _node_binary():
    return shutil.which("node")


def _puppeteer_available():
    if os.environ.get("DOXYFW_TEST_PUPPETEER"):
        return True
    return PUPPETEER_DIR.is_dir()


def _style_number(style, key):
    return float(style[key])


def _style_color_luminance(value):
    text_value = str(value).strip()
    if text_value.startswith("#") and len(text_value) == 7:
        red = int(text_value[1:3], 16)
        green = int(text_value[3:5], 16)
        blue = int(text_value[5:7], 16)
    else:
        match = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", text_value)
        if not match:
            raise AssertionError("色を解析できません: {}".format(value))
        red = int(match.group(1))
        green = int(match.group(2))
        blue = int(match.group(3))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


# file_a -> file_b への呼び出しがあり、file_c はどこともつながらない 3 ファイル構成。
# ファイル選択時に file_b は興味対象 (非ミュート)、file_c は興味対象外 (ミュート) になる。
OVERVIEW_FIXTURE = {
    "file_a.xml": """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__a_8c" kind="file">
    <compoundname>file_a.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="a_helper" static="yes">
        <name>a_helper</name>
        <location file="src/file_a.c" line="10" bodyfile="src/file_a.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="a_util" static="yes">
        <name>a_util</name>
        <location file="src/file_a.c" line="18" bodyfile="src/file_a.c" bodystart="18"/>
      </memberdef>
      <memberdef kind="function" id="a_h1" static="yes">
        <name>a_h1</name>
        <location file="src/file_a.c" line="40" bodyfile="src/file_a.c" bodystart="40"/>
      </memberdef>
      <memberdef kind="function" id="a_h2" static="yes">
        <name>a_h2</name>
        <location file="src/file_a.c" line="48" bodyfile="src/file_a.c" bodystart="48"/>
      </memberdef>
      <memberdef kind="function" id="a_h3" static="yes">
        <name>a_h3</name>
        <location file="src/file_a.c" line="56" bodyfile="src/file_a.c" bodystart="56"/>
      </memberdef>
      <memberdef kind="function" id="a_h4" static="yes">
        <name>a_h4</name>
        <location file="src/file_a.c" line="64" bodyfile="src/file_a.c" bodystart="64"/>
      </memberdef>
      <memberdef kind="function" id="a_h5" static="yes">
        <name>a_h5</name>
        <location file="src/file_a.c" line="72" bodyfile="src/file_a.c" bodystart="72"/>
      </memberdef>
      <memberdef kind="function" id="a_main" static="no">
        <name>a_main</name>
        <references refid="a_helper" compoundref="file__a_8c">a_helper</references>
        <references refid="a_util" compoundref="file__a_8c">a_util</references>
        <references refid="a_h1" compoundref="file__a_8c">a_h1</references>
        <references refid="a_h2" compoundref="file__a_8c">a_h2</references>
        <references refid="a_h3" compoundref="file__a_8c">a_h3</references>
        <references refid="a_h4" compoundref="file__a_8c">a_h4</references>
        <references refid="a_h5" compoundref="file__a_8c">a_h5</references>
        <references refid="b_entry" compoundref="file__b_8c">b_entry</references>
        <location file="src/file_a.c" line="30" bodyfile="src/file_a.c" bodystart="30"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
    "file_b.xml": """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__b_8c" kind="file">
    <compoundname>file_b.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="b_leaf" static="yes">
        <name>b_leaf</name>
        <location file="src/file_b.c" line="10" bodyfile="src/file_b.c" bodystart="10"/>
      </memberdef>
      <memberdef kind="function" id="b_entry" static="no">
        <name>b_entry</name>
        <references refid="b_leaf" compoundref="file__b_8c">b_leaf</references>
        <references refid="a_helper" compoundref="file__a_8c">a_helper</references>
        <location file="src/file_b.c" line="20" bodyfile="src/file_b.c" bodystart="20"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
    "file_c.xml": """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__c_8c" kind="file">
    <compoundname>file_c.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="c_alone" static="no">
        <name>c_alone</name>
        <location file="src/file_c.c" line="10" bodyfile="src/file_c.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
    "file_f.xml": """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__f_8c" kind="file">
    <compoundname>file_f.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="f_other" static="no">
        <name>f_other</name>
        <location file="generated/file_f.c" line="10" bodyfile="generated/file_f.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
    "file_g.xml": """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__g_8c" kind="file">
    <compoundname>file_g.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="g_lib" static="no">
        <name>g_lib</name>
        <location file="libsrc/file_g.c" line="10" bodyfile="libsrc/file_g.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
    # file_d と file_e はファイルをまたぐ循環参照 (d_cyc <-> e_cyc)。循環関数の選択時に
    # 限り、循環相手の所属ファイルが非表示でも復活させる例外条件の検証に使う。
    "file_d.xml": """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__d_8c" kind="file">
    <compoundname>file_d.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="d_cyc" static="no">
        <name>d_cyc</name>
        <references refid="e_cyc" compoundref="file__e_8c">e_cyc</references>
        <location file="src/file_d.c" line="10" bodyfile="src/file_d.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
    "file_e.xml": """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="file__e_8c" kind="file">
    <compoundname>file_e.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="e_cyc" static="no">
        <name>e_cyc</name>
        <references refid="d_cyc" compoundref="file__d_8c">d_cyc</references>
        <location file="src/file_e.c" line="10" bodyfile="src/file_e.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""",
}


@unittest.skipUnless(_node_binary(), "node が見つからないため Puppeteer テストをスキップ")
@unittest.skipUnless(_puppeteer_available(), "puppeteer が見つからないため Puppeteer テストをスキップ")
class OverviewInteractionTest(unittest.TestCase):
    """全体マップのクリック反映を Puppeteer で検証する (3 フェーズ モデル)。"""

    def _generate_report(self, temp_dir):
        xml_dir = temp_dir / "xml"
        output_dir = temp_dir / "report"
        xml_dir.mkdir()
        output_dir.mkdir()
        for name, content in OVERVIEW_FIXTURE.items():
            write_xml(xml_dir, name, content)
        generate_dependency_report.generate_report(xml_dir, output_dir, "test")
        return output_dir / "index.html"

    def _generate_large_layout_report(self, temp_dir):
        xml_dir = temp_dir / "xml"
        output_dir = temp_dir / "report"
        xml_dir.mkdir()
        output_dir.mkdir()

        members = []
        for index in range(60):
            fn_id = "f_{:02d}".format(index)
            references = ""
            if index == 0:
                references = "".join(
                    '        <references refid="f_{0:02d}" compoundref="big__file_8c">func_{0:02d}</references>\n'.format(i)
                    for i in range(1, 60)
                )
            members.append(
                """      <memberdef kind="function" id="{id}" static="yes">
        <name>func_{index:02d}</name>
{references}        <location file="src/big_file.c" line="{line}" bodyfile="src/big_file.c" bodystart="{line}"/>
      </memberdef>
""".format(id=fn_id, index=index, references=references, line=index + 10)
            )
        write_xml(
            xml_dir,
            "big_file.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="big__file_8c" kind="file">
    <compoundname>big_file.c</compoundname>
    <sectiondef>
{members}    </sectiondef>
  </compounddef>
</doxygen>
""".format(members="".join(members)),
        )
        for index in range(1, 5):
            write_xml(
                xml_dir,
                "other_{}.xml".format(index),
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="other__{index}_8c" kind="file">
    <compoundname>other_{index}.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="o_{index}" static="yes">
        <name>other_{index}</name>
        <location file="src/other_{index}.c" line="10" bodyfile="src/other_{index}.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""".format(index=index),
            )
        generate_dependency_report.generate_report(xml_dir, output_dir, "large-layout")
        return output_dir / "index.html"

    def _generate_scope_layout_report(self, temp_dir, collapsed_count=30, hub_functions=12):
        # Phase B の部分コレクション化を検証するためのフィクスチャ。
        # 崩壊 (関数 1 つ) ファイルを多数 + 関数を複数持つ対象ファイル (hub.c) 1 つ。
        # 対象ファイルを選択したとき、cola へ投入されるのは hub.c とその関数だけで、
        # 崩壊ファイル群は含まれないことを検証する。
        xml_dir = temp_dir / "xml"
        output_dir = temp_dir / "report"
        xml_dir.mkdir()
        output_dir.mkdir()

        members = []
        for index in range(hub_functions):
            members.append(
                """      <memberdef kind="function" id="h_{index:02d}" static="yes">
        <name>hub_{index:02d}</name>
        <location file="src/hub.c" line="{line}" bodyfile="src/hub.c" bodystart="{line}"/>
      </memberdef>
""".format(index=index, line=index + 10)
            )
        write_xml(
            xml_dir,
            "hub.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="hub_8c" kind="file">
    <compoundname>hub.c</compoundname>
    <sectiondef>
{members}    </sectiondef>
  </compounddef>
</doxygen>
""".format(members="".join(members)),
        )
        for index in range(collapsed_count):
            write_xml(
                xml_dir,
                "leaf_{}.xml".format(index),
                """<?xml version="1.0" encoding="UTF-8"?>
<doxygen>
  <compounddef id="leaf__{index}_8c" kind="file">
    <compoundname>leaf_{index}.c</compoundname>
    <sectiondef>
      <memberdef kind="function" id="l_{index}" static="yes">
        <name>leaf_{index}</name>
        <location file="src/leaf_{index}.c" line="10" bodyfile="src/leaf_{index}.c" bodystart="10"/>
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""".format(index=index),
            )
        generate_dependency_report.generate_report(xml_dir, output_dir, "scope-layout")
        return output_dir / "index.html"

    def _run_probe(self, index_html):
        result = subprocess.run(
            [_node_binary(), str(PROBE_SCRIPT), str(index_html)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg="probe failed:\n{}\n{}".format(result.stdout, result.stderr),
        )
        line = next(
            (ln for ln in result.stdout.splitlines() if ln.startswith("RESULT ")),
            None,
        )
        self.assertIsNotNone(line, msg="RESULT 行が見つからない:\n{}".format(result.stdout))
        return json.loads(line[len("RESULT "):])

    def _run_large_layout_probe(self, index_html):
        result = subprocess.run(
            [_node_binary(), str(LARGE_LAYOUT_PROBE_SCRIPT), str(index_html), "src/big_file.c"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg="large layout probe failed:\n{}\n{}".format(result.stdout, result.stderr),
        )
        line = next(
            (ln for ln in result.stdout.splitlines() if ln.startswith("RESULT ")),
            None,
        )
        self.assertIsNotNone(line, msg="RESULT 行が見つからない:\n{}".format(result.stdout))
        return json.loads(line[len("RESULT "):])

    def _run_scope_layout_probe(self, index_html, file_path="src/hub.c", samples=5):
        result = subprocess.run(
            [_node_binary(), str(SCOPE_LAYOUT_PROBE_SCRIPT), str(index_html), file_path, str(samples)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg="scope layout probe failed:\n{}\n{}".format(result.stdout, result.stderr),
        )
        line = next(
            (ln for ln in result.stdout.splitlines() if ln.startswith("RESULT ")),
            None,
        )
        self.assertIsNotNone(line, msg="RESULT 行が見つからない:\n{}".format(result.stdout))
        return json.loads(line[len("RESULT "):])

    def _run_reselect_probe(self, index_html, file_path="src/big_file.c", function_id="f_01"):
        result = subprocess.run(
            [_node_binary(), str(RESELECT_PROBE_SCRIPT), str(index_html), file_path, function_id],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg="reselect probe failed:\n{}\n{}".format(result.stdout, result.stderr),
        )
        line = next(
            (ln for ln in result.stdout.splitlines() if ln.startswith("RESULT ")),
            None,
        )
        self.assertIsNotNone(line, msg="RESULT 行が見つからない:\n{}".format(result.stdout))
        return json.loads(line[len("RESULT "):])

    def test_overview_reselect_during_seed(self):
        # 無選択 -> ファイル選択 (Phase B 開始) -> seed 表示中に file 内の関数を実クリックで選択。
        # 中止で seed に取り残された関数が再レイアウトされる (Phase B 再発火) ことを検証する。
        with tempfile.TemporaryDirectory() as temp_dir_text:
            index_html = self._generate_large_layout_report(Path(temp_dir_text))
            data = self._run_reselect_probe(index_html, "src/big_file.c", "f_01")

            self.assertEqual(data["pageErrors"], [], msg=str(data["pageErrors"]))
            self.assertTrue(data["seedCaught"], msg="seed 窓 (cola 計算中) を捉えられていない: " + str(data))
            self.assertTrue(data["layoutRunningAtSeed"], msg="クリック時に cola が実行中でない: " + str(data))
            self.assertTrue(data["clicked"], msg="関数ノードを実クリックできていない: " + str(data))

            # 関数選択が反映され、新選択のレイアウトが完了している。
            # 実クリックは seed 円上で重なる隣接関数を掴むことがあるため、特定 id ではなく
            # 「いずれかの関数が選択されセンターになっている」ことを検証する。
            self.assertTrue(data["renderedMatchesCurrent"], msg=str(data))
            self.assertTrue(
                data["selectedFunctionId"].startswith("f_"),
                msg="関数が選択されていない: " + str(data),
            )
            self.assertTrue(data["fnIsCenter"], msg="選択関数がセンターノードになっていない: " + str(data))

            # 失火の解消: 中止された Phase B の後、再レイアウトが発火して layoutRunCount が増える。
            # 修正前は再投入されず Phase B がスキップされ、この値は増えない。
            self.assertGreater(
                data["layoutRunCountAfter"], data["layoutRunCountAtSeed"], msg=str(data)
            )
            # 残存関数 (f_00, f_01) が seed から移動している (取り残されていない)。
            self.assertGreaterEqual(data["movedFromSeed"], 1, msg=str(data))

    def test_overview_scope_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            collapsed_count = 30
            hub_functions = 12
            index_html = self._generate_scope_layout_report(
                Path(temp_dir_text), collapsed_count=collapsed_count, hub_functions=hub_functions
            )
            data = self._run_scope_layout_probe(index_html)

            self.assertEqual(data["pageErrors"], [], msg=str(data["pageErrors"]))
            self.assertTrue(data["renderedMatchesCurrent"])
            self.assertEqual(data["childLayout"]["count"], hub_functions)

            # --- スコープが効いている証拠 ---
            # 全ノード数は「hub + hub の関数 + 崩壊ファイル群」。
            self.assertGreaterEqual(data["totalNodeCount"], collapsed_count + hub_functions + 1)
            # cola に投入されたのは hub とその関数だけ (崩壊ファイル群は含まれない)。
            # 上限は hub ファイル 1 + 関数 hub_functions に余裕を持たせた値。
            self.assertLessEqual(
                data["scopedLayoutNodeCount"], hub_functions + 2, msg=str(data)
            )
            # 崩壊ファイル群を確実に除外している (全ノード数よりはるかに小さい)。
            self.assertLess(
                data["scopedLayoutNodeCount"], data["totalNodeCount"] - collapsed_count + 2,
                msg=str(data),
            )

            # --- レイアウト品質: seed からバランスよく分散する ---
            # hub の関数は seed のコンパクトな塊ではなく、hub-spoke で広がる。
            self.assertLessEqual(data["childLayout"]["aspectRatio"], 2.2, msg=str(data["childLayout"]))
            self.assertGreaterEqual(
                max(data["childLayout"]["width"], data["childLayout"]["height"]),
                200.0,
                msg=str(data["childLayout"]),
            )

            # --- 改善効果の計測 (全グラフ経路 vs 部分コレクション経路) ---
            measure = data["measure"]
            # 部分コレクション経路の投入ノード数は全グラフ経路より確実に少ない。
            self.assertLess(
                measure["scoped"]["nodeCount"], measure["full"]["nodeCount"], msg=str(measure)
            )
            self.assertLessEqual(measure["scoped"]["nodeCount"], hub_functions + 2, msg=str(measure))
            self.assertGreaterEqual(
                measure["full"]["nodeCount"], collapsed_count + hub_functions + 1, msg=str(measure)
            )

    def test_overview_large_file_function_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            index_html = self._generate_large_layout_report(Path(temp_dir_text))
            data = self._run_large_layout_probe(index_html)

            self.assertEqual(data["pageErrors"], [], msg=str(data["pageErrors"]))
            self.assertTrue(data["renderedMatchesCurrent"])
            self.assertEqual(data["childLayout"]["count"], 60)
            self.assertLessEqual(data["childLayout"]["aspectRatio"], 1.8)
            self.assertAlmostEqual(data["viewportBefore"]["zoom"], data["viewportAfter"]["zoom"], delta=0.001)
            self.assertAlmostEqual(data["viewportBefore"]["pan"]["x"], data["viewportAfter"]["pan"]["x"], delta=0.5)
            self.assertAlmostEqual(data["viewportBefore"]["pan"]["y"], data["viewportAfter"]["pan"]["y"], delta=0.5)
            self.assertEqual(data["movedFileCount"], 0, msg=str(data["movedTop"]))

            # --- seed 配置窓のアニメーション中にファイルをドラッグ ---
            # 修正前は grab で位置アニメーションが破棄され onComplete が失われて固着 (rendered が
            # ["","",""] のまま) した。修正後はアニメーションを止めず、関数を親ファイルの最新位置に
            # アンカーした目標で動かすため、ファイルへ追従しつつレイアウト結果へ収束して整定する。
            seed_drag = data["fileDragDuringAnimation"]
            self.assertTrue(
                seed_drag["animationCaught"],
                msg="位置アニメーション窓を再現できていない",
            )
            # 固着しない。
            self.assertFalse(seed_drag["stuck"])
            self.assertTrue(seed_drag["final"]["renderedMatchesCurrent"])
            self.assertEqual(seed_drag["final"]["count"], 60)
            # レイアウト結果が採用される: 関数群は seed のコンパクトな塊 (幅 ~256) ではなく、
            # 非ドラッグ時と同等の広がりまで収束する (cola の再選択ばらつきを見込み下限で判定)。
            self.assertGreaterEqual(seed_drag["baselineSpan"], 700.0)
            self.assertGreaterEqual(seed_drag["final"]["span"], 700.0, msg=str(seed_drag))
            self.assertGreaterEqual(
                max(sample["span"] for sample in seed_drag["dragSamples"]),
                700.0,
                msg=str(seed_drag["dragSamples"]),
            )
            # 関数群はドラッグされたファイルへ追従し、近傍に留まる (散逸しない)。
            self.assertIsNotNone(seed_drag["final"]["childCenterToFile"])
            self.assertLessEqual(seed_drag["final"]["childCenterToFile"], 80.0, msg=str(seed_drag))
            # ドラッグ中もファイルへ追従し続ける (補間の起点も live アンカーするため、ドラッグ前の
            # 座標から始まって「一瞬戻る/取り残される」動きにならない)。
            drag_dists = [
                sample["childCenterToFile"]
                for sample in seed_drag["dragSamples"]
                if sample["childCenterToFile"] is not None
            ]
            self.assertTrue(drag_dists)
            self.assertLessEqual(max(drag_dists), 120.0, msg=str(seed_drag["dragSamples"]))
            # viewport (zoom/pan) は保持される。
            self.assertAlmostEqual(
                seed_drag["viewportBefore"]["zoom"], seed_drag["viewportAfter"]["zoom"], delta=0.001
            )
            self.assertAlmostEqual(
                seed_drag["viewportBefore"]["pan"]["x"], seed_drag["viewportAfter"]["pan"]["x"], delta=0.5
            )
            self.assertAlmostEqual(
                seed_drag["viewportBefore"]["pan"]["y"], seed_drag["viewportAfter"]["pan"]["y"], delta=0.5
            )

            # --- Phase B の単一子ゼロコスト化 ---
            # 単一関数ファイル (other_1.c) の選択ではファイル内配置が自明 (親中心) なため、
            # cola (Phase B) は起動しない。無選択遷移でも起動しない。複数関数ファイル
            # (big_file.c) の選択では Phase B が本来必要なので起動する。
            skip = data["layoutSkip"]
            self.assertEqual(skip["singleChildCount"], 1, msg=str(skip))
            # 単一子ファイル選択: cola 起動回数が増えない (Phase B スキップ)。
            self.assertEqual(
                skip["countAfterSingle"], skip["countBeforeSingle"], msg=str(skip)
            )
            # 無選択遷移: cola 起動回数が増えない。
            self.assertEqual(
                skip["countAfterDeselect"], skip["countAfterSingle"], msg=str(skip)
            )
            # 複数子ファイル選択: cola が起動する (Phase B 継続の担保)。
            self.assertGreater(
                skip["countAfterMulti"], skip["countAfterDeselect"], msg=str(skip)
            )
            # 単一子は親ファイル中心へ配置される。
            self.assertIsNotNone(skip["singleChildCenterToFile"])
            self.assertLessEqual(skip["singleChildCenterToFile"], 5.0, msg=str(skip))

    def test_overview_click_phases(self):
        with tempfile.TemporaryDirectory() as temp_dir_text:
            index_html = self._generate_report(Path(temp_dir_text))
            data = self._run_probe(index_html)

            # JS 実行時エラーが無いこと (CSS 欠落 ERR_FILE_NOT_FOUND は除外済み)。
            self.assertEqual(data["pageErrors"], [], msg=str(data["pageErrors"]))

            # 初期はファイル ノードのみ。
            self.assertEqual(
                sorted(data["initialNodeIds"]),
                [
                    "generated/file_f.c",
                    "libsrc/file_g.c",
                    "src/file_a.c",
                    "src/file_b.c",
                    "src/file_c.c",
                    "src/file_d.c",
                    "src/file_e.c",
                ],
            )
            initial_tab_interrupt = data["initialTabInterrupt"]
            self.assertTrue(initial_tab_interrupt["initializing"])
            self.assertEqual(initial_tab_interrupt["elementCount"], 0)
            self.assertIsNone(initial_tab_interrupt["renderedSignature"])
            self.assertIsNone(initial_tab_interrupt["pendingSignature"])
            self.assertFalse(initial_tab_interrupt["afterReturn"]["initializing"])
            self.assertGreater(initial_tab_interrupt["afterReturn"]["elementCount"], 0)
            self.assertTrue(initial_tab_interrupt["afterReturn"]["renderedMatchesCurrent"])
            self.assertTrue(initial_tab_interrupt["afterReturn"]["isReady"])

            # file_a の関数 (a_helper, a_util, a_h1..a_h5, a_main の 8 個)。
            file_a_functions = ["a_h1", "a_h2", "a_h3", "a_h4", "a_h5", "a_helper", "a_main", "a_util"]

            # --- 未初期化のまま一覧表で選択してから全体マップを初回表示 ---
            # 空選択で初期レイアウトした後、選択反映レイアウトを行うため、いったん全体マップを
            # 表示してから同じファイルを選んだ場合と同じノード位置になる。
            initial_hidden_selection = data["initialHiddenSelection"]
            self.assertEqual(
                initial_hidden_selection["beforeActivate"]["currentSignature"],
                json.dumps(["", "src/file_a.c", ""], separators=(",", ":")),
            )
            self.assertEqual(initial_hidden_selection["beforeActivate"]["elementCount"], 0)
            self.assertFalse(initial_hidden_selection["hiddenDroppedBeforeReady"])
            self.assertEqual(
                initial_hidden_selection["baseline"]["nodeIds"],
                initial_hidden_selection["hiddenFirst"]["nodeIds"],
            )
            self.assertEqual(
                initial_hidden_selection["hiddenFirst"]["renderedSignature"],
                json.dumps(["", "src/file_a.c", ""], separators=(",", ":")),
            )
            self.assertIn("dep-selected-file", initial_hidden_selection["hiddenFirst"]["selectedFileClasses"])
            self.assertTrue(initial_hidden_selection["hiddenFirst"]["fileCMuted"])
            self.assertEqual(sorted(initial_hidden_selection["hiddenFirst"]["functionNodes"]), file_a_functions)
            self.assertLessEqual(
                initial_hidden_selection["maxDelta"], 0.5, msg=str(initial_hidden_selection["movedTop"])
            )

            # --- 表示スタイル: opacity ではなく色と z-order で状態を表現 ---
            style_state = data["styleState"]
            light_style = style_state["light"]
            self.assertIn("dep-emphasis-edge", light_style["outgoingClasses"])
            self.assertNotIn("dep-base-edge-muted", light_style["outgoingClasses"])
            self.assertIn("dep-emphasis-edge", light_style["incomingClasses"])
            self.assertNotIn("dep-base-edge-muted", light_style["incomingClasses"])
            self.assertIn("dep-base-edge-muted", light_style["mutedEdgeClasses"])
            self.assertIn("dep-file-node-muted", light_style["sourceMutedClasses"])
            self.assertIn("dep-file-source-node", light_style["sourceMutedClasses"])
            self.assertIn("dep-file-node-muted", light_style["libraryMutedClasses"])
            self.assertIn("dep-file-library-node", light_style["libraryMutedClasses"])
            self.assertIn("dep-file-node-muted", light_style["defaultMutedClasses"])
            self.assertNotIn("dep-file-source-node", light_style["defaultMutedClasses"])
            self.assertNotIn("dep-file-library-node", light_style["defaultMutedClasses"])

            outgoing_edge_style = light_style["edgeStyles"]["outgoing"]
            incoming_edge_style = light_style["edgeStyles"]["incoming"]
            muted_edge_style = light_style["edgeStyles"]["muted"]
            # アルファを廃し不透明 (opacity 1) で描く。状態は色と z 順で表現する。
            self.assertAlmostEqual(_style_number(outgoing_edge_style, "opacity"), 1.0)
            self.assertAlmostEqual(_style_number(incoming_edge_style, "opacity"), 1.0)
            self.assertAlmostEqual(_style_number(muted_edge_style, "opacity"), 1.0)
            self.assertEqual(outgoing_edge_style["color"], outgoing_edge_style["line-color"])
            self.assertEqual(incoming_edge_style["color"], incoming_edge_style["line-color"])
            self.assertEqual(muted_edge_style["color"], muted_edge_style["line-color"])
            # 矢印を線と同じ見た目にする本修正の要: 矢印色は線色と一致する。
            self.assertEqual(outgoing_edge_style["target-arrow-color"], outgoing_edge_style["line-color"])
            self.assertEqual(incoming_edge_style["target-arrow-color"], incoming_edge_style["line-color"])
            self.assertEqual(muted_edge_style["target-arrow-color"], muted_edge_style["line-color"])
            self.assertEqual(outgoing_edge_style["z-index-compare"], "manual")
            self.assertEqual(incoming_edge_style["z-index-compare"], "manual")
            self.assertEqual(muted_edge_style["z-index-compare"], "manual")
            self.assertLess(_style_number(muted_edge_style, "z-index"), _style_number(incoming_edge_style, "z-index"))
            self.assertEqual(incoming_edge_style["line-color"], outgoing_edge_style["line-color"])
            self.assertEqual(_style_number(incoming_edge_style, "z-index"), _style_number(outgoing_edge_style, "z-index"))

            selected_node_style = light_style["nodeStyles"]["selected"]
            related_node_style = light_style["nodeStyles"]["normalRelated"]
            source_muted_style = light_style["nodeStyles"]["sourceMuted"]
            library_muted_style = light_style["nodeStyles"]["libraryMuted"]
            default_muted_style = light_style["nodeStyles"]["defaultMuted"]
            self.assertAlmostEqual(_style_number(source_muted_style, "opacity"), _style_number(selected_node_style, "opacity"))
            self.assertAlmostEqual(_style_number(library_muted_style, "opacity"), _style_number(selected_node_style, "opacity"))
            self.assertAlmostEqual(_style_number(default_muted_style, "opacity"), _style_number(selected_node_style, "opacity"))
            self.assertEqual(selected_node_style["z-index-compare"], "manual")
            self.assertEqual(related_node_style["z-index-compare"], "manual")
            self.assertEqual(source_muted_style["z-index-compare"], "manual")
            self.assertLess(_style_number(muted_edge_style, "z-index"), _style_number(source_muted_style, "z-index"))
            self.assertLess(_style_number(source_muted_style, "z-index"), _style_number(incoming_edge_style, "z-index"))
            self.assertLess(_style_number(source_muted_style, "z-index"), _style_number(related_node_style, "z-index"))
            self.assertLess(_style_number(library_muted_style, "z-index"), _style_number(related_node_style, "z-index"))
            self.assertLess(_style_number(default_muted_style, "z-index"), _style_number(related_node_style, "z-index"))
            self.assertNotEqual(source_muted_style["background-color"], library_muted_style["background-color"])
            self.assertNotEqual(default_muted_style["background-color"], source_muted_style["background-color"])

            selected_edge = style_state["selectedEdge"]
            self.assertIn("dep-selected-edge", selected_edge["classes"])
            self.assertAlmostEqual(_style_number(selected_edge["style"], "opacity"), 1.0)
            self.assertEqual(selected_edge["style"]["line-color"], outgoing_edge_style["line-color"])
            self.assertEqual(selected_edge["style"]["color"], selected_edge["style"]["line-color"])
            self.assertEqual(selected_edge["style"]["target-arrow-color"], selected_edge["style"]["line-color"])

            cycle_function = style_state["cycleFunction"]
            self.assertIn("dep-function-edge", cycle_function["edgeAClasses"])
            self.assertIn("dep-function-edge", cycle_function["edgeBClasses"])
            self.assertEqual(cycle_function["edgeAStyle"]["line-color"], outgoing_edge_style["line-color"])
            self.assertEqual(cycle_function["edgeBStyle"]["line-color"], outgoing_edge_style["line-color"])
            self.assertEqual(cycle_function["edgeAStyle"]["color"], cycle_function["edgeAStyle"]["line-color"])
            self.assertEqual(cycle_function["edgeBStyle"]["color"], cycle_function["edgeBStyle"]["line-color"])
            self.assertLess(_style_number(source_muted_style, "z-index"), _style_number(cycle_function["edgeAStyle"], "z-index"))

            function_relation = style_state["functionRelation"]
            self.assertIn("dep-function-edge", function_relation["selectedEdgeClasses"])
            self.assertNotIn("dep-function-edge", function_relation["relatedEdgeClasses"])
            self.assertEqual(function_relation["selectedEdgeStyle"]["line-color"], outgoing_edge_style["line-color"])
            self.assertEqual(function_relation["selectedEdgeStyle"]["color"], function_relation["selectedEdgeStyle"]["line-color"])
            self.assertEqual(function_relation["relatedEdgeStyle"]["color"], function_relation["relatedEdgeStyle"]["line-color"])
            self.assertNotEqual(function_relation["relatedEdgeStyle"]["line-color"], function_relation["selectedEdgeStyle"]["line-color"])
            self.assertLess(_style_number(function_relation["relatedEdgeStyle"], "z-index"), _style_number(related_node_style, "z-index"))
            self.assertLess(
                _style_color_luminance(function_relation["selectedEdgeStyle"]["line-color"]),
                _style_color_luminance(function_relation["relatedEdgeStyle"]["line-color"]),
            )

            dark_style = style_state["dark"]
            self.assertGreater(
                _style_color_luminance(dark_style["edgeStyles"]["outgoing"]["line-color"]),
                _style_color_luminance(dark_style["edgeStyles"]["muted"]["line-color"]),
            )

            svg_order = light_style["svgOrder"]
            self.assertLess(svg_order.index("src/file_c.c"), svg_order.index("src/file_b.c\nsrc/file_a.c"))
            self.assertLess(svg_order.index("src/file_c.c"), svg_order.index("src/file_a.c\nsrc/file_b.c"))
            self.assertLess(svg_order.index("src/file_d.c\nsrc/file_e.c"), svg_order.index("src/file_b.c\nsrc/file_a.c"))
            self.assertLess(svg_order.index("src/file_d.c\nsrc/file_e.c"), svg_order.index("src/file_a.c\nsrc/file_b.c"))
            self.assertLess(svg_order.index("src/file_b.c\nsrc/file_a.c"), svg_order.index("a_main"))
            self.assertLess(svg_order.index("src/file_a.c\nsrc/file_b.c"), svg_order.index("a_main"))

            # --- Phase A: クリック同期完了直後 ---
            sync = data["sync"]
            # 無選択から選択への境界でも、選択ファイルの active class は Phase A で即時反映する。
            self.assertIn("dep-selected-file", sync["selectedFileClasses"])
            self.assertTrue(sync["classPlan"]["deferStateClassChanges"])
            self.assertGreater(sync["classPlan"]["phaseA"], 0)
            self.assertGreater(sync["classPlan"]["phaseC"], 0)
            # グループ内の関数ノードが同期的に追加されている。
            self.assertEqual(sorted(sync["functionNodes"]), file_a_functions)
            # 興味対象外のミュートはこの時点では未適用 (Phase C へ遅延)。
            self.assertFalse(sync["fileCMuted"])

            # --- Phase B + C 完了後 ---
            final = data["final"]
            self.assertTrue(final["renderedMatchesCurrent"])
            # 無関係な file_c はミュートされる。
            self.assertTrue(final["fileCMuted"])
            # 呼び出し関係のある file_b はミュートされない。
            self.assertFalse(final["fileBMuted"])
            self.assertEqual(sorted(final["functionNodes"]), file_a_functions)

            # --- timing: active は同期、muted は後続フレームで反映 ---
            phase_timing = data["phaseTiming"]
            self.assertIn("dep-selected-file", phase_timing["samples"]["immediate"]["selectedFileClasses"])
            self.assertNotIn("dep-file-node-muted", phase_timing["samples"]["immediate"]["mutedFileClasses"])
            self.assertIn("dep-selected-file", phase_timing["samples"]["afterFrame"]["selectedFileClasses"])
            self.assertTrue(phase_timing["samples"]["afterFrame"]["layoutRunning"])
            self.assertTrue(phase_timing["final"]["renderedMatchesCurrent"])
            self.assertIn("dep-file-node-muted", phase_timing["final"]["mutedFileClasses"])

            # --- 別ファイルへ選択切替: 選択中同士の変更は Phase A で同期反映 ---
            switch_sync = data["switchSync"]
            self.assertIn("dep-selected-file", switch_sync["selectedFileClasses"])
            self.assertFalse(switch_sync["classPlan"]["deferStateClassChanges"])
            self.assertGreater(switch_sync["classPlan"]["phaseA"], 0)
            self.assertEqual(switch_sync["classPlan"]["phaseC"], 0)

            # --- 選択解除: 状態 class 変更は Phase C へ送る ---
            clear_selection = data["clearSelection"]
            self.assertTrue(clear_selection["classPlan"]["deferStateClassChanges"])
            self.assertGreater(clear_selection["classPlan"]["phaseA"], 0)
            self.assertGreater(clear_selection["classPlan"]["phaseC"], 0)
            self.assertNotIn("dep-selected-file", clear_selection["fileCClasses"])
            self.assertNotIn("dep-selected-file", clear_selection["final"]["fileCClasses"])
            self.assertNotIn("dep-file-node-muted", clear_selection["final"]["fileAClasses"])

            # --- 初期化済みマップから別タブで選択変更後に戻る: 最終断面まで非表示で反映 ---
            # 初期化済みの場合は初期化用 immediate を通さないが、一覧表から戻る間は
            # layout-relayouting で隠し、非アニメーションで選択を反映する。
            hidden_tab_selection = data["hiddenTabSelection"]
            self.assertTrue(hidden_tab_selection["hiddenSeen"])
            self.assertFalse(hidden_tab_selection["hiddenDroppedBeforeReady"])
            self.assertFalse(hidden_tab_selection["animationSeen"])
            self.assertFalse(hidden_tab_selection["final"]["hidden"])
            self.assertFalse(hidden_tab_selection["final"]["animationActive"])
            self.assertTrue(hidden_tab_selection["final"]["renderedMatchesCurrent"])
            self.assertIn("dep-selected-file", hidden_tab_selection["final"]["selectedFileClasses"])
            self.assertTrue(hidden_tab_selection["final"]["fileCMuted"])
            # この修正の中核: 復帰前後で非選択ファイル ノードが動かない。
            self.assertEqual(
                hidden_tab_selection["movedCount"], 0, msg=str(hidden_tab_selection["movedTop"])
            )
            self.assertLessEqual(hidden_tab_selection["maxMovedDelta"], 0.5)

            # --- 「レイアウト再実行」実行中の選択変更で状態が固着しない ---
            # ボタン連打: 2 回目は inert ツールバーに吸収され、選択は保持され、relayout は
            # 1 回だけ走り、待機後に操作ロック / inert が解除され、再度 relayout を起動できる。
            relayout_double_click = data["relayoutDoubleClick"]
            self.assertTrue(relayout_double_click["available"])
            self.assertEqual(relayout_double_click["selectionBefore"], '["","src/file_a.c",""]')
            # 連打中も選択は外れない (貫通による背景タップが起きない)。
            self.assertEqual(
                relayout_double_click["afterDblClick"]["current"], '["","src/file_a.c",""]'
            )
            # 固着せず収束する。
            self.assertTrue(relayout_double_click["settled"])
            after_settle = relayout_double_click["afterSettle"]
            self.assertFalse(after_settle["isLayoutRunning"])
            self.assertFalse(after_settle["controlsInert"])
            self.assertTrue(after_settle["panningEnabled"])
            self.assertFalse(after_settle["autoungrabify"])
            self.assertEqual(after_settle["current"], '["","src/file_a.c",""]')
            self.assertTrue(relayout_double_click["relayoutWorksAfter"])

            # ボタン -> 背景: 背景クリックなので選択解除は正しい挙動。固着せず復帰する。
            relayout_then_background = data["relayoutThenBackground"]
            self.assertTrue(relayout_then_background["available"])
            bg_settle = relayout_then_background["afterSettle"]
            self.assertFalse(bg_settle["isLayoutRunning"])
            self.assertFalse(bg_settle["controlsInert"])
            self.assertTrue(bg_settle["panningEnabled"])
            self.assertFalse(bg_settle["autoungrabify"])
            self.assertEqual(bg_settle["current"], '["","",""]')
            self.assertTrue(relayout_then_background["relayoutWorksAfter"])

            # --- Phase B 中の連続選択: 古い Phase C が最新選択へ反映されない ---
            rapid_selection = data["rapidSelection"]
            self.assertIn("dep-selected-file", rapid_selection["immediate"]["selectedFileClasses"])
            self.assertFalse(rapid_selection["immediate"]["fileAMutedImmediate"])
            self.assertFalse(rapid_selection["immediate"]["fileCMutedImmediate"])
            self.assertTrue(rapid_selection["immediate"]["classPlan"]["deferStateClassChanges"])
            self.assertGreater(rapid_selection["immediate"]["classPlan"]["phaseC"], 0)
            self.assertTrue(rapid_selection["final"]["renderedMatchesCurrent"])
            self.assertIn("dep-selected-file", rapid_selection["final"]["selectedFileClasses"])
            self.assertTrue(rapid_selection["final"]["fileAMuted"])
            self.assertFalse(rapid_selection["final"]["fileCMuted"])

            # --- seed 窓内で関数選択へ割り込み: 進行中レイアウトを破棄し関数選択へ整定 ---
            # selectFile 直後 (Phase B 進行中) に selectFunction で割り込む。修正前は停止されない
            # 旧 cola が走り続け全体が暴れたが、修正後は新しい選択へ clean に整定する。
            seed_fn = data["seedInterruptFunction"]
            self.assertTrue(
                seed_fn["interrupt"]["mid"]["layoutRunning"],
                msg="selectFile 直後にレイアウトが進行中でない (seed 窓を再現できていない)",
            )
            fn_id = seed_fn["interrupt"]["fnId"]
            self.assertTrue(fn_id, msg="file_a の関数ノードが取得できていない")
            self.assertTrue(seed_fn["final"]["renderedMatchesCurrent"])
            expected_fn_sig = json.dumps([fn_id, "src/file_a.c", ""], separators=(",", ":"))
            self.assertEqual(seed_fn["final"]["currentSignature"], expected_fn_sig)
            # 選択した関数が中心ノードとして強調され、ファイル選択強調は外れている。
            # 関数選択ビューは選択関数とその呼び出し関係に絞り込まれるため、ファイル全関数では
            # なく関係する関数のみを対象にレイアウトされる (進行中の旧レイアウトは破棄済み)。
            self.assertTrue(seed_fn["final"]["fnIsCenter"])
            self.assertFalse(seed_fn["final"]["fileSelectedFile"])
            self.assertGreaterEqual(seed_fn["final"]["functionNodeCount"], 1)

            # --- 実マウス seed 窓内関数クリック: 非選択ファイルは動かさない ---
            real_seed_fn = data["realSeedInterruptFunctionStability"]
            self.assertTrue(
                real_seed_fn["seed"]["layoutRunning"],
                msg="実マウス seed 窓を再現できていない",
            )
            self.assertTrue(real_seed_fn["seed"]["fnId"], msg="クリック対象の関数ノードが取得できていない")
            self.assertTrue(real_seed_fn["final"]["renderedMatchesCurrent"])
            self.assertEqual(real_seed_fn["movedCount"], 0, msg=str(real_seed_fn["movedTop"]))
            self.assertLessEqual(real_seed_fn["maxMovedDelta"], 0.5)

            # --- seed 窓内でファイルをドラッグ: アニメーション直前の中心位置を使う ---
            seed_drag = data["seedDragFile"]
            self.assertTrue(seed_drag["seed"]["layoutRunning"], msg="ファイル ドラッグの seed 窓を再現できていない")
            self.assertTrue(seed_drag["animationSeenAfterDrag"])
            self.assertTrue(seed_drag["final"]["renderedMatchesCurrent"])
            self.assertLessEqual(seed_drag["fileDriftFromDragged"], 8.0)
            self.assertLessEqual(seed_drag["childCenterDriftFromFile"], 90.0)
            self.assertAlmostEqual(seed_drag["seed"]["viewport"]["zoom"], seed_drag["final"]["viewport"]["zoom"], delta=0.001)
            self.assertAlmostEqual(seed_drag["seed"]["viewport"]["pan"]["x"], seed_drag["final"]["viewport"]["pan"]["x"], delta=0.5)
            self.assertAlmostEqual(seed_drag["seed"]["viewport"]["pan"]["y"], seed_drag["final"]["viewport"]["pan"]["y"], delta=0.5)

            # --- seed 窓内で関数をドラッグ: 親ファイル中心の変化を開始座標へ反映する ---
            seed_drag_fn = data["seedDragFunction"]
            self.assertTrue(seed_drag_fn["seed"]["layoutRunning"], msg="関数ドラッグの seed 窓を再現できていない")
            self.assertTrue(seed_drag_fn["seed"]["fnId"], msg="ドラッグ対象の関数ノードが取得できていない")
            self.assertEqual(len(seed_drag_fn["dragSamples"]), 5)
            self.assertFalse(any(sample["animationActive"] for sample in seed_drag_fn["dragSamples"]))
            self.assertLessEqual(
                max(sample["renderedDelta"] for sample in seed_drag_fn["dragSamples"]),
                2.0,
                msg=str(seed_drag_fn["dragSamples"]),
            )
            self.assertGreater(seed_drag_fn["fnMovedFromSeed"], 8.0)
            self.assertFalse(seed_drag_fn["afterDrag"]["animationActive"])
            self.assertTrue(seed_drag_fn["animationSeenAfterDrag"])
            self.assertTrue(seed_drag_fn["final"]["renderedMatchesCurrent"])
            self.assertLessEqual(seed_drag_fn["childCenterDriftFromFile"], 90.0)
            self.assertAlmostEqual(seed_drag_fn["seed"]["viewport"]["zoom"], seed_drag_fn["final"]["viewport"]["zoom"], delta=0.001)
            self.assertAlmostEqual(seed_drag_fn["seed"]["viewport"]["pan"]["x"], seed_drag_fn["final"]["viewport"]["pan"]["x"], delta=0.5)
            self.assertAlmostEqual(seed_drag_fn["seed"]["viewport"]["pan"]["y"], seed_drag_fn["final"]["viewport"]["pan"]["y"], delta=0.5)

            # --- drag 後に無選択化して同じファイルを再選択: 削除済み関数の旧 drag 座標を seed に使わない ---
            dragged_seed_reset = data["draggedFunctionSeedReset"]
            self.assertTrue(dragged_seed_reset["available"])
            self.assertTrue(dragged_seed_reset["reselectedSeed"]["layoutRunning"])
            self.assertGreater(dragged_seed_reset["minDraggedDistance"], 20.0, msg=str(dragged_seed_reset))
            self.assertTrue(dragged_seed_reset["final"]["renderedMatchesCurrent"])

            # --- seed 窓内で無選択化へ割り込み (Problem 2): マップも完全に無選択へ整定 ---
            # 修正前は詳細ペインだけ無選択になりマップはファイル選択のまま残った。
            seed_clear = data["seedInterruptClear"]
            self.assertTrue(
                seed_clear["interrupt"]["mid"]["layoutRunning"],
                msg="selectFile 直後にレイアウトが進行中でない (seed 窓を再現できていない)",
            )
            self.assertTrue(seed_clear["final"]["renderedMatchesCurrent"])
            self.assertEqual(
                seed_clear["final"]["currentSignature"],
                json.dumps(["", "", ""], separators=(",", ":")),
            )
            # マップ側も無選択へ整定: ファイル選択強調が外れ、関数ノードも消えていること。
            self.assertFalse(seed_clear["final"]["fileSelectedFile"])
            self.assertEqual(seed_clear["final"]["functionNodeCount"], 0)

            # --- ファイル選択 -> 選択解除の往復で、ファイル グループ中心を維持する ---
            center_stability = data["centerStability"]
            self.assertIsNotNone(center_stability["before"])
            self.assertIsNotNone(center_stability["selected"])
            self.assertIsNotNone(center_stability["cleared"])
            self.assertLess(center_stability["selectedDrift"], 2.0)
            self.assertLess(center_stability["clearedDrift"], 2.0)

            # --- 実マウス クリックで関数の位置補正 (Phase B) が効くこと ---
            # ノードの実タップは grab/free を発火する。これがドラッグ扱いされると
            # Phase B がスキップされ関数が seed のまま残る (修正前の不具合)。
            real_click = data["realClick"]
            self.assertTrue(real_click["available"])
            self.assertEqual(real_click["total"], len(file_a_functions))
            # 過半数の関数が初期配置 (seed) から移動していること。
            self.assertGreater(real_click["moved"], len(file_a_functions) // 2)

            # --- 右クリック非表示: 一般的な選択変更・背景クリックでは復活せず初期化で全復活 ---
            hide_persist = data["hidePersist"]
            # 非表示直後: ノードが消え、非表示集合とラベルに反映される。
            self.assertFalse(hide_persist["afterHide"]["fileCExists"])
            self.assertEqual(hide_persist["afterHide"]["hiddenFiles"], ["src/file_c.c"])
            self.assertTrue(hide_persist["afterHide"]["noticeVisible"])
            # 背景クリック相当の無選択化では復活しない (要件どおり維持)。
            self.assertFalse(hide_persist["afterBgClear"]["fileCExists"])
            self.assertEqual(hide_persist["afterBgClear"]["hiddenFiles"], ["src/file_c.c"])
            # 別ファイル選択でも復活しない (関連扱いに留まる)。
            self.assertFalse(hide_persist["afterOtherSelect"]["fileCExists"])
            self.assertEqual(hide_persist["afterOtherSelect"]["hiddenFiles"], ["src/file_c.c"])
            # 初期化で全復活し、ラベルも消える。
            self.assertTrue(hide_persist["afterReset"]["fileCExists"])
            self.assertEqual(hide_persist["afterReset"]["hiddenFiles"], [])
            self.assertFalse(hide_persist["afterReset"]["noticeVisible"])

            # --- 非表示ファイル自身の選択で復活し、元の位置近傍へ再表示 ---
            restore_select = data["hideRestoreBySelect"]
            self.assertTrue(restore_select["restored"]["fileCExists"])
            self.assertEqual(restore_select["restored"]["hiddenFiles"], [])
            self.assertFalse(restore_select["restored"]["noticeVisible"])
            self.assertIsNotNone(restore_select["beforeHide"])
            self.assertIsNotNone(restore_select["restoreDrift"])
            # 元の位置近傍 (アンカー復元) へ戻ること。
            self.assertLess(restore_select["restoreDrift"], 2.0)

            # --- 非表示ファイルの関数選択で復活、ただし非循環の関連先では復活しない ---
            restore_fn = data["hideRestoreByFunction"]
            # a_main は b_entry を呼ぶが、関連先になっただけでは file_b は復活しない。
            self.assertFalse(restore_fn["afterRelated"]["fileBExists"])
            self.assertFalse(restore_fn["afterRelated"]["bEntryExists"])
            self.assertEqual(restore_fn["afterRelated"]["hiddenFiles"], ["src/file_b.c"])
            # file_b 自身の関数 (b_entry) を選択すると復活する。
            self.assertTrue(restore_fn["afterOwn"]["fileBExists"])
            self.assertEqual(restore_fn["afterOwn"]["hiddenFiles"], [])

            # --- 循環参照の例外: 循環関数選択で循環相手の所属ファイルを復活 ---
            restore_cycle = data["hideRestoreByCycle"]
            self.assertFalse(restore_cycle["afterHide"]["fileEExists"])
            self.assertEqual(restore_cycle["afterHide"]["hiddenFiles"], ["src/file_e.c"])
            self.assertTrue(restore_cycle["afterCycleSelect"]["fileEExists"])
            self.assertTrue(restore_cycle["afterCycleSelect"]["eCycExists"])
            self.assertEqual(restore_cycle["afterCycleSelect"]["hiddenFiles"], [])

            # --- 「非表示ファイルの再表示」ボタン: 選択を変えず全件復活 ---
            reveal_all = data["revealAll"]
            # ボタンとして押せる状態 (透過・hit test 無効ではない)。
            self.assertTrue(reveal_all["afterHide"]["noticeIsButton"])
            self.assertTrue(reveal_all["afterHide"]["noticeClickable"])
            self.assertTrue(reveal_all["afterHide"]["noticeVisible"])
            self.assertEqual(
                sorted(reveal_all["afterHide"]["hiddenFiles"]),
                ["src/file_b.c", "src/file_c.c"],
            )
            self.assertFalse(reveal_all["afterHide"]["fileBExists"])
            self.assertFalse(reveal_all["afterHide"]["fileCExists"])
            # クリックで全件復活し、ラベルも消える。
            self.assertEqual(reveal_all["afterReveal"]["hiddenFiles"], [])
            self.assertFalse(reveal_all["afterReveal"]["noticeVisible"])
            self.assertTrue(reveal_all["afterReveal"]["fileBExists"])
            self.assertTrue(reveal_all["afterReveal"]["fileCExists"])
            # 現在の選択状況に応じ、関連ファイルは通常表示、無関係ファイルは控えめ表示。
            self.assertFalse(reveal_all["afterReveal"]["fileBMuted"])
            self.assertTrue(reveal_all["afterReveal"]["fileCMuted"])
            # 選択状態 (file_a) は変わらない。
            self.assertTrue(reveal_all["afterReveal"]["selectedFileStillA"])
            self.assertEqual(
                reveal_all["afterReveal"]["currentSignature"],
                json.dumps(["", "src/file_a.c", ""], separators=(",", ":")),
            )

            # --- 再表示時ちらつき防止: ミュート対象は生成直後 (Phase A 断面) から既にミュート ---
            # 修正前は新規追加ノードが構造クラスのみ (通常表示) で生成され、ミュートが Phase C へ
            # 遅延していたため、再表示直後の 1 フレーム素の見た目が露出した。
            reveal_no_flash = data["revealMutedNoFlash"]
            self.assertEqual(reveal_no_flash["sample"]["hiddenBefore"], ["src/file_c.c"])
            self.assertTrue(reveal_no_flash["sample"]["fileCExists"])
            # 再表示同期 (Phase A) 完了直後のフレーム待機前断面で、既にミュート済みであること。
            self.assertTrue(reveal_no_flash["sample"]["immediateMuted"])
            # 選択状態 (file_a) は変わらない。
            self.assertTrue(reveal_no_flash["sample"]["selectedStillA"])
            # 整定後もミュートのまま。
            self.assertTrue(reveal_no_flash["final"]["finalMuted"])
            self.assertEqual(reveal_no_flash["final"]["hiddenFiles"], [])

            # --- seed 窓内で再表示に割り込み: 中止された関数レイアウトをやり直す ---
            # 非表示ファイルがある状態で表示中ファイルを選択し、seed の cola 計算中に再表示すると、
            # 進行中レイアウトは中止される。修正前は選択ファイルの関数が再レイアウトされず seed
            # 円形配置のまま残った。修正後は未整定の関数を再投入し Phase B をやり直す。
            seed_reveal = data["seedInterruptReveal"]
            self.assertTrue(seed_reveal["available"])
            self.assertTrue(
                seed_reveal["revealLayoutRunningBefore"],
                msg="再表示の時点でレイアウトが進行中でない (seed 窓を再現できていない)",
            )
            self.assertEqual(seed_reveal["total"], len(file_a_functions))
            self.assertEqual(seed_reveal["hiddenCount"], 0)
            self.assertTrue(seed_reveal["fileCRevealed"])
            self.assertTrue(seed_reveal["renderedMatchesCurrent"])
            self.assertTrue(seed_reveal["isReady"])
            # 過半数の関数が seed から移動している (レイアウトがやり直された)。
            self.assertGreater(seed_reveal["moved"], len(file_a_functions) // 2)

            # --- seed 窓内で別ファイルの非表示に割り込み: 同様に関数レイアウトをやり直す ---
            seed_hide = data["seedInterruptHide"]
            self.assertTrue(seed_hide["available"])
            self.assertTrue(
                seed_hide["hideLayoutRunningBefore"],
                msg="非表示の時点でレイアウトが進行中でない (seed 窓を再現できていない)",
            )
            self.assertEqual(seed_hide["total"], len(file_a_functions))
            self.assertTrue(seed_hide["fileBHidden"])
            self.assertTrue(seed_hide["renderedMatchesCurrent"])
            self.assertTrue(seed_hide["isReady"])
            self.assertGreater(seed_hide["moved"], len(file_a_functions) // 2)


if __name__ == "__main__":
    unittest.main()
