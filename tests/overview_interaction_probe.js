'use strict';

// 依存関係レポートの全体マップ (Cytoscape) のインタラクションを Puppeteer で検証するプローブ。
// 生成済み index.html のパスを argv[2] に受け取り、結果を 1 行の JSON ("RESULT " 接頭辞付き) で
// 標準出力へ書き出す。アサーションは呼び出し側 (test_generate_dependency_report.py) が行う。
//
// 検証観点 (3 フェーズ モデル):
//   Phase A: ファイル ノードのクリックで、グループ化・関数ノードの追加・興味対象の強調
//            (dep-selected-file) が同期的に即反映される。興味対象外のミュートは未適用。
//   Phase C: 興味対象外の非強調 (dep-file-node-muted) はレイアウト後に最後に適用される。
//   実クリック: ファイル ノードを実マウスでクリック (grab/free を誘発) したとき、グループ内
//               関数の位置補正 (Phase B) が効き、関数が初期配置 (seed) から移動すること。
//
// Puppeteer は docsfw 配下にバンドルされたものを利用する (DOXYFW_TEST_PUPPETEER で上書き可)。

const path = require('path');

function resolvePuppeteer() {
  const candidates = [];
  if (process.env.DOXYFW_TEST_PUPPETEER) candidates.push(process.env.DOXYFW_TEST_PUPPETEER);
  candidates.push(path.resolve(__dirname, '../../docsfw/bin/node_modules/puppeteer'));
  candidates.push('puppeteer');
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch (err) {
      // 次の候補へ
    }
  }
  throw new Error('puppeteer not found (set DOXYFW_TEST_PUPPETEER)');
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function countMoved(seed, settled) {
  if (!seed || !settled) return -1;
  const seedById = new Map(seed.map((c) => [c.id, c]));
  let moved = 0;
  for (const c of settled) {
    const s = seedById.get(c.id);
    if (s && (Math.abs(s.x - c.x) > 2 || Math.abs(s.y - c.y) > 2)) moved += 1;
  }
  return moved;
}

function distance(a, b) {
  if (!a || !b) return null;
  return Math.hypot(a.x - b.x, a.y - b.y);
}

async function waitOverviewReady(page) {
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 20000 }
  );
  await sleep(50);
}

async function newOverviewProbePage(browser, reportPath, errors) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000 });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console:' + m.text()); });
  await page.evaluateOnNewDocument(() => { window.__DEP_REPORT_TEST__ = true; });
  await page.goto('file://' + reportPath, { waitUntil: 'load' });
  await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
  return page;
}

async function captureOverviewPositions(page) {
  return page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const nodeIds = api.nodeIds().sort();
    return {
      nodeIds,
      currentSignature: api.currentSignature(),
      renderedSignature: api.renderedSignature(),
      selectedFileClasses: api.classesOf('src/file_a.c') || [],
      fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1,
      functionNodes: nodeIds.filter((id) => id.indexOf('/') === -1),
      positions: Object.fromEntries(nodeIds.map((id) => [id, api.positionOf(id)]))
    };
  });
}

async function runInitialHiddenSelectionScenario(browser, reportPath, errors, filePath) {
  const baselinePage = await newOverviewProbePage(browser, reportPath, errors);
  let baseline = null;
  try {
    await baselinePage.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await waitOverviewReady(baselinePage);
    await baselinePage.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
    await waitOverviewReady(baselinePage);
    baseline = await captureOverviewPositions(baselinePage);
  } finally {
    await baselinePage.close();
  }

  const hiddenPage = await newOverviewProbePage(browser, reportPath, errors);
  let beforeActivate = null;
  let afterActivate = null;
  let hiddenDroppedBeforeReady = false;
  let hiddenFirst = null;
  try {
    await hiddenPage.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
    beforeActivate = await hiddenPage.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        currentSignature: api.currentSignature(),
        renderedSignature: api.renderedSignature(),
        elementCount: api.elementCount(),
        initializing: api.isInitializing(),
        relayoutHidden: api.isRelayoutHidden()
      };
    });
    await hiddenPage.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    afterActivate = await hiddenPage.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        initializing: api.isInitializing(),
        relayoutHidden: api.isRelayoutHidden(),
        layoutRunning: api.isLayoutRunning(),
        elementCount: api.elementCount(),
        renderedSignature: api.renderedSignature()
      };
    });

    const deadline = Date.now() + 25000;
    while (Date.now() < deadline) {
      const state = await hiddenPage.evaluate(() => {
        const api = window.depReportOverviewTestApi;
        return {
          hidden: api.isInitializing() || api.isRelayoutHidden(),
          layoutRunning: api.isLayoutRunning(),
          renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
        };
      });
      if (!state.hidden && (state.layoutRunning || !state.renderedMatchesCurrent)) {
        hiddenDroppedBeforeReady = true;
      }
      if (!state.layoutRunning && state.renderedMatchesCurrent) break;
      await sleep(50);
    }
    await waitOverviewReady(hiddenPage);
    hiddenFirst = await captureOverviewPositions(hiddenPage);
  } finally {
    await hiddenPage.close();
  }

  const commonNodeIds = baseline.nodeIds.filter((id) => hiddenFirst.positions[id]);
  const deltas = commonNodeIds
    .map((id) => ({ id, delta: distance(baseline.positions[id], hiddenFirst.positions[id]) }))
    .filter((entry) => entry.delta !== null)
    .sort((a, b) => b.delta - a.delta);
  const fileDeltas = deltas.filter((entry) => entry.id.indexOf('/') !== -1);
  const selectedFunctionDeltas = deltas.filter((entry) => entry.id.indexOf('/') === -1);
  return {
    beforeActivate,
    afterActivate,
    hiddenDroppedBeforeReady,
    baseline,
    hiddenFirst,
    maxDelta: deltas.length > 0 ? deltas[0].delta : 0,
    maxFileDelta: fileDeltas.length > 0 ? fileDeltas[0].delta : 0,
    maxFunctionDelta: selectedFunctionDeltas.length > 0 ? selectedFunctionDeltas[0].delta : 0,
    movedTop: deltas.slice(0, 8)
  };
}

