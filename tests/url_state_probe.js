'use strict';

// 依存関係レポートの URL ハッシュ (#tab=...&fn=... / &file=...) によるタブ・選択状態の
// 復元と、操作に応じたハッシュの追従更新を確認するプローブ。
//
// 確認内容:
//   1. #tab=overview&fn=<id> で開く -> 全体マップ タブがアクティブで関数が選択済み。
//   2. #tab=files&file=<パス> で開く -> ファイル一覧タブがアクティブでファイルが選択済み。
//   3. ハッシュなしで開く -> 従来どおり関数一覧タブ (後方互換)。ハッシュは書き込まれない。
//   4. ページ内でタブ切り替えと選択を行う -> location.hash が追従する。
//   5. ページ表示後にハッシュを書き換える (hashchange) -> 状態が追従する。
//
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

async function newReportPage(browser, url, errors) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000 });
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => {
    if (m.type() === 'error' && m.text().indexOf('ERR_FILE_NOT_FOUND') === -1) errors.push('console:' + m.text());
  });
  await page.evaluateOnNewDocument(() => { window.__DEP_REPORT_TEST__ = true; });
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
  return page;
}

async function pageState(page) {
  return page.evaluate(() => {
    const activeButton = document.querySelector('.dep-tab.active');
    let selection = ['', '', ''];
    try {
      selection = JSON.parse(window.depReportOverviewTestApi.selectionSignature
        ? window.depReportOverviewTestApi.selectionSignature()
        : window.depReportOverviewTestApi.currentSignature());
    } catch (err) {
      selection = ['', '', ''];
    }
    return {
      activePanel: activeButton ? activeButton.getAttribute('data-tab-target') : '',
      selectedId: selection[0] || '',
      selectedFilePath: selection[1] || '',
      hash: window.location.hash
    };
  });
}

async function run(reportPath, functionId, filePath) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const errors = [];
  const baseUrl = 'file://' + reportPath;
  try {
    // 1. 関数指定 + 全体マップ
    const encodedFn = encodeURIComponent(functionId);
    let page = await newReportPage(browser, baseUrl + '#tab=overview&fn=' + encodedFn, errors);
    await sleep(400);
    const fnScenario = await pageState(page);
    await page.close();

    // 2. ファイル指定 + ファイル一覧
    let pageFile = await newReportPage(browser, baseUrl + '#tab=files&file=' + encodeURIComponent(filePath), errors);
    await sleep(400);
    const fileScenario = await pageState(pageFile);
    await pageFile.close();

    // 3. ハッシュなし (後方互換) + 4. 操作に応じたハッシュ追従 + 5. hashchange 追従
    const pagePlain = await newReportPage(browser, baseUrl, errors);
    await sleep(400);
    const plainScenario = await pageState(pagePlain);
    await pagePlain.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await pagePlain.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await sleep(200);
    const afterInteraction = await pageState(pagePlain);
    await pagePlain.evaluate((fp) => {
      window.location.hash = 'tab=files&file=' + encodeURIComponent(fp);
    }, filePath);
    await sleep(400);
    const afterHashChange = await pageState(pagePlain);
    await pagePlain.close();

    return {
      pageErrors: errors,
      fnScenario,
      fileScenario,
      plainScenario,
      afterInteraction,
      afterHashChange
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  const functionId = process.argv[3] || 'f_01';
  const filePath = process.argv[4] || 'src/ext_a.c';
  if (!reportPath) {
    console.error('usage: node url_state_probe.js <index.html path> [function id] [file path]');
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
