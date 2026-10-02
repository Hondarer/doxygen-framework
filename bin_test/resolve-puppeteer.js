'use strict';

const { execFileSync } = require('child_process');
const path = require('path');

// docsfw は Node.js モジュールをグローバルの導入先からも採用する。
// require('puppeteer') はグローバルの導入先を探索しないため、docsfw と同じ解決処理で場所を得る。
// see: ../../docsfw/docs/node-components.md
function resolveWithDocsfw() {
  const resolver = path.resolve(__dirname, '../../docsfw/bin_internal/resolve-node-components.js');
  try {
    const output = execFileSync(process.execPath, [resolver], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    return JSON.parse(output).paths.puppeteer || null;
  } catch (err) {
    return null;
  }
}

function resolvePuppeteer() {
  const candidates = [];
  if (process.env.DOXYFW_TEST_PUPPETEER) {
    candidates.push(process.env.DOXYFW_TEST_PUPPETEER);
  }
  candidates.push('puppeteer');
  const docsfwPuppeteer = resolveWithDocsfw();
  if (docsfwPuppeteer) {
    candidates.push(docsfwPuppeteer);
  }
  candidates.push(path.resolve(__dirname, '../../docsfw/bin_internal/node_modules/puppeteer'));
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch (err) {
      // 次の候補へ
    }
  }
  throw new Error('puppeteer not found (set DOXYFW_TEST_PUPPETEER)');
}

module.exports = { resolvePuppeteer };