async function runStyleScenario(page) {
  const edgeStyleNames = ['line-color', 'target-arrow-color', 'color', 'opacity', 'z-index', 'z-index-compare', 'z-compound-depth'];
  const nodeStyleNames = ['background-color', 'border-color', 'color', 'opacity', 'z-index', 'z-index-compare', 'z-compound-depth'];
  const outgoingEdge = 'src/file_a.c\nsrc/file_b.c';
  const incomingEdge = 'src/file_b.c\nsrc/file_a.c';
  const mutedEdge = 'src/file_d.c\nsrc/file_e.c';
  const cycleEdgeA = 'd_cyc->e_cyc';
  const cycleEdgeB = 'e_cyc->d_cyc';
  const selectedFunctionEdge = 'a_main->b_entry';
  const relatedFunctionEdge = 'b_entry->a_helper';

  async function fileSelectionSnapshot(theme) {
    await page.evaluate((t) => {
      const api = window.depReportOverviewTestApi;
      api.applyThemeForTest(t);
      api.resetGraph();
    }, theme);
    await waitOverviewReady(page);
    await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_a.c'));
    await waitOverviewReady(page);
    return page.evaluate((args) => {
      const api = window.depReportOverviewTestApi;
      return {
        outgoingClasses: api.classesOf(args.outgoingEdge) || [],
        incomingClasses: api.classesOf(args.incomingEdge) || [],
        mutedEdgeClasses: api.classesOf(args.mutedEdge) || [],
        sourceMutedClasses: api.classesOf('src/file_c.c') || [],
        libraryMutedClasses: api.classesOf('libsrc/file_g.c') || [],
        defaultMutedClasses: api.classesOf('generated/file_f.c') || [],
        edgeStyles: {
          outgoing: api.styleOf(args.outgoingEdge, args.edgeStyleNames),
          incoming: api.styleOf(args.incomingEdge, args.edgeStyleNames),
          muted: api.styleOf(args.mutedEdge, args.edgeStyleNames)
        },
        nodeStyles: {
          selected: api.styleOf('src/file_a.c', args.nodeStyleNames),
          sourceMuted: api.styleOf('src/file_c.c', args.nodeStyleNames),
          libraryMuted: api.styleOf('libsrc/file_g.c', args.nodeStyleNames),
          defaultMuted: api.styleOf('generated/file_f.c', args.nodeStyleNames),
          normalRelated: api.styleOf('src/file_b.c', args.nodeStyleNames)
        },
        svgOrder: api.svgDrawOrder()
      };
    }, { outgoingEdge, incomingEdge, mutedEdge, edgeStyleNames, nodeStyleNames });
  }

  const light = await fileSelectionSnapshot('light');

  await page.evaluate((edgeId) => window.depReportOverviewTestApi.selectEdge(edgeId), outgoingEdge);
  await waitOverviewReady(page);
  const selectedEdge = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    return {
      classes: api.classesOf(args.outgoingEdge) || [],
      style: api.styleOf(args.outgoingEdge, args.edgeStyleNames)
    };
  }, { outgoingEdge, edgeStyleNames });

  await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('d_cyc'));
  await waitOverviewReady(page);
  const cycleFunction = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    return {
      edgeAClasses: api.classesOf(args.cycleEdgeA) || [],
      edgeBClasses: api.classesOf(args.cycleEdgeB) || [],
      edgeAStyle: api.styleOf(args.cycleEdgeA, args.edgeStyleNames),
      edgeBStyle: api.styleOf(args.cycleEdgeB, args.edgeStyleNames)
    };
  }, { cycleEdgeA, cycleEdgeB, edgeStyleNames });

  await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('a_main'));
  await waitOverviewReady(page);
  const functionRelation = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    return {
      selectedEdgeClasses: api.classesOf(args.selectedFunctionEdge) || [],
      relatedEdgeClasses: api.classesOf(args.relatedFunctionEdge) || [],
      selectedEdgeStyle: api.styleOf(args.selectedFunctionEdge, args.edgeStyleNames),
      relatedEdgeStyle: api.styleOf(args.relatedFunctionEdge, args.edgeStyleNames)
    };
  }, { selectedFunctionEdge, relatedFunctionEdge, edgeStyleNames });

  const dark = await fileSelectionSnapshot('dark');
  await page.evaluate(() => window.depReportOverviewTestApi.applyThemeForTest('light'));
  return { light, selectedEdge, cycleFunction, functionRelation, dark };
}

async function runPhaseTimingScenario(page, filePath, mutedFilePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);

  const samples = await page.evaluate(async (args) => {
    const api = window.depReportOverviewTestApi;
    const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve()));
    api.selectFile(args.filePath);
    const immediate = {
      selectedFileClasses: api.classesOf(args.filePath) || [],
      mutedFileClasses: api.classesOf(args.mutedFilePath) || [],
      classPlan: api.lastClassUpdatePlan()
    };
    await nextFrame();
    const afterFrame = {
      selectedFileClasses: api.classesOf(args.filePath) || [],
      mutedFileClasses: api.classesOf(args.mutedFilePath) || [],
      layoutRunning: api.isLayoutRunning()
    };
    return { immediate, afterFrame };
  }, { filePath, mutedFilePath });

  await waitOverviewReady(page);
  const final = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    return {
      selectedFileClasses: api.classesOf(args.filePath) || [],
      mutedFileClasses: api.classesOf(args.mutedFilePath) || [],
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
    };
  }, { filePath, mutedFilePath });

  return { samples, final };
}

async function runCenterStabilityScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);
  const before = await page.evaluate((p) => window.depReportOverviewTestApi.positionOf(p), filePath);

  await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
  await waitOverviewReady(page);
  const selected = await page.evaluate((p) => window.depReportOverviewTestApi.positionOf(p), filePath);

  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);
  const cleared = await page.evaluate((p) => window.depReportOverviewTestApi.positionOf(p), filePath);

  return {
    before,
    selected,
    cleared,
    selectedDrift: distance(before, selected),
    clearedDrift: distance(before, cleared)
  };
}

// ファイル ノードを実マウスでクリックし、グループ内関数が seed から移動するか測る。
async function runRealClickScenario(page, filePath) {
  const pos = await page.evaluate((p) => window.depReportOverviewTestApi.renderedPositionOf(p), filePath);
  if (!pos) return { available: false };
  await page.mouse.click(pos.x, pos.y);
  // クリック直後 (Phase A 完了直後) の seed 配置。
  await sleep(60);
  const seed = await page.evaluate((p) => window.depReportOverviewTestApi.childPositions(p), filePath);
  // 非同期 cola (約 900ms) + アニメーション (430ms) を確実に超える固定長待機。
  await sleep(3500);
  const settled = await page.evaluate((p) => window.depReportOverviewTestApi.childPositions(p), filePath);
  return {
    available: true,
    total: settled ? settled.length : 0,
    moved: countMoved(seed, settled)
  };
}

// 全体マップの操作ロック / inert / 実行フラグの断面を読む。
function readOverviewRuntimeState(page) {
  return page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const cy = document.getElementById('overviewGraph')._cyreg.cy;
    const shell = document.querySelector('.dep-graph-shell');
    return {
      isLayoutRunning: api.isLayoutRunning(),
      controlsInert: shell ? shell.classList.contains('controls-inert') : null,
      panningEnabled: cy.panningEnabled(),
      autoungrabify: cy.autoungrabify(),
      current: api.currentSignature(),
      rendered: api.renderedSignature()
    };
  });
}

