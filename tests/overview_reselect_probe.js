'use strict';

// 依存関係レポート全体マップの「Phase B 進行中の関数選択で再レイアウトが失火する」不具合の
// 再現プローブ。ヘッドレス ブラウザの実クリックで再現する。
//
// シナリオ (big_file.c: 60 関数、f_00 が f_01..f_59 を呼ぶ hub 構成):
//   1. 無選択へ。
//   2. selectFile("src/big_file.c") で Phase B (cola) 開始。
//   3. isLayoutRunning() が true になるまでポーリングし、seed 窓 (cola 計算中) を捉える。
//      この時点の layoutRunCount と big_file の子 seed 座標を記録。
//   4. 関数ノード f_01 を実マウスでクリック (grab -> tap(selectFunction) -> free を発火)。
//      これで可視集合が {f_00, f_01} に縮小し、両方とも既存ノードのため diff は空になる。
//   5. レイアウト完了を待つ。
//
// 修正が無いと、中止で seed に取り残された f_00/f_01 が再レイアウトされず (layoutRunCount が
// 増えず、座標が seed のまま) 失火する。修正後は pending 再投入で Phase B が再発火する。
//
// 生成済み index.html のパスを argv[2]、対象ファイルパスを argv[3]、割り込む関数 id を
// argv[4] に受け取り、結果を 1 行の JSON ("RESULT " 接頭辞付き) で標準出力へ書き出す。

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

// seed 座標と最終座標を突き合わせ、しきい値を超えて動いた子ノード数を数える。
function countMoved(seed, settled, threshold) {
  if (!seed || !settled) return 0;
  const seedById = new Map(seed.map((c) => [c.id, c]));
  let moved = 0;
  for (const cur of settled) {
    const s = seedById.get(cur.id);
    if (!s) continue;
    if (Math.hypot(cur.x - s.x, cur.y - s.y) > threshold) moved += 1;
  }
  return moved;
}

async function waitOverviewReady(page) {
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 50000 }
  );
  await sleep(100);
}

async function run(reportPath, filePath, functionId) {
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

    // 1-2. 無選択 -> ファイル選択で Phase B 開始。
    await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
    await waitOverviewReady(page);
    await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);

    // 3. seed 窓 (cola 計算中) を捉える。isLayoutRunning が true になるまで短時間ポーリング。
    let seedCaught = false;
    for (let i = 0; i < 400; i++) {
      if (await page.evaluate(() => window.depReportOverviewTestApi.isLayoutRunning())) {
        seedCaught = true;
        break;
      }
      await sleep(4);
    }
    // seed 窓では pan/zoom によりファイル配下の一部関数がキャンバス外に描画されることがある。
    // 画面 (コンテナ矩形) 内に見えている関数ノードを選び、その中心を実クリックする。どの関数を
    // 選んでも可視集合は {f_00 + その関数} に縮小し、両方とも既存ノードのため再現条件を満たす。
    const beforeClick = await page.evaluate((args) => {
      const api = window.depReportOverviewTestApi;
      const rect = document.getElementById('overviewGraph').getBoundingClientRect();
      const margin = 40;
      const fnIds = api.nodeIds().filter((id) => id.indexOf('/') === -1 && id.indexOf('pull-') !== 0);
      let target = null;
      for (const id of fnIds) {
        const pos = api.renderedPositionOf(id);
        if (!pos) continue;
        if (pos.x >= rect.left + margin && pos.x <= rect.right - margin
          && pos.y >= rect.top + margin && pos.y <= rect.bottom - margin) {
          target = { id, pos };
          break;
        }
      }
      return {
        layoutRunning: api.isLayoutRunning(),
        layoutRunCount: api.layoutRunCount(),
        seedChildren: api.childPositions(args.filePath),
        target
      };
    }, { filePath, functionId });

    // 4. 関数ノードを実マウスでクリック (grab -> tap(selectFunction) -> free)。
    let clicked = false;
    const clickedFunctionId = beforeClick.target ? beforeClick.target.id : "";
    if (beforeClick.target) {
      await page.mouse.click(beforeClick.target.pos.x, beforeClick.target.pos.y);
      clicked = true;
    }

    // 5. レイアウト完了待ち。
    await waitOverviewReady(page);

    const after = await page.evaluate(() => {
      const api = window.depReportOverviewTestApi;
      // 実クリックは seed 円上で重なる隣接ノードを掴むことがあるため、実際に選択された関数を
      // currentSignature から取り出して評価する ([selectedId, selectedFilePath, selectedEdgeKey])。
      let selectedFunctionId = "";
      try { selectedFunctionId = JSON.parse(api.currentSignature())[0] || ""; } catch (err) { selectedFunctionId = ""; }
      return {
        layoutRunCount: api.layoutRunCount(),
        renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
        currentSignature: api.currentSignature(),
        selectedFunctionId,
        fnIsCenter: (api.classesOf(selectedFunctionId) || []).indexOf('dep-center-node') !== -1,
        // 割り込み後の可視関数ノード (f_00 + 選択関数が残る)。座標が seed から動いたかを測る。
        remainingChildren: (() => {
          const ids = api.nodeIds().filter((id) => id.indexOf('/') === -1 && id.indexOf('pull-') !== 0);
          return ids.map((id) => Object.assign({ id }, api.positionOf(id) || { x: 0, y: 0 }));
        })()
      };
    });

    // seed からの移動数 (残存関数について)。beforeClick.seedChildren には big_file の子座標
    // (seed 円配置) が入っている。after.remainingChildren と id で突き合わせる。
    const movedFromSeed = countMoved(beforeClick.seedChildren, after.remainingChildren, 1.0);

    return {
      pageErrors: errors,
      filePath,
      functionId,
      clickedFunctionId,
      seedCaught,
      clicked,
      layoutRunningAtSeed: beforeClick.layoutRunning,
      layoutRunCountAtSeed: beforeClick.layoutRunCount,
      layoutRunCountAfter: after.layoutRunCount,
      renderedMatchesCurrent: after.renderedMatchesCurrent,
      currentSignature: after.currentSignature,
      selectedFunctionId: after.selectedFunctionId,
      fnIsCenter: after.fnIsCenter,
      remainingCount: after.remainingChildren.length,
      movedFromSeed
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
    console.error('usage: node overview_reselect_probe.js <index.html path> [file path] [function id]');
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
