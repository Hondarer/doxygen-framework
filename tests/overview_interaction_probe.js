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

async function runHiddenTabSelectionScenario(page, filePath) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 20000 }
  );

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

  const final = await page.evaluate((p) => {
    const api = window.depReportOverviewTestApi;
    return {
      hidden: api.isRelayoutHidden(),
      animationActive: api.isPositionAnimationActive(),
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      selectedFileClasses: api.classesOf(p) || [],
      fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1
    };
  }, filePath);

  return {
    immediate,
    animationSeen,
    hiddenDroppedBeforeReady,
    final
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
    const fnIds = api.nodeIds().filter((id) => id.indexOf('src/') === -1);
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
      functionNodeCount: api.nodeIds().filter((id) => id.indexOf('src/') === -1).length
    };
  }, { fnId: interrupt.fnId, filePath });

  return { interrupt, final };
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
      functionNodeCount: api.nodeIds().filter((id) => id.indexOf('src/') === -1).length
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
      fileBExists: api.nodeIds().indexOf('src/file_b.c') !== -1,
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1
    };
  });

  // ボタンをクリックして全件復活させる。
  await page.evaluate(() => document.getElementById('overviewHiddenNotice').click());
  await waitOverviewReady(page);
  const afterReveal = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return {
      hiddenFiles: api.hiddenFiles(),
      noticeVisible: api.hiddenNoticeVisible(),
      fileBExists: api.nodeIds().indexOf('src/file_b.c') !== -1,
      fileCExists: api.nodeIds().indexOf('src/file_c.c') !== -1,
      // 選択状態 (file_a) は変えない。
      selectedFileStillA: (api.classesOf('src/file_a.c') || []).indexOf('dep-selected-file') !== -1,
      currentSignature: api.currentSignature()
    };
  });

  return { afterHide, afterReveal };
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
    await page.waitForFunction(() => window.depReportOverviewTestApi.isReady(), { timeout: 20000 });
    await page.waitForFunction(() => !window.depReportOverviewTestApi.isLayoutRunning(), { timeout: 20000 });

    const initialNodeIds = await page.evaluate(() => window.depReportOverviewTestApi.nodeIds());

    // クリック直後 (selectFile 同期完了直後 = Phase A 完了 / Phase C 未適用) の断面。
    const sync = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      api.selectFile('src/file_a.c');
      return {
        selectedFileClasses: api.classesOf('src/file_a.c') || [],
        functionNodes: api.nodeIds().filter((id) => id.indexOf('src/') === -1),
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
        functionNodes: api.nodeIds().filter((id) => id.indexOf('src/') === -1),
        classPlan: api.lastClassUpdatePlan()
      };
    });

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

    return {
      initialNodeIds,
      sync,
      final,
      switchSync,
      clearSelection,
      hiddenTabSelection,
      rapidSelection,
      seedInterruptFunction,
      seedInterruptClear,
      centerStability,
      realClick,
      hidePersist,
      hideRestoreBySelect,
      hideRestoreByFunction,
      hideRestoreByCycle,
      revealAll,
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