async function waitOverviewSettledOrStuck(page) {
  // 修正前は relayout 実行中の選択変更で固着し isLayoutRunning が戻らない。固着を検出するため
  // 例外を握り潰して settled フラグで返す (watchdog 8s を超える余裕を持たせる)。
  try {
    await page.waitForFunction(
      () => !window.depReportOverviewTestApi.isLayoutRunning(),
      { timeout: 12000 }
    );
    await sleep(200);
    return true;
  } catch (err) {
    return false;
  }
}

// relayout が再び起動できるか (固着していないか) を確認する。ボタンを 1 回クリックし、
// 実行状態に入るかどうかを返す。
async function probeRelayoutWorksAfter(page, button) {
  await page.mouse.click(button.x, button.y);
  await sleep(250);
  const running = await page.evaluate(() => window.depReportOverviewTestApi.isLayoutRunning());
  return running;
}

function overviewRelayoutButtonCenter(page) {
  return page.evaluate(() => {
    const r = document.getElementById('overviewRelayout').getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
}

// ファイル選択中に「レイアウト再実行」ボタンを実マウスで素早く 2 回クリックする。修正前は
// 2 回目が inert ツールバーを貫通して背景タップ (選択解除) を発火し、relayout の実行状態が
// 孤児化して固着した。修正後は選択が保持され、relayout は 1 回だけ走り、待機後に復帰する。
async function runRelayoutDoubleClickScenario(page, filePath) {
  await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
  await waitOverviewReady(page);
  const button = await overviewRelayoutButtonCenter(page);
  const selectionBefore = await page.evaluate(() => window.depReportOverviewTestApi.currentSignature());
  await page.mouse.click(button.x, button.y);
  await sleep(120);
  await page.mouse.click(button.x, button.y);
  await sleep(400);
  const afterDblClick = await readOverviewRuntimeState(page);
  const settled = await waitOverviewSettledOrStuck(page);
  const afterSettle = await readOverviewRuntimeState(page);
  const relayoutWorksAfter = await probeRelayoutWorksAfter(page, button);
  return { available: true, selectionBefore, afterDblClick, settled, afterSettle, relayoutWorksAfter };
}

// ファイル選択中に relayout ボタンを 1 回クリックし、アニメーション開始前にノードを避けた背景を
// 実マウスでクリックする。背景クリックなので選択解除は正しい挙動だが、修正前は relayout の
// 実行状態が孤児化して固着した。修正後は固着せず復帰する。
async function runRelayoutThenBackgroundScenario(page, filePath) {
  await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
  await waitOverviewReady(page);
  const points = await page.evaluate(() => {
    const cy = document.getElementById('overviewGraph')._cyreg.cy;
    const rect = document.getElementById('overviewGraph').getBoundingClientRect();
    const btn = document.getElementById('overviewRelayout').getBoundingClientRect();
    const occupied = cy.nodes().map((n) => n.renderedBoundingBox());
    function free(rx, ry) {
      return !occupied.some((b) => rx >= b.x1 - 8 && rx <= b.x2 + 8 && ry >= b.y1 - 8 && ry <= b.y2 + 8);
    }
    let bg = null;
    for (let gy = rect.height - 20; gy > 40 && !bg; gy -= 20) {
      for (let gx = 20; gx < rect.width - 20; gx += 20) {
        const cx = rect.left + gx;
        const cyv = rect.top + gy;
        if (cx >= btn.left - 40 && cx <= btn.right + 220 && cyv >= btn.top - 10 && cyv <= btn.bottom + 10) continue;
        if (free(gx, gy)) { bg = { x: cx, y: cyv }; break; }
      }
    }
    return { button: { x: btn.left + btn.width / 2, y: btn.top + btn.height / 2 }, bg };
  });
  if (!points.bg) return { available: false };
  await page.mouse.click(points.button.x, points.button.y);
  await sleep(60);
  await page.mouse.click(points.bg.x, points.bg.y);
  await sleep(400);
  const afterBackground = await readOverviewRuntimeState(page);
  const settled = await waitOverviewSettledOrStuck(page);
  const afterSettle = await readOverviewRuntimeState(page);
  const relayoutWorksAfter = await probeRelayoutWorksAfter(page, points.button);
  return { available: true, afterBackground, settled, afterSettle, relayoutWorksAfter };
}

async function runHiddenTabSelectionScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 20000 }
  );

  // 復帰前の (初期化済み・無選択) ファイル ノード位置を採取する。復帰後に非選択ファイルが
  // 動かないことを検証するための基準。
  const beforeReturn = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const fileIds = api.nodeIds().filter((id) => id.indexOf('/') !== -1);
    return { fileIds, filePositions: Object.fromEntries(fileIds.map((id) => [id, api.positionOf(id)])) };
  });

  await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    api.activateFileList();
    api.selectFile(p);
    api.activateOverview();
  }, filePath);

  const immediate = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      hidden: api.isRelayoutHidden(),
      animationActive: api.isPositionAnimationActive(),
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
    };
  });

  let animationSeen = immediate.animationActive;
  let hiddenSeen = immediate.hidden;
  let hiddenDroppedBeforeReady = false;
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        hidden: api.isRelayoutHidden(),
        layoutRunning: api.isLayoutRunning(),
        animationActive: api.isPositionAnimationActive(),
        renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
      };
    });
    if (state.hidden) hiddenSeen = true;
    if (state.animationActive) animationSeen = true;
    if (!state.hidden && (state.layoutRunning || !state.renderedMatchesCurrent)) {
      hiddenDroppedBeforeReady = true;
    }
    if (!state.layoutRunning && state.renderedMatchesCurrent) {
      break;
    }
    await sleep(50);
  }

  while (Date.now() < deadline) {
    const hidden = await page.evaluate(() => window.depReportOverviewTestApi.isRelayoutHidden());
    if (!hidden) break;
    await sleep(20);
  }

  const final = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    return {
      hidden: api.isRelayoutHidden(),
      animationActive: api.isPositionAnimationActive(),
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      selectedFileClasses: api.classesOf(args.filePath) || [],
      fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1,
      filePositions: Object.fromEntries(args.fileIds.map((id) => [id, api.positionOf(id)]))
    };
  }, { filePath, fileIds: beforeReturn.fileIds });

  // 非選択ファイル ノードが復帰前後で動かないこと (全体マップ内選択と同じ挙動)。
  const moved = beforeReturn.fileIds
    .filter((id) => id !== filePath)
    .map((id) => ({ id, delta: distance(beforeReturn.filePositions[id], final.filePositions[id]) }))
    .filter((entry) => entry.delta !== null && entry.delta > 0.5)
    .sort((a, b) => b.delta - a.delta);

  return {
    immediate,
    hiddenSeen,
    animationSeen,
    hiddenDroppedBeforeReady,
    final,
    movedCount: moved.length,
    maxMovedDelta: moved.length > 0 ? moved[0].delta : 0,
    movedTop: moved.slice(0, 5)
  };
}

