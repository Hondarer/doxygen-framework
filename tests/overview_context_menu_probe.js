'use strict';

// 全体マップの右クリックメニューが、カーソル位置へ補正されてもブラウザーの標準 contextmenu を
// 表示しないことを確認するプローブ。
//
// 検証内容:
//   1. グラフ右下付近で右クリックすると、独自メニューがカーソル位置へ補正されて表示される。
//   2. 表示済みの独自メニュー上で再度右クリックすると、contextmenu がメニュー要素を target にし、
//      defaultPrevented が true になる。
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

async function run(reportPath) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const errors = [];
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 1000 });
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push('console:' + m.text());
    });
    await page.evaluateOnNewDocument(() => { window.__DEP_REPORT_TEST__ = true; });
    await page.goto('file://' + reportPath, { waitUntil: 'load' });
    await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
    await page.evaluate(() => window.depReportOverviewTestApi.activateOverview());
    await waitReady(page);

    const point = await page.evaluate(() => {
      const rect = document.getElementById('overviewGraph').getBoundingClientRect();
      return {
        x: Math.round(rect.right - 24),
        y: Math.round(rect.bottom - 24)
      };
    });

    await page.evaluate(() => {
      window.__contextMenuEvents = [];
      const targetLabel = (target) => {
        if (!target) return '';
        if (target.id) return '#' + target.id;
        const className = typeof target.className === 'string' ? target.className.trim().replace(/\s+/g, '.') : '';
        return target.tagName + (className ? '.' + className : '');
      };
      const record = (phase) => (event) => {
        window.__contextMenuEvents.push({
          phase,
          targetLabel: targetLabel(event.target),
          defaultPrevented: event.defaultPrevented,
          x: event.clientX,
          y: event.clientY
        });
      };
      document.addEventListener('contextmenu', record('capture'), true);
      document.addEventListener('contextmenu', record('bubble'));
    });

    await page.mouse.click(point.x, point.y, { button: 'right' });
    await sleep(200);
    const firstMenu = await page.evaluate((p) => {
      const menu = document.getElementById('overviewGraphMenu');
      const rect = menu.getBoundingClientRect();
      return {
        visible: menu.classList.contains('visible'),
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
        pointInside: rect.left <= p.x
          && p.x <= rect.right
          && rect.top <= p.y
          && p.y <= rect.bottom
      };
    }, point);

    await page.evaluate(() => {
      window.__contextMenuEvents = [];
    });

    await page.mouse.click(point.x, point.y, { button: 'right' });
    await sleep(200);

    const secondMenu = await page.evaluate(() => {
      const menu = document.getElementById('overviewGraphMenu');
      const rect = menu.getBoundingClientRect();
      return {
        visible: menu.classList.contains('visible'),
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height
      };
    });
    const events = await page.evaluate(() => window.__contextMenuEvents || []);

    return {
      pageErrors: errors.filter((e) => e.indexOf('ERR_FILE_NOT_FOUND') === -1),
      point,
      firstMenu,
      secondMenu,
      events
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const reportPath = process.argv[2];
  if (!reportPath) {
    console.error('usage: node overview_context_menu_probe.js <index.html path>');
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
