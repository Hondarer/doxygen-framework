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
        fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1
      };
    });

    // レイアウト + アニメーション + Phase C 完了待ち。
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
        fileCMuted: (api.classesOf('src/file_c.c') || []).indexOf('dep-file-node-muted') !== -1,
        fileBMuted: (api.classesOf('src/file_b.c') || []).indexOf('dep-file-node-muted') !== -1,
        functionNodes: api.nodeIds().filter((id) => id.indexOf('src/') === -1)
      };
    });

    // 別ファイル選択でも同期反映され、署名が確定すること。
    await page.evaluate(() => window.depReportOverviewTestApi.selectFile('src/file_c.c'));
    const switchSync = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      return {
        selectedFileClasses: api.classesOf('src/file_c.c') || [],
        // 直前に選択していた file_a は興味対象外となるが、ミュートは Phase C へ遅延 (同期時点では未適用)。
        fileAMutedImmediate: (api.classesOf('src/file_a.c') || []).indexOf('dep-file-node-muted') !== -1
      };
    });

    // 背景クリック相当 (選択解除)。
    await page.waitForFunction(() => !window.depReportOverviewTestApi.isLayoutRunning(), { timeout: 20000 });
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await sleep(800);

    // 実マウス クリックでの位置補正検証。grab/free を実際に発火させるため、
    // selectFile 直呼びではなく page.mouse.click を使う。
    const realClick = await runRealClickScenario(page, 'src/file_a.c');

    return {
      initialNodeIds,
      sync,
      final,
      switchSync,
      realClick,
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