// Phase B の seed 配置直後 (cola 計算中・layoutstop 前) に選択を別の対象へ変えたとき、
// 進行中レイアウトが破棄され、新しい選択に対応した状態へ整定することを検証する。
// selectFile 直後に同一 JS ターンで割り込むことで、cola の layoutstop (非同期) より前に
// 確実に割り込み、グラフ規模に依らず seed 窓内の競合を再現する。
async function runSeedInterruptFunctionScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);

  const interrupt = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    api.selectFile(p);
    // seed 窓内 (Phase B 進行中) であることの確認材料。
    const mid = {
      layoutRunning: api.isLayoutRunning(),
      pending: api.pendingSignature(),
      rendered: api.renderedSignature()
    };
    const fnIds = api.nodeIds().filter((id) => id.indexOf('/') === -1);
    const fnId = fnIds.length > 0 ? fnIds[0] : '';
    if (fnId) api.selectFunction(fnId);
    return {
      fnId,
      mid,
      afterPending: api.pendingSignature()
    };
  }, filePath);

  await waitOverviewReady(page);
  const final = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    return {
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      currentSignature: api.currentSignature(),
      fnIsCenter: (api.classesOf(args.fnId) || []).indexOf('dep-center-node') !== -1,
      fileSelectedFile: (api.classesOf(args.filePath) || []).indexOf('dep-selected-file') !== -1,
      functionNodeCount: api.nodeIds().filter((id) => id.indexOf('/') === -1).length
    };
  }, { fnId: interrupt.fnId, filePath });

  return { interrupt, final };
}

// ファイル選択で関数が seed 表示された直後に実マウスで関数をクリックしても、
// 選択ファイル以外のファイル ノードがローカル関数レイアウトに巻き込まれないことを検証する。
async function runRealSeedInterruptFunctionStabilityScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);

  const seed = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    const fileIds = api.nodeIds().filter((id) => id.indexOf('/') !== -1);
    const positions = (ids) => Object.fromEntries(ids.map((id) => [id, api.positionOf(id)]));
    api.selectFile(p);
    const functionIds = api.nodeIds().filter((id) => id.indexOf('/') === -1 && id.indexOf('pull-') !== 0);
    const fnId = functionIds.length > 0 ? functionIds[0] : '';
    return {
      fileIds,
      filePositionsAfterSelect: positions(fileIds),
      fnId,
      fnRenderedPosition: fnId ? api.renderedPositionOf(fnId) : null,
      layoutRunning: api.isLayoutRunning()
    };
  }, filePath);

  if (seed.fnRenderedPosition) {
    await page.mouse.click(seed.fnRenderedPosition.x, seed.fnRenderedPosition.y);
  }

  await waitOverviewReady(page);
  const final = await page.evaluate((fileIds) => {
    const api = window.depReportOverviewTestApi;
    return {
      filePositions: Object.fromEntries(fileIds.map((id) => [id, api.positionOf(id)])),
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
    };
  }, seed.fileIds);

  const moved = seed.fileIds
    .filter((id) => id !== filePath)
    .map((id) => ({ id, delta: distance(seed.filePositionsAfterSelect[id], final.filePositions[id]) }))
    .filter((entry) => entry.delta !== null && entry.delta > 0.5)
    .sort((a, b) => b.delta - a.delta);

  return {
    seed,
    final,
    movedCount: moved.length,
    maxMovedDelta: moved.length > 0 ? moved[0].delta : 0,
    movedTop: moved.slice(0, 5)
  };
}

async function runSeedDragFileScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);

  const seed = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    api.selectFile(p);
    return {
      layoutRunning: api.isLayoutRunning(),
      viewport: api.viewport(),
      filePosition: api.positionOf(p),
      renderedFilePosition: api.renderedPositionOf(p)
    };
  }, filePath);

  if (seed.renderedFilePosition) {
    await page.mouse.move(seed.renderedFilePosition.x, seed.renderedFilePosition.y);
    await page.mouse.down();
    await page.mouse.move(seed.renderedFilePosition.x + 150, seed.renderedFilePosition.y + 90, { steps: 8 });
    await page.mouse.up();
  }

  const afterDrag = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    return {
      filePosition: api.positionOf(p),
      viewport: api.viewport(),
      layoutRunning: api.isLayoutRunning(),
      animationActive: api.isPositionAnimationActive()
    };
  }, filePath);

  let animationSeenAfterDrag = afterDrag.animationActive;
  for (let i = 0; i < 80; i++) {
    const state = await page.evaluate(() => ({
      layoutRunning: window.depReportOverviewTestApi.isLayoutRunning(),
      animationActive: window.depReportOverviewTestApi.isPositionAnimationActive()
    }));
    if (state.animationActive) animationSeenAfterDrag = true;
    if (!state.layoutRunning && animationSeenAfterDrag) break;
    await sleep(25);
  }

  await waitOverviewReady(page);
  const final = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    const children = api.childPositions(p);
    const childCenter = children && children.length > 0
      ? {
          x: children.reduce((acc, child) => acc + child.x, 0) / children.length,
          y: children.reduce((acc, child) => acc + child.y, 0) / children.length
        }
      : null;
    return {
      filePosition: api.positionOf(p),
      childCenter,
      viewport: api.viewport(),
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
    };
  }, filePath);

  return {
    seed,
    afterDrag,
    final,
    animationSeenAfterDrag,
    fileDriftFromDragged: distance(afterDrag.filePosition, final.filePosition),
    childCenterDriftFromFile: distance(final.filePosition, final.childCenter)
  };
}

