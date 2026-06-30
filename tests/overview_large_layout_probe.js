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

    return {
      pageErrors: errors,
      childLayout: childLayoutStats(after.children || []),
      selectedFileBox: after.selectedFileBox,
      graphSize: after.graphSize,
      viewportBefore: before.viewport,
      viewportAfter: after.viewport,
      renderedMatchesCurrent: after.renderedMatchesCurrent,
      movedFileCount: moved.length,
      movedTop: moved.slice(0, 5)
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
