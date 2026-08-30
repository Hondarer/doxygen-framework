'use strict';

const path = require('path');

function resolvePuppeteer() {
  const candidates = [];
  if (process.env.DOXYFW_TEST_PUPPETEER) {
    candidates.push(process.env.DOXYFW_TEST_PUPPETEER);
  }
  candidates.push('puppeteer');
  candidates.push(path.resolve(__dirname, '../../docsfw/bin/node_modules/puppeteer'));
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
