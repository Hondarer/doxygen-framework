'use strict';

// 詳細ペイン (関数一覧・ファイル一覧・全体マップ) の「コピー」ボタンを検証するプローブ。
//
// 確認内容:
//   1. 関数一覧タブで関数選択 -> コピー -> 表示内容 (関数名) と #tab=functions&fn=... の URL。
//   2. ファイル一覧タブでファイル選択 -> コピー -> ファイル パスと #tab=files&file=... の URL。
//   3. 全体マップで関数選択 -> コピー -> #tab=overview&fn=... の URL。
//
// navigator.clipboard.writeText はスタブし、書き込まれた文字列を window.__copiedText に捕捉する。
// argv: index.html パス、関数 id、ファイル パス。結果は "RESULT " 接頭辞付き JSON 1 行。

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

async function waitOverviewReady(page) {
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && !window.depReportOverviewTestApi.isPositionAnimationActive()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 60000 }
  );
  await sleep(200);
}

async function copyFrom(page, sourceId) {
  return page.evaluate(async (id) => {
    window.__copiedText = null;
    const button = document.querySelector('.dep-detail-copy[data-copy-source="' + id + '"]');
    if (!button) return { clicked: false, text: null };
    button.click();
    for (let i = 0; i < 50 && window.__copiedText === null; i++) {
      await new Promise((r) => setTimeout(r, 20));
    }
    return { clicked: true, text: window.__copiedText, label: button.textContent };
  }, sourceId);
}

async function run(reportPath, functionId, filePath) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const errors = [];
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 1000 });
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.evaluateOnNewDocument(() => {
      window.__DEP_REPORT_TEST__ = true;
      window.__copiedText = null;
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: (text) => { window.__copiedText = text; return Promise.resolve(); } },
        configurable: true
      });
    });
    await page.goto('file://' + reportPath, { waitUntil: 'load' });
    await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });

    // 0. 非選択状態ではすべてのコピー ボタンが非活性。
    const initialDisabled = await page.evaluate(() => {
      const out = {};
      for (const button of document.querySelectorAll('.dep-detail-copy')) {
        out[button.getAttribute('data-copy-source')] = button.disabled;
      }
      return out;
    });

    // 1. 関数一覧タブで関数を選択してコピー
    await page.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await sleep(200);
    const selectedDisabled = await page.evaluate(() => {
      const out = {};
      for (const button of document.querySelectorAll('.dep-detail-copy')) {
        out[button.getAttribute('data-copy-source')] = button.disabled;
      }
      return out;
    });
    const functionCopy = await copyFrom(page, 'detail');

    // 2. ファイル一覧タブでファイルを選択してコピー
    await page.evaluate(() => window.depReportOverviewTestApi.activateFileList());
    await page.evaluate((fp) => window.depReportOverviewTestApi.selectFile(fp), filePath);
    await sleep(200);
    const fileCopy = await copyFrom(page, 'fileDetail');

    // 3. 全体マップで関数を選択してコピー
    await page.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await waitOverviewReady(page);
    await page.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await waitOverviewReady(page);
    const overviewCopy = await copyFrom(page, 'overviewDetail');

    return {
      pageErrors: errors,
      initialDisabled,
      selectedDisabled,
      functionCopy,
      fileCopy,
      overviewCopy
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  const functionId = process.argv[3] || 'c_2';
  const filePath = process.argv[4] || 'src/chain.c';
  if (!reportPath) {
    console.error('usage: node detail_copy_probe.js <index.html path> [function id] [file path]');
    process.exit(2);
  }
  run(path.resolve(reportPath), functionId, filePath)
    .then((result) => {
      console.log('RESULT ' + JSON.stringify(result));
    })
    .catch((err) => {
      console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
      process.exit(1);
    });
}
