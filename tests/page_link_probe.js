'use strict';

// 詳細ペインの page リンク (make docs 発行のシングルページ md HTML) と、
// 設定メニューのページ種別選択を検証するプローブ。
//
// 確認内容:
//   1. 関数選択 -> リンク欄に page リンクがあり、href が
//      <template を variant で置換>/Files/<fn.file>.html#<関数名の小文字> であること。
//   2. 設定メニューで ja-details へ変更 -> href が追従し、localStorage に保存される。
//   3. リロード後も ja-details が維持される。
//   4. localStorage 未保存時の既定: ブラウザー言語 en では en (通常) になる。
//   5. コピー md に [page](...) が含まれる。
//   6. pageUrlTemplate なしのレポートでは page リンクと設定ボタンが出ない。
//
// argv: page 対応 index.html、page なし index.html、関数 id。結果は "RESULT " 付き JSON 1 行。

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

async function newReportPage(browser, url, errors, options) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000 });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.evaluateOnNewDocument((opts) => {
    window.__DEP_REPORT_TEST__ = true;
    window.__copiedText = null;
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: (text) => { window.__copiedText = text; return Promise.resolve(); } },
      configurable: true
    });
    if (opts && opts.language) {
      Object.defineProperty(navigator, 'language', { value: opts.language, configurable: true });
    }
    if (opts && opts.clearVariant) {
      try {
        window.localStorage.removeItem('doxyfw-dependency-page-variant');
      } catch (err) {
        // localStorage が使えない環境では何もしない
      }
    }
  }, options || {});
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.depReportOverviewTestApi, { timeout: 15000 });
  return page;
}

function pageLinkHref(page) {
  return page.evaluate(() => {
    const link = document.querySelector('#detail a[target="doxyfw-dependency-page"]');
    return link ? link.getAttribute('href') : null;
  });
}

async function run(withPagePath, withoutPagePath, functionId) {
  const puppeteer = resolvePuppeteer();
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const errors = [];
  const withPageUrl = 'file://' + withPagePath;
  try {
    // 1-3, 5: page 対応レポート (ja 環境、localStorage 未保存の状態から開始)
    let page = await newReportPage(browser, withPageUrl, errors, { language: 'ja-JP', clearVariant: true });
    await page.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await sleep(200);
    const hrefJa = await pageLinkHref(page);

    // キャメルケース関数のアンカーは Pandoc auto identifier により小文字化される。
    await page.evaluate(() => window.depReportOverviewTestApi.selectFunction('myCamelFn'));
    await sleep(200);
    const hrefCamel = await pageLinkHref(page);
    await page.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await sleep(200);
    const settingsVisible = await page.evaluate(() => {
      const section = document.getElementById('pageVariantSection');
      return Boolean(section && !section.hidden);
    });

    // 設定メニューで ja-details へ変更
    await page.evaluate(() => {
      const button = document.querySelector('#pageVariantOptions [data-page-variant="ja-details"]');
      if (button) button.click();
    });
    await sleep(200);
    const hrefJaDetails = await pageLinkHref(page);
    const storedVariant = await page.evaluate(() => window.localStorage.getItem('doxyfw-dependency-page-variant'));
    const checkedVariant = await page.evaluate(() => {
      const el = document.querySelector('#pageVariantOptions .checked');
      return el ? el.getAttribute('data-page-variant') : null;
    });

    // 5. コピー md に [page](...) が含まれる
    const copyText = await page.evaluate(async () => {
      window.__copiedText = null;
      const button = document.querySelector('.dep-detail-copy[data-copy-source="detail"]');
      button.click();
      for (let i = 0; i < 50 && window.__copiedText === null; i++) {
        await new Promise((r) => setTimeout(r, 20));
      }
      return window.__copiedText;
    });

    // 3. 開き直しても ja-details が維持される (localStorage 永続化)。
    //    初回ページには clearVariant の初期化スクリプトが登録済みでリロードでも実行される
    //    ため、消去なしの新規ページで確認する。
    await page.close();
    const pageReload = await newReportPage(browser, withPageUrl, errors, { language: 'ja-JP' });
    await pageReload.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await sleep(200);
    const hrefAfterReload = await pageLinkHref(pageReload);
    await pageReload.close();

    // 4. localStorage 未保存の en 環境では既定が en (通常)
    const pageEn = await newReportPage(browser, withPageUrl, errors, { language: 'en-US', clearVariant: true });
    await pageEn.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await sleep(200);
    const hrefEnDefault = await pageLinkHref(pageEn);
    await pageEn.close();

    // 6. pageUrlTemplate なしのレポートでは page リンクと設定ボタンが出ない
    const pagePlain = await newReportPage(browser, 'file://' + withoutPagePath, errors, { language: 'ja-JP' });
    await pagePlain.evaluate((id) => window.depReportOverviewTestApi.selectFunction(id), functionId);
    await sleep(200);
    const hrefWithoutTemplate = await pageLinkHref(pagePlain);
    const settingsVisibleWithout = await pagePlain.evaluate(() => {
      const section = document.getElementById('pageVariantSection');
      return Boolean(section && !section.hidden);
    });
    await pagePlain.close();

    return {
      pageErrors: errors,
      hrefJa,
      hrefCamel,
      settingsVisible,
      hrefJaDetails,
      storedVariant,
      checkedVariant,
      copyText: copyText ? copyText.slice(0, 2000) : null,
      hrefAfterReload,
      hrefEnDefault,
      hrefWithoutTemplate,
      settingsVisibleWithout
    };
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const withPagePath = process.argv[2];
  const withoutPagePath = process.argv[3];
  const functionId = process.argv[4] || 'c_2';
  if (!withPagePath || !withoutPagePath) {
    console.error('usage: node page_link_probe.js <with-page index.html> <without-page index.html> [function id]');
    process.exit(2);
  }
  run(path.resolve(withPagePath), path.resolve(withoutPagePath), functionId)
    .then((result) => {
      console.log('RESULT ' + JSON.stringify(result));
    })
    .catch((err) => {
      console.error('PROBE_ERROR ' + (err && err.stack ? err.stack : String(err)));
      process.exit(1);
    });
}
