'use strict';

// 依存関係レポート全体マップの「seed 表示 (Phase B) 中に選択済みファイル自身を再クリック
// すると関数配置がずれて最適レイアウトにならない」不具合の再現プローブ。
// ヘッドレス ブラウザの実マウスで再現する。
//
// 原因は 2 つ。
// 1. 実ドラッグを伴わない free (純タップ) でも handleOverviewNodeFree が
//    rememberOverviewUserMovedPositions を呼び、ファイルが「ユーザー移動済み」と
//    誤記録されて位置アニメーションが live アンカー経路に入る。
// 2. live アンカーが子 (関数) の再配置中に parent.position() を読む。compound の位置は
//    子から導出されるため、静止 grab では錨自体が子の移動で毎フレーム流され、クラスタが
//    漂流して重心がファイルから離れ、外周の関数が取り残される。
//
// シナリオ (big_file.c: 60 関数、f_00 が f_01..f_59 を呼ぶ hub 構成):
//   control:        再クリックなし。span と重心-ファイル距離の基準値を得る。
//   tapDuringCola:  cola 窓を捉えて mouse.down -> 保持 (cola 終了を跨ぐ) -> mouse.up。
//   tapDuringAnim:  cola 終了後の位置アニメーション窓で同様の押下保持。
//
// 修正が無いと tap シナリオで重心-ファイル距離が control から大きく増える (漂流)。
// 修正後は純タップが痕跡を残さず、control と同じ経路で収束する。
//
// 生成済み index.html のパスを argv[2]、対象ファイルパスを argv[3] に受け取り、
// 結果を 1 行の JSON ("RESULT " 接頭辞付き) で標準出力へ書き出す。

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
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 50000 }
  );
  await sleep(100);
}

// ファイル ノード自身に命中するクライアント座標を実ヒット テストで選ぶ。ファイル領域内でも
// 関数ノードやエッジが重なる点ではそちらが tap 対象になるため、bbox の幾何だけでは選べない。
// cytoscape の renderer().findNearestElement (モデル座標) で当たり判定を行う。
async function pickFileHitPoint(page, filePath) {
  return page.evaluate((targetPath) => {
    const container = document.getElementById('overviewGraph');
    const cy = container._cyreg.cy;
    const rect = container.getBoundingClientRect();
    const pan = cy.pan();
    const zoom = cy.zoom();
    const node = cy.getElementById(targetPath);
    if (!node || node.length === 0) return null;
    const box = node.renderedBoundingBox({ includeLabels: false });
    const insideView = (x, y) => (
      x >= rect.left + 10 && x <= rect.right - 10 && y >= rect.top + 10 && y <= rect.bottom - 10
    );
    const hitsFile = (clientX, clientY) => {
      const modelX = (clientX - rect.left - pan.x) / zoom;
      const modelY = (clientY - rect.top - pan.y) / zoom;
      const hit = cy.renderer().findNearestElement(modelX, modelY, true, false);
      return Boolean(hit && hit.isNode && hit.isNode() && hit.id() === targetPath);
    };
    const centerX = rect.left + (box.x1 + box.x2) / 2;
    const centerY = rect.top + (box.y1 + box.y2) / 2;
    const stepX = Math.max(4, (box.x2 - box.x1) / 40);
    const stepY = Math.max(4, (box.y2 - box.y1) / 40);
    for (let radius = 0; radius <= 18; radius++) {
      const offsets = radius === 0
        ? [[0, 0]]
        : [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1], [-1, 1]];
      for (const [dx, dy] of offsets) {
        const x = centerX + dx * radius * stepX;
        const y = centerY + dy * radius * stepY;
        if (!insideView(x, y)) continue;
        if (hitsFile(x, y)) return { x, y };
      }
    }
    return null;
  }, filePath);
}

// 関数ノード群のモデル座標から広がり (最大ペア距離) を求める。
function spanOf(children) {
  let span = 0;
  for (let i = 0; i < children.length; i++) {
    for (let j = i + 1; j < children.length; j++) {
      const d = Math.hypot(children[i].x - children[j].x, children[i].y - children[j].y);
      if (d > span) span = d;
    }
  }
  return span;
}

