'use strict';

// ファイル選択でレイアウトが収束した後の関数選択で、関数間の再レイアウト (Phase B) が
// 発火することを確認するプローブ。
//
// 再現する不具合: ファイル選択 (全関数表示) から関数選択へ縮小する遷移で、他ファイルへの
// 新規追加ノードが各ファイル単一子のみだと、単一子スキップ判定により Phase B 全体が失火し、
// 同一ファイルの残存ノードがファイル選択時の座標のまま取り残される。
//
// argv: index.html パス、ファイル パス、関数 id。結果は "RESULT " 接頭辞付き JSON 1 行。

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
  await sleep(300);
}

async function run(reportPath, filePath, functionId) {
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

    // 1. ファイル選択 -> レイアウト収束まで待機
    await page.evaluate((fp) => window.depReportOverviewTestApi.selectFile(fp), filePath);
    await waitReady(page);
    const beforePositions = await page.evaluate(
      (fp) => window.depReportOverviewTestApi.childPositions(fp),
      filePath
    );

    // レイアウト/位置アニメーションの発火を監視する
    await page.evaluate(() => {
      window.__layoutRan = false;
      const api = window.depReportOverviewTestApi;
      window.__layoutWatch = setInterval(() => {
        if (api.isLayoutRunning() || api.isPositionAnimationActive()) window.__layoutRan = true;
      }, 10);
    });

    // 2. 関数選択 -> Phase B (関数レイアウト) が発火すること
    await page.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await waitReady(page);
    const layoutRan = await page.evaluate(() => {
      clearInterval(window.__layoutWatch);
      return window.__layoutRan;
    });
    const afterPositions = await page.evaluate(
      (fp) => window.depReportOverviewTestApi.childPositions(fp),
      filePath
    );
    const renderedCurrent = await page.evaluate(
      () => window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature()
    );

    // 残存ノードが再配置されたか (ファイル選択時の座標から移動したか) を数える
    const beforeById = new Map((beforePositions || []).map((p) => [p.id, p]));
    let movedCount = 0;
    for (const p of afterPositions || []) {
      const before = beforeById.get(p.id);
      if (!before) continue;
      if (Math.abs(before.x - p.x) > 5 || Math.abs(before.y - p.y) > 5) movedCount += 1;
    }

    return {
      pageErrors: errors,
      layoutRan,
      renderedCurrent,
      movedCount,
      survivorCount: (afterPositions || []).length
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  const filePath = process.argv[3] || 'src/big_file.c';
  const functionId = process.argv[4] || 'f_01';
  if (!reportPath) {
    console.error('usage: node overview_file_to_fn_probe.js <index.html path> [file path] [function id]');
    process.exit(2);
  }
  run(path.resolve(reportPath), filePath, functionId)
    .then((result) => {
      console.log('RESULT ' + JSON.stringify(result));
    })
    .catch((err) => {
      console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
      process.exit(1);
    });
}