async function runSeedDragFunctionScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
  await page.waitForFunction(
    () => window.depReportOverviewTestApi.nodeIds().some((id) => id.indexOf('/') === -1 && id.indexOf('pull-') !== 0),
    { timeout: 5000 }
  );
  await sleep(60);

  const seed = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    const functionIds = api.nodeIds().filter((id) => id.indexOf('/') === -1 && id.indexOf('pull-') !== 0);
    const fnId = functionIds.length > 0 ? functionIds[0] : '';
    return {
      layoutRunning: api.isLayoutRunning(),
      viewport: api.viewport(),
      fnId,
      filePosition: api.positionOf(p),
      fnPosition: fnId ? api.positionOf(fnId) : null,
      fnRenderedPosition: fnId ? api.renderedPositionOf(fnId) : null
    };
  }, filePath);

  const dragSamples = [];
  if (seed.fnRenderedPosition) {
    await page.mouse.move(seed.fnRenderedPosition.x, seed.fnRenderedPosition.y);
    await page.mouse.down();
    for (const step of [1, 2, 3, 4, 5]) {
      await page.mouse.move(seed.fnRenderedPosition.x + step * 26, seed.fnRenderedPosition.y + step * 15, { steps: 4 });
      await sleep(80);
      const sample = await page.evaluate((args) => {
        const api = window.depReportOverviewTestApi;
        const rendered = args.fnId ? api.renderedPositionOf(args.fnId) : null;
        return {
          step: args.step,
          expectedRendered: {
            x: args.start.x + args.step * 26,
            y: args.start.y + args.step * 15
          },
          rendered,
          layoutRunning: api.isLayoutRunning(),
          animationActive: api.isPositionAnimationActive()
        };
      }, { fnId: seed.fnId, start: seed.fnRenderedPosition, step });
      dragSamples.push(Object.assign({}, sample, {
        renderedDelta: distance(sample.rendered, sample.expectedRendered)
      }));
    }
    await page.mouse.up();
  }

  const afterDrag = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    return {
      filePosition: api.positionOf(args.filePath),
      fnPosition: args.fnId ? api.positionOf(args.fnId) : null,
      layoutRunning: api.isLayoutRunning(),
      animationActive: api.isPositionAnimationActive(),
      viewport: api.viewport()
    };
  }, { filePath, fnId: seed.fnId });

  let animationSeenAfterDrag = afterDrag.animationActive;
  for (let i = 0; i < 80; i++) {
    const state = await page.evaluate(() => ({
      layoutRunning: window.depReportOverviewTestApi.isLayoutRunning(),
      animationActive: window.depReportOverviewTestApi.isPositionAnimationActive()
    }));
    if (state.animationActive) animationSeenAfterDrag = true;
    if (!state.layoutRunning && animationSeenAfterDrag) break;
    await sleep(25);
  }

  await waitOverviewReady(page);
  const final = await page.evaluate((args) => {
    const api = window.depReportOverviewTestApi;
    const children = api.childPositions(args.filePath);
    const childCenter = children && children.length > 0
      ? {
          x: children.reduce((acc, child) => acc + child.x, 0) / children.length,
          y: children.reduce((acc, child) => acc + child.y, 0) / children.length
        }
      : null;
    return {
      filePosition: api.positionOf(args.filePath),
      fnPosition: args.fnId ? api.positionOf(args.fnId) : null,
      childCenter,
      viewport: api.viewport(),
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
    };
  }, { filePath, fnId: seed.fnId });

  return {
    seed,
    dragSamples,
    afterDrag,
    final,
    animationSeenAfterDrag,
    fnMovedFromSeed: distance(seed.fnPosition, afterDrag.fnPosition),
    fnFinalDriftFromDragged: distance(afterDrag.fnPosition, final.fnPosition),
    fileFinalDriftFromDragged: distance(afterDrag.filePosition, final.filePosition),
    childCenterDriftFromFile: distance(final.filePosition, final.childCenter)
  };
}

async function overviewBackgroundPoint(page) {
  return page.evaluate(() => {
    const graph = document.getElementById('overviewGraph');
    const cy = graph && graph._cyreg ? graph._cyreg.cy : null;
    if (!graph || !cy) return null;
    const rect = graph.getBoundingClientRect();
    const occupied = cy.nodes().map((n) => n.renderedBoundingBox({ includeLabels: true, includeOverlays: false }));
    function free(rx, ry) {
      return !occupied.some((b) => rx >= b.x1 - 8 && rx <= b.x2 + 8 && ry >= b.y1 - 8 && ry <= b.y2 + 8);
    }
    for (let gy = rect.height - 20; gy > 40; gy -= 20) {
      for (let gx = 20; gx < rect.width - 20; gx += 20) {
        if (free(gx, gy)) return { x: rect.left + gx, y: rect.top + gy };
      }
    }
    return null;
  });
}

async function runDraggedFunctionSeedResetScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);
  await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
  await waitOverviewReady(page);

  const before = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    const fnIds = api.nodeIds().filter((id) => id.indexOf('/') === -1 && id.indexOf('pull-') !== 0).slice(0, 2);
    return {
      fnIds,
      positions: Object.fromEntries(fnIds.map((id) => [id, api.positionOf(id)])),
      rendered: Object.fromEntries(fnIds.map((id) => [id, api.renderedPositionOf(id)]))
    };
  }, filePath);

  const offsets = [{ x: 120, y: 70 }, { x: -95, y: 65 }];
  for (let i = 0; i < before.fnIds.length; i++) {
    const rendered = before.rendered[before.fnIds[i]];
    const offset = offsets[i] || offsets[0];
    if (!rendered) continue;
    await page.mouse.move(rendered.x, rendered.y);
    await page.mouse.down();
    await page.mouse.move(rendered.x + offset.x, rendered.y + offset.y, { steps: 8 });
    await page.mouse.up();
    await sleep(80);
  }

  const dragged = await page.evaluate((fnIds) => {
    const api = window.depReportOverviewTestApi;
    return Object.fromEntries(fnIds.map((id) => [id, api.positionOf(id)]));
  }, before.fnIds);

  const bg = await overviewBackgroundPoint(page);
  if (bg) await page.mouse.click(bg.x, bg.y);
  await waitOverviewReady(page);

  const reselectedSeed = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    api.selectFile(p);
    const fnIds = api.nodeIds().filter((id) => id.indexOf('/') === -1 && id.indexOf('pull-') !== 0).slice(0, 2);
    return {
      fnIds,
      positions: Object.fromEntries(fnIds.map((id) => [id, api.positionOf(id)])),
      layoutRunning: api.isLayoutRunning()
    };
  }, filePath);

  await waitOverviewReady(page);
  const final = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return { renderedMatchesCurrent: api.renderedSignature() === api.currentSignature() };
  });

  const draggedDistances = reselectedSeed.fnIds.map((id) => distance(dragged[id], reselectedSeed.positions[id]));

  return {
    available: Boolean(bg) && before.fnIds.length > 0,
    before,
    dragged,
    reselectedSeed,
    draggedDistances,
    minDraggedDistance: draggedDistances.length > 0 ? Math.min(...draggedDistances) : null,
    final
  };
}

