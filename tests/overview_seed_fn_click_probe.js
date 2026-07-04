'use strict';

// 依存関係レポート全体マップの「ファイル実クリック直後の seed 状態で関数を素早く実クリック
// すると再レイアウトがキャンセルされる」不具合の再現プローブ。
//
// overview_reselect_probe.js との相違点:
//   1. selectFile も API でなく実マウス クリックで行う (実操作のイベント列
//      grab -> free -> tap を両クリックで再現する)。
//   2. 関数クリックの遅延 (seed-<ms> / pre-<ms>) と、押下中の微小移動 (+j<px>) や
//      押下保持 (+h<ms>) を遅延モードとして指定できる。
//   3. 複数子を持つ親ごとの子の広がりを測り、親中心で重なったまま取り残されて
//      いないかを判定に含める。
//
// 押下保持 (+h) が失火の決定化に効く: 関数の grab (mousedown) が進行中の cola を中止した後、
// tap (mouseup) の選択 sync がトークンを更新するまでの間に rAF tick が走ると、中止済み cola の
// layoutstop が発火する。保持によりこの間隔を rAF より確実に長くできる。
//
// シナリオ (big_file.c: f_00 が f_01..f_59 を呼ぶ hub 構成):
//   1. 無選択へ。
//   2. ファイル ノードを実マウス クリック -> Phase B (cola) 開始 (seed 円表示)。
//   3. 遅延モードに応じたタイミングで、画面内に見えている関数ノードを実マウス クリック。
//   4. レイアウト完了を待ち、layoutRunCount の増加と親ごとの子の広がりを測る。
//
// 生成済み index.html のパスを argv[2]、対象ファイルパスを argv[3]、遅延モード (カンマ区切り) を
// argv[4]、優先クリック対象の関数 id を argv[5] に受け取り、結果を 1 行の JSON
// ("RESULT " 接頭辞付き) で標準出力へ書き出す。

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

// 実操作のクリックを模す。jitterPx > 0 のときは押下中に数 px の移動を挟み、
// cytoscape の drag イベントを発火させる (タップ判定は維持される移動量)。
async function clickWithJitter(page, pos, jitterPx, holdMs) {
  await page.mouse.move(pos.x, pos.y);
  await page.mouse.down();
  if (jitterPx > 0) {
    await sleep(30);
    await page.mouse.move(pos.x + jitterPx, pos.y + jitterPx, { steps: 2 });
    await sleep(30);
  }
  if (holdMs > 0) await sleep(holdMs);
  await page.mouse.up();
}

async function waitOverviewReady(page) {
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && !window.depReportOverviewTestApi.isPositionAnimationActive()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 50000 }
  );
  await sleep(150);
}

// 画面 (コンテナ矩形) 内に見えている指定ファイル配下の関数ノードを 1 つ選ぶ。
// preferredId が可視ならそれを優先する。
async function findVisibleFunctionTarget(page, filePath, preferredId) {
  return page.evaluate((fp, prefId) => {
    const api = window.depReportOverviewTestApi;
    const rect = document.getElementById('overviewGraph').getBoundingClientRect();
    const margin = 40;
    const inView = (pos) => pos
      && pos.x >= rect.left + margin && pos.x <= rect.right - margin
      && pos.y >= rect.top + margin && pos.y <= rect.bottom - margin;
    if (prefId) {
      const pos = api.renderedPositionOf(prefId);
      if (inView(pos)) return { id: prefId, pos };
    }
    const children = api.childPositions(fp) || [];
    for (const child of children) {
      const pos = api.renderedPositionOf(child.id);
      if (inView(pos)) return { id: child.id, pos };
    }
    return null;
  }, filePath, preferredId || '');
}

// 複数子を持つ親ごとに、子ノード間の最大距離 (広がり) を測る。親中心で重なったまま
// 取り残されている親は spread がほぼ 0 になる。
async function measureParentSpreads(page) {
  return page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    const fileIds = api.nodeIds().filter((id) => id.indexOf('/') !== -1);
    const results = [];
    for (const fileId of fileIds) {
      const children = api.childPositions(fileId) || [];
      if (children.length < 2) continue;
      let spread = 0;
      for (let i = 0; i < children.length; i++) {
        for (let j = i + 1; j < children.length; j++) {
          const d = Math.hypot(children[i].x - children[j].x, children[i].y - children[j].y);
          if (d > spread) spread = d;
        }
      }
      results.push({ fileId, childCount: children.length, spread });
    }
    return results;
  });
}

