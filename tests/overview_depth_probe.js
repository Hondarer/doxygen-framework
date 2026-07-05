'use strict';

// 全体マップ背景メニューの呼び出し元/先 表示深さ設定 (非表示/1 つ先/すべて) を検証するプローブ。
//
// 確認内容:
//   1. 既定 (caller=1, callee=1) で選択関数の 1 段先が表示される。
//   2. callee=all / caller=all で推移閉包に拡張される。
//   3. caller=0 で呼び出し元側が消える。
//   4. 選択関数の循環グループ全体は、caller/callee がともに 0 でも表示される。
//   5. メニューのチェック表示が現在値と一致する。
//   6. 「初期化」で深さ設定が既定 (1, 1) に戻る。
//   7. caller=all/callee=all で、展開経路上のエッジ (c_0->c_1 など、選択から 2 段以上離れた
//      エッジも含む) はすべて強調され、両端が表示されていても展開経路に含まれない
//      「ルート外」エッジ (c_0->c_3) は強調されない。
//
// argv: index.html パス。結果は "RESULT " 接頭辞付き JSON 1 行。

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

async function waitReady(page) {
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && !window.depReportOverviewTestApi.isPositionAnimationActive()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 60000 }
  );
  await sleep(200);
}

function nodeIds(page) {
  return page.evaluate(() => window.depReportOverviewTestApi.nodeIds().filter((id) => id.indexOf('/') === -1));
}

function isEdgeEmphasized(page, edgeId) {
  return page.evaluate(
    (id) => (window.depReportOverviewTestApi.classesOf(id) || []).includes('dep-function-edge'),
    edgeId
  );
}

async function run(reportPath) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const errors = [];
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 1000 });
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.evaluateOnNewDocument(() => { window.__DEP_REPORT_TEST__ = true; });
    await page.goto('file://' + reportPath, { waitUntil: 'load' });
    await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
    await page.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await waitReady(page);

    // 1. c_2 選択 (既定 1/1)
    await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('c_2'));
    await waitReady(page);
    const defaultNodes = (await nodeIds(page)).sort();

    // 2a. 呼び出し先 すべて
    await page.evaluate(() => window.depReportOverviewTestApi.setOverviewDepth('callee', 'all'));
    await waitReady(page);
    const calleeAllNodes = (await nodeIds(page)).sort();

    // 2b. 呼び出し元 すべて (呼び出し先 all を維持したまま)
    await page.evaluate(() => window.depReportOverviewTestApi.setOverviewDepth('caller', 'all'));
    await waitReady(page);
    const bothAllNodes = (await nodeIds(page)).sort();

    // 7. 展開経路上のエッジはすべて強調され、ルート外エッジ (c_0->c_3) は強調されない。
    const routeEdgesEmphasized = {
      c0_c1: await isEdgeEmphasized(page, 'c_0->c_1'),
      c1_c2: await isEdgeEmphasized(page, 'c_1->c_2'),
      c2_c3: await isEdgeEmphasized(page, 'c_2->c_3'),
      c3_c4: await isEdgeEmphasized(page, 'c_3->c_4'),
      c2_x1: await isEdgeEmphasized(page, 'c_2->x_1'),
      x1_x2: await isEdgeEmphasized(page, 'x_1->x_2'),
      x2_x1: await isEdgeEmphasized(page, 'x_2->x_1')
    };
    const nonRouteEdgeEmphasized = await isEdgeEmphasized(page, 'c_0->c_3');

    // 3. 呼び出し元 非表示
    await page.evaluate(() => window.depReportOverviewTestApi.setOverviewDepth('caller', '0'));
    await waitReady(page);
    const callerHiddenNodes = (await nodeIds(page)).sort();

    // 4. 循環メンバー選択、caller/callee ともに非表示でも循環グループは表示される
    await page.evaluate(() => window.depReportOverviewTestApi.setOverviewDepth('caller', '0'));
    await page.evaluate(() => window.depReportOverviewTestApi.setOverviewDepth('callee', '0'));
    await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('x_1'));
    await waitReady(page);
    const cycleHiddenNodes = (await nodeIds(page)).sort();

    // 5. メニュー チェック表示
    const checkedAfterCycle = await page.evaluate(() => window.depReportOverviewTestApi.overviewDepthMenuChecked());

    // 6. 初期化で (1, 1) に戻る
    await page.evaluate(() => window.depReportOverviewTestApi.resetGraph());
    await waitReady(page);
    const settingsAfterReset = await page.evaluate(() => window.depReportOverviewTestApi.overviewDepthSettings());

    return {
      pageErrors: errors,
      defaultNodes,
      calleeAllNodes,
      bothAllNodes,
      callerHiddenNodes,
      cycleHiddenNodes,
      checkedAfterCycle,
      settingsAfterReset,
      routeEdgesEmphasized,
      nonRouteEdgeEmphasized
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  if (!reportPath) {
    console.error('usage: node overview_depth_probe.js <index.html path>');
    process.exit(2);
  }
  run(path.resolve(reportPath))
    .then((result) => {
      console.log('RESULT ' + JSON.stringify(result));
    })
    .catch((err) => {
      console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
      process.exit(1);
    });
}
