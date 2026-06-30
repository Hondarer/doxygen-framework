'use strict';

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

function distance(a, b) {
  if (!a || !b) return null;
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function childLayoutStats(children) {
  const xs = children.map((child) => child.x);
  const ys = children.map((child) => child.y);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  return {
    count: children.length,
    width,
    height,
    aspectRatio: Math.max(width, height) / Math.max(1, Math.min(width, height))
  };
}

async function waitOverviewReady(page) {
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 50000 }
  );
  await sleep(100);
}

// page.evaluate に注入する、関数群のスナップショット (幅と中心からファイルへの距離) を返す式。
const CHILD_SNAPSHOT_FN = `(function (p) {
  const api = window.depReportOverviewTestApi;
  const children = api.childPositions(p) || [];
  if (!children.length) return { count: 0, span: 0, childCenterToFile: null };
  const xs = children.map((c) => c.x);
  const ys = children.map((c) => c.y);
  const cc = {
    x: children.reduce((a, c) => a + c.x, 0) / children.length,
    y: children.reduce((a, c) => a + c.y, 0) / children.length
  };
  const fp = api.positionOf(p);
  return {
    count: children.length,
    span: Math.max(...xs) - Math.min(...xs),
    childCenterToFile: fp ? Math.hypot(fp.x - cc.x, fp.y - cc.y) : null
  };
})`;

// 位置アニメーション窓 (cola 後) でファイルを実マウスでドラッグし、固着せずレイアウト結果が
// 採用され、関数群がファイルへ追従しつつ収束することを確認する。
async function runFileDragDuringAnimationScenario(page, filePath) {
  const childSnapshot = (p) => page.evaluate(`(${CHILD_SNAPSHOT_FN})(${JSON.stringify(p)})`);

  // 非ドラッグ時の関数群の広がり (収束の基準)。
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);
  await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
  await waitOverviewReady(page);
  const baseline = await childSnapshot(filePath);

  // もう一度選択し直してアニメーション窓を捉える。
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);
  const viewportBefore = await page.evaluate(() => window.depReportOverviewTestApi.viewport());
  await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
  for (let i = 0; i < 600; i++) {
    if (await page.evaluate(() => window.depReportOverviewTestApi.isPositionAnimationActive())) break;
    if (!(await page.evaluate(() => window.depReportOverviewTestApi.isLayoutRunning()))) break;
    await sleep(4);
  }
  const animationCaught = await page.evaluate(() => window.depReportOverviewTestApi.isPositionAnimationActive());
  const grabPoint = await page.evaluate((p) => window.depReportOverviewTestApi.renderedPositionOf(p), filePath);

  const dragSamples = [];
  if (grabPoint) {
    await page.mouse.move(grabPoint.x, grabPoint.y);
    await page.mouse.down();
    for (const step of [1, 2, 3, 4, 5, 6]) {
      await page.mouse.move(grabPoint.x + step * 45, grabPoint.y + step * 28, { steps: 3 });
      await sleep(70);
      dragSamples.push(Object.assign({ step }, await childSnapshot(filePath)));
    }
    await page.mouse.up();
  }

  let stuck = true;
  for (let i = 0; i < 320; i++) {
    const s = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return { lr: api.isLayoutRunning(), m: api.renderedSignature() === api.currentSignature() };
    });
    if (!s.lr && s.m) { stuck = false; break; }
    await sleep(25);
  }
  await sleep(150);

  const finalChild = await childSnapshot(filePath);
  const finalState = await page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return { renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(), viewport: api.viewport() };
  });

  return {
    animationCaught,
    baselineSpan: baseline.span,
    dragSamples,
    stuck,
    final: Object.assign({}, finalChild, finalState),
    viewportBefore,
    viewportAfter: finalState.viewport
  };
}

async function run(reportPath, filePath) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1100 });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error' && m.text().indexOf('ERR_FILE_NOT_FOUND') === -1) errors.push('console:' + m.text()); });
    await page.evaluateOnNewDocument(() => { window.__DEP_REPORT_TEST__ = true; });
    await page.goto('file://' + reportPath, { waitUntil: 'load' });

    await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
    await page.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await waitOverviewReady(page);

    const before = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      const fileIds = api.nodeIds().filter((id) => id.indexOf('src/') === 0);
      return {
        fileIds,
        filePositions: Object.fromEntries(fileIds.map((id) => [id, api.positionOf(id)])),
        viewport: api.viewport()
      };
    });

    await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
    await waitOverviewReady(page);

    const after = await page.evaluate((args) => {
      const api = window.depReportOverviewTestApi;
      return {
        children: api.childPositions(args.filePath),
        selectedFileBox: api.renderedBoundingBoxOf(args.filePath),
        graphSize: api.graphSize(),
        viewport: api.viewport(),
        filePositions: Object.fromEntries(args.fileIds.map((id) => [id, api.positionOf(id)])),
        renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
      };
    }, { filePath, fileIds: before.fileIds });

    const moved = before.fileIds
      .filter((id) => id !== filePath)
      .map((id) => ({ id, delta: distance(before.filePositions[id], after.filePositions[id]) }))
      .filter((entry) => entry.delta !== null && entry.delta > 0.5)
      .sort((a, b) => b.delta - a.delta);

    const fileDragDuringAnimation = await runFileDragDuringAnimationScenario(page, filePath);

    return {
      pageErrors: errors,
      childLayout: childLayoutStats(after.children || []),
      selectedFileBox: after.selectedFileBox,
      graphSize: after.graphSize,
      viewportBefore: before.viewport,
      viewportAfter: after.viewport,
      renderedMatchesCurrent: after.renderedMatchesCurrent,
      movedFileCount: moved.length,
      movedTop: moved.slice(0, 5),
      fileDragDuringAnimation
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  const filePath = process.argv[3] || 'src/big_file.c';
  if (!reportPath) {
    console.error('usage: node overview_large_layout_probe.js <index.html path> [file path]');
    process.exit(2);
  }
  run(path.resolve(reportPath), filePath)
    .then((result) => {
      console.log('RESULT ' + JSON.stringify(result));
    })
    .catch((err) => {
      console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
      process.exit(1);
    });
}