async function runScenario(page, filePath, delayModeSpec, preferredId) {
  // 遅延モードの末尾に "+j<px>" が付くときは、押下中に <px> の微小移動を挟む
  // (実マウス操作で起きる drag イベント発火を再現する)。
  let delayMode = delayModeSpec;
  let jitterPx = 0;
  let holdMs = 0;
  const jitterMatch = delayMode.match(/\+j(\d+)/);
  if (jitterMatch) jitterPx = Number(jitterMatch[1]);
  const holdMatch = delayMode.match(/\+h(\d+)/);
  if (holdMatch) holdMs = Number(holdMatch[1]);
  delayMode = delayMode.replace(/\+[jh]\d+/g, '');
  // 無選択の初期状態へ戻す。
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);

  const api = 'window.depReportOverviewTestApi';
  const filePos = await page.evaluate(
    (fp) => window.depReportOverviewTestApi.renderedPositionOf(fp),
    filePath
  );
  if (!filePos) {
    return { delayMode, error: 'file node not visible: ' + filePath };
  }

  const runCountBefore = await page.evaluate(() => window.depReportOverviewTestApi.layoutRunCount());

  // 1 回目: ファイル ノードを実マウス クリック (微小移動なし。移動があると tap 判定が
  // 失われファイル選択自体が発生しないため、jitter は関数クリックのみに適用する)。
  await page.mouse.click(filePos.x, filePos.y);

  // 遅延モードに応じて関数クリックのタイミングを決める。
  //   pre-<ms>: layoutRunning を待たず、ファイル クリックから <ms> 後にクリック。
  //   seed-<ms>: layoutRunning が true になってから <ms> 後にクリック。
  let seedCaught = false;
  if (delayMode.indexOf('seed-') === 0) {
    for (let i = 0; i < 500; i++) {
      if (await page.evaluate(() => window.depReportOverviewTestApi.isLayoutRunning())) {
        seedCaught = true;
        break;
      }
      await sleep(3);
    }
    const wait = Number(delayMode.slice('seed-'.length));
    if (wait > 0) await sleep(wait);
  } else {
    const wait = Number(delayMode.slice('pre-'.length));
    if (wait > 0) await sleep(wait);
    seedCaught = await page.evaluate(() => window.depReportOverviewTestApi.isLayoutRunning());
  }

  // クリック対象の関数ノードが描画されるまで少し粘る (pre モードでは Phase A 前の可能性がある)。
  let target = null;
  for (let i = 0; i < 200; i++) {
    target = await findVisibleFunctionTarget(page, filePath, preferredId);
    if (target) break;
    await sleep(5);
  }
  const stateAtClick = await page.evaluate(() => ({
    layoutRunning: window.depReportOverviewTestApi.isLayoutRunning(),
    animActive: window.depReportOverviewTestApi.isPositionAnimationActive(),
    layoutRunCount: window.depReportOverviewTestApi.layoutRunCount()
  }));

  // 2 回目: 関数ノードを実マウス クリック。
  let clicked = false;
  if (target) {
    await clickWithJitter(page, target.pos, jitterPx, holdMs);
    clicked = true;
  }

  // レイアウト完了を待つ。失火した場合も rendered==current にはなり得るため、
  // 追加で短い安定待ちを置いてから計測する。
  await waitOverviewReady(page);
  await sleep(300);

  const after = await page.evaluate(() => {
    const api2 = window.depReportOverviewTestApi;
    let selectedFunctionId = '';
    try { selectedFunctionId = JSON.parse(api2.currentSignature())[0] || ''; } catch (err) { selectedFunctionId = ''; }
    return {
      layoutRunCount: api2.layoutRunCount(),
      renderedMatchesCurrent: api2.renderedSignature() === api2.currentSignature(),
      currentSignature: api2.currentSignature(),
      selectedFunctionId
    };
  });
  const parentSpreads = await measureParentSpreads(page);
  // 広がりがほぼ 0 (子が親中心で重なったまま) の親を「取り残し」と数える。
  const stuckParents = parentSpreads.filter((p) => p.spread < 10);

  return {
    delayMode: delayModeSpec,
    seedCaught,
    clicked,
    clickedFunctionId: target ? target.id : '',
    stateAtClick,
    layoutRunCountBefore: runCountBefore,
    layoutRunCountAfter: after.layoutRunCount,
    renderedMatchesCurrent: after.renderedMatchesCurrent,
    currentSignature: after.currentSignature,
    selectedFunctionId: after.selectedFunctionId,
    parentSpreads,
    stuckParents
  };
}

async function run(reportPath, filePath, delayModes, preferredId) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1100 });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error' && m.text().indexOf('ERR_FILE_NOT_FOUND') === -1) errors.push('console:' + m.text()); });
    if (process.env.DOXYFW_PROBE_DEBUG) {
      page.on('console', (m) => { if (m.text().indexOf('[DBG]') !== -1) console.error(Date.now() + ' ' + m.text()); });
    }
    await page.evaluateOnNewDocument(() => { window.__DEP_REPORT_TEST__ = true; });
    await page.goto('file://' + reportPath, { waitUntil: 'load' });

    await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
    await page.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await waitOverviewReady(page);

    const scenarios = [];
    for (const delayMode of delayModes) {
      scenarios.push(await runScenario(page, filePath, delayMode, preferredId));
    }

    return { pageErrors: errors, filePath, scenarios };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  const filePath = process.argv[3] || 'src/big_file.c';
  const delayModes = (process.argv[4] || 'pre-0,pre-60,seed-0,seed-120,seed-300').split(',');
  if (!reportPath) {
    console.error('usage: node overview_seed_fn_click_probe.js <index.html path> [file path] [delay modes]');
    process.exit(2);
  }
  run(path.resolve(reportPath), filePath, delayModes, process.argv[5] || '')
    .then((result) => {
      console.log('RESULT ' + JSON.stringify(result));
    })
    .catch((err) => {
      console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
      process.exit(1);
    });
}