// Problem 2: ファイル選択の seed 窓内に背景クリック相当の無選択化を行うと、以前は
// 詳細ペインだけ無選択になりマップはファイル選択のまま残った。修正後はマップも完全に
// 無選択へ整定することを検証する。
async function runSeedInterruptClearScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);

  const interrupt = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    api.selectFile(p);
    const mid = {
      layoutRunning: api.isLayoutRunning(),
      pending: api.pendingSignature(),
      rendered: api.renderedSignature(),
      fileSelectedFile: (api.classesOf(p) || []).indexOf('dep-selected-file') !== -1
    };
    api.clearSelection();
    return { mid, afterPending: api.pendingSignature() };
  }, filePath);

  await waitOverviewReady(page);
  const final = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    return {
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      currentSignature: api.currentSignature(),
      fileSelectedFile: (api.classesOf(p) || []).indexOf('dep-selected-file') !== -1,
      functionNodeCount: api.nodeIds().filter((id) => id.indexOf('/') === -1).length
    };
  }, filePath);

  return { interrupt, final };
}

async function runRapidSelectionScenario(page) {
  const immediate = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    api.selectFile('src/file_a.c');
    api.selectFile('src/file_c.c');
    return {
      selectedFileClasses: api.classesOf('src/file_c.c') || [],
      fileAMutedImmediate: (api.classesOf('src/file_a.c') || []).indexOf('dep-file-node-muted') !== -1,
      fileCMutedImmediate: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1,
      classPlan: api.lastClassUpdatePlan()
    };
  });

  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 20000 }
  );
  await sleep(50);

  const final = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      selectedFileClasses: api.classesOf('src/file_c.c') || [],
      fileAMuted: (api.classesOf('src/file_a.c') || []).indexOf('dep-file-node-muted') !== -1,
      fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1
    };
  });

  return { immediate, final };
}

// ファイルを非表示にした後、一般的な選択変更では復活せず、背景クリック相当の無選択でも
// 維持され、初期化 (resetGraph) でのみ全復活することを検証する。
async function runHidePersistScenario(page) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_a.c'));
  await waitOverviewReady(page);

  const afterHide = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    api.hideFile('src/file_c.c');
    return {
      hiddenFiles: api.hiddenFiles(),
      noticeVisible: api.hiddenNoticeVisible(),
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1
    };
  });

  // 背景クリック相当の無選択化 (clearOverviewSelection) では復活しない。
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);
  const afterBgClear = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return { fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1, hiddenFiles: api.hiddenFiles() };
  });

  // 別ファイルを選択しても復活しない (関連扱いに留まる)。
  await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_b.c'));
  await waitOverviewReady(page);
  const afterOtherSelect = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return { fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1, hiddenFiles: api.hiddenFiles() };
  });

  // 初期化で全復活し、ラベルも消える。
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  const afterReset = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1,
      hiddenFiles: api.hiddenFiles(),
      noticeVisible: api.hiddenNoticeVisible()
    };
  });

  return { afterHide, afterBgClear, afterOtherSelect, afterReset };
}

// 非表示ファイル自身を選択対象にすると復活し、元の位置近傍へ再表示されることを検証する。
async function runHideRestoreBySelectScenario(page) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  const beforeHide = await page.evaluate(() => window.depReportOverviewTestApi.positionOf('src/file_c.c'));

  await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_a.c'));
  await waitOverviewReady(page);
  await page.evaluate(() => window.depReportOverviewTestApi.hideFile('src/file_c.c'));

  await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_c.c'));
  await waitOverviewReady(page);
  const restored = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1,
      hiddenFiles: api.hiddenFiles(),
      noticeVisible: api.hiddenNoticeVisible(),
      position: api.positionOf('src/file_c.c')
    };
  });
  return { beforeHide, restored, restoreDrift: distance(beforeHide, restored.position) };
}

// 非表示ファイルの関数を選択すると復活するが、関連関数の所属ファイルになっただけ
// (非循環の呼び出し先) では復活しないことを検証する。
async function runHideRestoreByFunctionScenario(page) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  await page.evaluate(() => window.depReportOverviewTestApi.hideFile('src/file_b.c'));

  // a_main (file_a, 非循環) は b_entry (file_b) を呼ぶが、関連先になっただけでは復活しない。
  await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('a_main'));
  await waitOverviewReady(page);
  const afterRelated = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      fileBExists: api.nodeIds().indexOf('src/file_b.c') !== -1,
      bEntryExists: api.nodeIds().indexOf('b_entry') !== -1,
      hiddenFiles: api.hiddenFiles()
    };
  });

  // file_b 自身の関数 (b_entry) を選択すると復活する。
  await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('b_entry'));
  await waitOverviewReady(page);
  const afterOwn = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return { fileBExists: api.nodeIds().indexOf('src/file_b.c') !== -1, hiddenFiles: api.hiddenFiles() };
  });

  return { afterRelated, afterOwn };
}

// 循環参照の関数を選択したとき、循環相手の所属ファイルが非表示でも復活させる例外条件。
async function runHideRestoreByCycleScenario(page) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  await page.evaluate(() => window.depReportOverviewTestApi.hideFile('src/file_e.c'));
  const afterHide = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return { fileEExists: api.nodeIds().indexOf('src/file_e.c') !== -1, hiddenFiles: api.hiddenFiles() };
  });

  // d_cyc (file_d) は e_cyc (file_e) と循環。循環関数選択で file_e を復活させる。
  await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('d_cyc'));
  await waitOverviewReady(page);
  const afterCycleSelect = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      fileEExists: api.nodeIds().indexOf('src/file_e.c') !== -1,
      eCycExists: api.nodeIds().indexOf('e_cyc') !== -1,
      hiddenFiles: api.hiddenFiles()
    };
  });
  return { afterHide, afterCycleSelect };
}

// 「非表示ファイルの再表示」ボタンで、選択状態を変えずに全非表示ファイルを復活させる。
async function runRevealAllScenario(page) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_a.c'));
  await waitOverviewReady(page);

  const afterHide = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    api.hideFile('src/file_b.c');
    api.hideFile('src/file_c.c');
    const notice = document.getElementById('overviewHiddenNotice');
    const style = notice ? window.getComputedStyle(notice) : null;
    return {
      hiddenFiles: api.hiddenFiles(),
      noticeVisible: api.hiddenNoticeVisible(),
      noticeIsButton: Boolean(notice) && notice.tagName.toLowerCase() === 'button',
      noticeClickable: Boolean(style) && style.pointerEvents !== 'none',
      noticeRect: api.hiddenNoticeRect(),
      fileBExists: api.nodeIds().indexOf('src/file_b.c') !== -1,
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1
    };
  });

  // DOM click ではなく実マウスで押し、ボタン消滅後の背後クリック扱いを検証する。
  if (afterHide.noticeRect) {
    await page.mouse.click(
      afterHide.noticeRect.left + afterHide.noticeRect.width / 2,
      afterHide.noticeRect.top + afterHide.noticeRect.height / 2
    );
  } else {
    await page.evaluate(() => document.getElementById('overviewHiddenNotice').click());
  }
  await waitOverviewReady(page);
  const afterReveal = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const fileBClasses = api.classesOf('src/file_b.c') || [];
    const fileCClasses = api.classesOf('src/file_c.c') || [];
    return {
      hiddenFiles: api.hiddenFiles(),
      noticeVisible: api.hiddenNoticeVisible(),
      fileBExists: api.nodeIds().indexOf('src/file_b.c') !== -1,
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1,
      fileBMuted: fileBClasses.indexOf('dep-file-node-muted') !== -1,
      fileCMuted: fileCClasses.indexOf('dep-file-node-muted') !== -1,
      // 選択状態 (file_a) は変えない。
      selectedFileStillA: (api.classesOf('src/file_a.c') || []).indexOf('dep-selected-file') !== -1,
      currentSignature: api.currentSignature()
    };
  });

  return { afterHide, afterReveal };
}

