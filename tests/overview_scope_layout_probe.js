'use strict';

// 依存関係レポート全体マップの Phase B (cola) 部分コレクション化の効果を計測するプローブ。
// 崩壊 (子なし) ファイルを多数含むレポートで対象ファイルを選択し、次を検証/計測する。
//   - 選択時の cola 投入ノード数 (lastLayoutNodeCount) が、対象ファイルとその関数だけに
//     収まり、崩壊ファイル群を含まないこと (スコープが効いている証拠)。
//   - 対象ファイルの関数が seed からバランスよく分散すること (レイアウト品質の維持)。
//   - 全グラフ経路 (scope=false) と部分コレクション経路 (scope=true) の投入ノード数・
//     純計算時間を同一条件で複数回計測し、中央値を返す (改善効果の報告用)。
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

function median(values) {
  if (!values.length) return null;
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

async function waitOverviewReady(page) {
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning()
      && window.depReportOverviewTestApi.renderedSignature() === window.depReportOverviewTestApi.currentSignature(),
    { timeout: 50000 }
  );
  await sleep(100);
}

// scope 経路を指定してレイアウトを 1 回計測する。実行後はレイアウト停止を待つ。
async function measureOnce(page, scope) {
  const result = await page.evaluate(
    (s) => window.depReportOverviewTestApi.measureLayoutForTest(s),
    scope
  );
  await page.waitForFunction(
    () => !window.depReportOverviewTestApi.isLayoutRunning(),
    { timeout: 50000 }
  );
  await sleep(30);
  return result;
}

async function run(reportPath, filePath, samples) {
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

    // 対象ファイルを選択 (通常経路 = 部分コレクション化が既定)。
    await page.evaluate((p) => window.depReportOverviewTestApi.selectFile(p), filePath);
    await waitOverviewReady(page);

    const selected = await page.evaluate((p) => {
      const api = window.depReportOverviewTestApi;
      return {
        children: api.childPositions(p),
        scopedLayoutNodeCount: api.lastLayoutNodeCount(),
        totalNodeCount: api.totalNodeCount(),
        renderedMatchesCurrent: api.renderedSignature() === api.currentSignature()
      };
    }, filePath);

    // 全グラフ経路 vs 部分コレクション経路の投入ノード数・時間を計測 (対象選択状態のまま)。
    const fullSamples = [];
    const scopedSamples = [];
    for (let i = 0; i < samples; i++) {
      fullSamples.push(await measureOnce(page, false));
      scopedSamples.push(await measureOnce(page, true));
    }

    return {
      pageErrors: errors,
      filePath,
      childLayout: childLayoutStats(selected.children || []),
      scopedLayoutNodeCount: selected.scopedLayoutNodeCount,
      totalNodeCount: selected.totalNodeCount,
      renderedMatchesCurrent: selected.renderedMatchesCurrent,
      measure: {
        samples,
        full: {
          nodeCount: fullSamples[0] ? fullSamples[0].nodeCount : null,
          durationMsMedian: median(fullSamples.map((s) => s.durationMs))
        },
        scoped: {
          nodeCount: scopedSamples[0] ? scopedSamples[0].nodeCount : null,
          durationMsMedian: median(scopedSamples.map((s) => s.durationMs))
        }
      }
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  const filePath = process.argv[3] || 'src/hub.c';
  const samples = Number(process.argv[4] || 5);
  if (!reportPath) {
    console.error('usage: node overview_scope_layout_probe.js <index.html path> [file path] [samples]');
    process.exit(2);
  }
  run(path.resolve(reportPath), filePath, samples)
    .then((result) => {
      console.log('RESULT ' + JSON.stringify(result));
    })
    .catch((err) => {
      console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
      process.exit(1);
    });
}