async function layoutState(page) {
  return page.evaluate(() => {
    const api = window.depReportOverviewTestApi;
    return { running: api.isLayoutRunning(), anim: api.isPositionAnimationActive() };
  });
}

async function measureSettled(page, filePath) {
  const after = await page.evaluate((targetPath) => {
    const api = window.depReportOverviewTestApi;
    const children = api.childPositions(targetPath) || [];
    const filePos = api.positionOf(targetPath);
    let centerToFile = 0;
    if (filePos && children.length > 0) {
      let sumX = 0;
      let sumY = 0;
      for (const c of children) {
        sumX += c.x;
        sumY += c.y;
      }
      centerToFile = Math.hypot(sumX / children.length - filePos.x, sumY / children.length - filePos.y);
    }
    return {
      renderedMatchesCurrent: api.renderedSignature() === api.currentSignature(),
      currentSignature: api.currentSignature(),
      childCount: children.length,
      children,
      centerToFile
    };
  }, filePath);
  return {
    renderedMatchesCurrent: after.renderedMatchesCurrent,
    currentSignature: after.currentSignature,
    childCount: after.childCount,
    settledSpan: spanOf(after.children),
    childCenterToFile: after.childCenterToFile === undefined ? after.centerToFile : after.childCenterToFile
  };
}

// 1 シナリオ実行。mode: "control" (再クリックなし) / "cola" (cola 窓で押下保持) /
// "anim" (位置アニメーション窓で押下保持)。
async function runScenario(page, filePath, mode) {
  await page.evaluate(() => window.depReportOverviewTestApi.clearSelection());
  await waitOverviewReady(page);

  // 無選択からファイル ノードを実クリックし Phase B を開始する。API 直呼びは grab/free を
  // 経ないため、ユーザー操作と同じ実マウスで行う。
  const firstPoint = await pickFileHitPoint(page, filePath);
  if (!firstPoint) throw new Error('file hit point not found: ' + filePath);
  await page.mouse.click(firstPoint.x, firstPoint.y);

  // seed 窓 (Phase B 実行中) を捉える。
  let seedCaught = false;
  for (let i = 0; i < 400; i++) {
    if (await page.evaluate(() => window.depReportOverviewTestApi.isLayoutRunning())) {
      seedCaught = true;
      break;
    }
    await sleep(2);
  }

  let reClicked = false;
  let stateAtDown = null;
  let stateAtUp = null;
  if (mode !== 'control') {
    if (mode === 'anim') {
      // cola 終了後の位置アニメーション窓に入るまで待つ。
      for (let i = 0; i < 200; i++) {
        const state = await layoutState(page);
        if (state.anim || !state.running) break;
        await sleep(4);
      }
    }
    const point = await pickFileHitPoint(page, filePath);
    if (!point) throw new Error('re-click hit point not found: ' + filePath);
    // 実マウスでファイル自身を押下保持つきで再クリックする (grab -> 保持 -> free -> tap)。
    // 保持は rAF 複数フレームを跨がせるための時間で、cola 窓の押下は cola 終了を跨いで
    // アニメーション開始時に grab 状態が観測されるようにする。
    await page.mouse.move(point.x, point.y);
    await page.mouse.down();
    stateAtDown = await layoutState(page);
    await sleep(mode === 'cola' ? 400 : 140);
    stateAtUp = await layoutState(page);
    await page.mouse.up();
    reClicked = true;
  }

  // 固定長の整定待ち。Phase B の cola (deferPositions) + 430ms アニメーションの間、
  // ノードは seed 位置で安定して見えるため、位置の安定検出には頼らない。
  await sleep(3500);
  await waitOverviewReady(page);

  const settled = await measureSettled(page, filePath);
  return Object.assign(
    { mode, seedCaught, reClicked, stateAtDown, stateAtUp },
    settled
  );
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

    const control = await runScenario(page, filePath, 'control');
    const tapDuringCola = await runScenario(page, filePath, 'cola');
    const tapDuringAnim = await runScenario(page, filePath, 'anim');

    return {
      pageErrors: errors,
      filePath,
      control,
      tapDuringCola,
      tapDuringAnim
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  const filePath = process.argv[3] || 'src/big_file.c';
  if (!reportPath) {
    console.error('usage: node overview_file_reclick_probe.js <index.html path> [file path]');
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