// 再表示時のちらつき検証。選択によりミュートされたファイルを非表示にし、再表示した直後
// (Phase A 同期完了直後 = フレーム待機前) の断面で、再表示ノードが既にミュート クラスを
// 持つこと (= 通常表示の素の見た目を一瞬も露出しないこと) を確認する。
async function runRevealMutedNoFlashScenario(page) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_a.c'));
  await waitOverviewReady(page);

  // file_a 選択でミュートされる file_c を非表示にする。
  await page.evaluate(() => window.depReportOverviewTestApi.hideFile('src/file_c.c'));
  await waitOverviewReady(page);

  // revealAll を呼び、同一同期 (フレーム待機なし) で再表示ノードのクラスを取得する。
  // これは Phase A 完了直後の断面であり、修正後はこの時点でミュート済みであるべき。
  const sample = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const hiddenBefore = api.hiddenFiles();
    api.revealAll();
    const immediateClasses = api.classesOf('src/file_c.c') || [];
    return {
      hiddenBefore,
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1,
      immediateMuted: immediateClasses.indexOf('dep-file-node-muted') !== -1,
      selectedStillA: (api.classesOf('src/file_a.c') || []).indexOf('dep-selected-file') !== -1
    };
  });

  await waitOverviewReady(page);
  const final = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      finalMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1,
      hiddenFiles: api.hiddenFiles()
    };
  });

  return { sample, final };
}

// seed 窓内 (Phase B の cola 計算中) に非表示ファイルを再表示して割り込んだとき、
// 中止された選択ファイルの関数レイアウトがやり直され、seed 円形配置から整定移動することを検証する。
async function runSeedInterruptRevealScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);
  // 選択対象 (file_a) と無関係なファイルを 1 つ非表示にしておく (再表示の対象)。
  await page.evaluate(() => window.depReportOverviewTestApi.hideFile('src/file_c.c'));
  await waitOverviewReady(page);

  // ファイルを実マウスでクリックし、Phase B (cola) を seed から起動させる。
  const pos = await page.evaluate((p) => window.depReportOverviewTestApi.renderedPositionOf(p), filePath);
  if (!pos) return { available: false };
  await page.mouse.click(pos.x, pos.y);
  // seed 窓内 (Phase B 進行中) の断面と seed 配置。
  await sleep(60);
  const seedInfo = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    return { layoutRunning: api.isLayoutRunning(), children: api.childPositions(p) };
  }, filePath);
  // seed 窓内で再表示を起動する (実行中レイアウトを割り込む)。
  const revealStarted = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const before = api.isLayoutRunning();
    const notice = document.getElementById('overviewHiddenNotice');
    if (notice) notice.click();
    return { layoutRunningBeforeReveal: before };
  });
  await sleep(3500);
  const settled = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    return {
      children: api.childPositions(p),
      hiddenFiles: api.hiddenFiles(),
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1,
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      isReady: api.isReady()
    };
  }, filePath);
  return {
    available: true,
    seedLayoutRunning: seedInfo.layoutRunning,
    revealLayoutRunningBefore: revealStarted.layoutRunningBeforeReveal,
    total: settled.children ? settled.children.length : 0,
    moved: countMoved(seedInfo.children, settled.children),
    fileCRevealed: settled.fileCExists,
    hiddenCount: settled.hiddenFiles.length,
    renderedMatchesCurrent: settled.renderedMatchesCurrent,
    isReady: settled.isReady
  };
}

// seed 窓内 (Phase B の cola 計算中) に別ファイルを非表示にして割り込んだとき、
// 中止された選択ファイルの関数レイアウトがやり直され、seed から整定移動することを検証する。
async function runSeedInterruptHideScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
  await waitOverviewReady(page);

  const pos = await page.evaluate((p) => window.depReportOverviewTestApi.renderedPositionOf(p), filePath);
  if (!pos) return { available: false };
  await page.mouse.click(pos.x, pos.y);
  await sleep(60);
  const seedInfo = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    return { layoutRunning: api.isLayoutRunning(), children: api.childPositions(p) };
  }, filePath);
  // seed 窓内で別ファイル (選択ファイルではない) を非表示にして割り込む。
  const hideStarted = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const before = api.isLayoutRunning();
    api.hideFile('src/file_b.c');
    return { layoutRunningBeforeHide: before };
  });
  await sleep(3500);
  const settled = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    return {
      children: api.childPositions(p),
      hiddenFiles: api.hiddenFiles(),
      fileBExists: api.nodeIds().indexOf('src/file_b.c') !== -1,
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      isReady: api.isReady()
    };
  }, filePath);
  return {
    available: true,
    seedLayoutRunning: seedInfo.layoutRunning,
    hideLayoutRunningBefore: hideStarted.layoutRunningBeforeHide,
    total: settled.children ? settled.children.length : 0,
    moved: countMoved(seedInfo.children, settled.children),
    fileBHidden: !settled.fileBExists,
    hiddenCount: settled.hiddenFiles.length,
    renderedMatchesCurrent: settled.renderedMatchesCurrent,
    isReady: settled.isReady
  };
}

async function run(reportPath) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 1000 });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push('console:' + m.text()); });
    await page.evaluateOnNewDocument(() => { window.__DEP_REPORT_TEST__ = true; });
    await page.goto('file://' + reportPath, { waitUntil: 'load' });

    await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
    await page.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await page.waitForFunction(() => window.depReportOverviewTestApi.isInitializing(), { timeout: 5000 });
    const initialTabInterrupt = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      api.activateFunctionList();
      return {
        initializing: api.isInitializing(),
        elementCount: api.elementCount(),
        renderedSignature: api.renderedSignature(),
        pendingSignature: api.pendingSignature(),
        layoutRunning: api.isLayoutRunning()
      };
    });
    await page.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await page.waitForFunction(() => window.depReportOverviewTestApi.isReady(), { timeout: 20000 });
    await page.waitForFunction(() => !window.depReportOverviewTestApi.isLayoutRunning(), { timeout: 20000 });
    initialTabInterrupt.afterReturn = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        initializing: api.isInitializing(),
        elementCount: api.elementCount(),
        renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
        isReady: api.isReady()
      };
    });

    const initialHiddenSelection = await runInitialHiddenSelectionScenario(browser, reportPath, errors, 'src/file_a.c');

    const initialNodeIds = await page.evaluate(() => window.depReportOverviewTestApi.nodeIds());
    const styleState = await runStyleScenario(page);
    await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
    await waitOverviewReady(page);

    // クリック直後 (selectFile 同期完了直後 = Phase A 完了 / Phase C 未適用) の断面。
    const sync = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      api.selectFile('src/file_a.c');
      return {
        selectedFileClasses: api.classesOf('src/file_a.c') || [],
        functionNodes: api.nodeIds().filter((id) => id.indexOf('/') === -1),
        fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1,
        classPlan: api.lastClassUpdatePlan()
      };
    });

    // レイアウト + アニメーション + Phase C 完了待ち。
    await waitOverviewReady(page);
    const final = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
        fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1,
        fileBMuted: (api.classesOf('src/file_b.c') || []).indexOf('dep-file-node-muted') !== -1,
        functionNodes: api.nodeIds().filter((id) => id.indexOf('/') === -1),
        classPlan: api.lastClassUpdatePlan()
      };
    });

    const phaseTiming = await runPhaseTimingScenario(page, 'src/file_a.c', 'src/file_c.c');

    // 別ファイル選択でも同期反映され、署名が確定すること。
    await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_c.c'));
    const switchSync = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        selectedFileClasses: api.classesOf('src/file_c.c') || [],
        // Phase C 並行化後も、新しく選択した file_c の強調は同期時点で反映される。
        fileAMutedImmediate: (api.classesOf('src/file_a.c') || []).indexOf('dep-file-node-muted') !== -1,
        classPlan: api.lastClassUpdatePlan()
      };
    });

    await page.waitForFunction(() => !window.depReportOverviewTestApi.isLayoutRunning(), { timeout: 20000 });
    const clearSelection = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      api.clearSelection();
      return {
        fileAClasses: api.classesOf('src/file_a.c') || [],
        fileBClasses: api.classesOf('src/file_b.c') || [],
        fileCClasses: api.classesOf('src/file_c.c') || [],
        classPlan: api.lastClassUpdatePlan()
      };
    });
    await waitOverviewReady(page);
    clearSelection.final = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        fileAClasses: api.classesOf('src/file_a.c') || [],
        fileBClasses: api.classesOf('src/file_b.c') || [],
        fileCClasses: api.classesOf('src/file_c.c') || []
      };
    });

    const hiddenTabSelection = await runHiddenTabSelectionScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    // 「レイアウト再実行」実行中の選択変更で状態が固着しないことの検証。実マウス クリックで
    // inert ツールバーの貫通も含めて再現する。
    const relayoutDoubleClick = await runRelayoutDoubleClickScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const relayoutThenBackground = await runRelayoutThenBackgroundScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const rapidSelection = await runRapidSelectionScenario(page);
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const centerStability = await runCenterStabilityScenario(page, 'src/file_a.c');

    // 実マウス クリックでの位置補正検証。grab/free を実際に発火させるため、
    // selectFile 直呼びではなく page.mouse.click を使う。
    // renderedPositionOf 由来の座標クリックは現在のズーム/パンに敏感なため、
    // ビューポートを変えうる seed 窓割り込み シナリオより前に実施する。
    const realClick = await runRealClickScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    // seed 窓内割り込み (API 直呼びのためビューポート非依存)。realClick の後に実施する。
    const seedInterruptFunction = await runSeedInterruptFunctionScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const realSeedInterruptFunctionStability = await runRealSeedInterruptFunctionStabilityScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const seedDragFile = await runSeedDragFileScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const seedDragFunction = await runSeedDragFunctionScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const draggedFunctionSeedReset = await runDraggedFunctionSeedResetScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);

    const seedInterruptClear = await runSeedInterruptClearScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
    await waitOverviewReady(page);

    // 右クリックによる「このファイルを非表示」と復活条件の検証。各シナリオは冒頭で
    // resetGraph により非表示を含む全状態を初期化してから開始する。
    const hidePersist = await runHidePersistScenario(page);
    const hideRestoreBySelect = await runHideRestoreBySelectScenario(page);
    const hideRestoreByFunction = await runHideRestoreByFunctionScenario(page);
    const hideRestoreByCycle = await runHideRestoreByCycleScenario(page);
    const revealAll = await runRevealAllScenario(page);
    await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
    await waitOverviewReady(page);
    const revealMutedNoFlash = await runRevealMutedNoFlashScenario(page);
    await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
    await waitOverviewReady(page);

    // seed 窓内の表示/非表示割り込みで、選択ファイルの関数レイアウトがやり直されることを検証する。
    const seedInterruptReveal = await runSeedInterruptRevealScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
    await waitOverviewReady(page);
    const seedInterruptHide = await runSeedInterruptHideScenario(page, 'src/file_a.c');
    await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
    await waitOverviewReady(page);

    return {
      initialNodeIds,
      initialTabInterrupt,
      initialHiddenSelection,
      styleState,
      sync,
      final,
      phaseTiming,
      switchSync,
      clearSelection,
      hiddenTabSelection,
      relayoutDoubleClick,
      relayoutThenBackground,
      rapidSelection,
      seedInterruptFunction,
      seedInterruptClear,
      centerStability,
      realClick,
      hidePersist,
      realSeedInterruptFunctionStability,
      seedDragFile,
      seedDragFunction,
      draggedFunctionSeedReset,
      hideRestoreBySelect,
      hideRestoreByFunction,
      hideRestoreByCycle,
      revealAll,
      revealMutedNoFlash,
      seedInterruptReveal,
      seedInterruptHide,
      pageErrors: errors.filter((e) => e.indexOf('ERR_FILE_NOT_FOUND') === -1)
    };
  } finally {
    await browser.close();
  }
}

(async () => {
  const reportPath = process.argv[2];
  if (!reportPath) {
    console.error('usage: node overview_interaction_probe.js <index.html path>');
    process.exit(2);
  }
  try {
    const result = await run(path.resolve(reportPath));
    console.log('RESULT ' + JSON.stringify(result));
  } catch (err) {
    console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
    process.exit(1);
  }
})();
