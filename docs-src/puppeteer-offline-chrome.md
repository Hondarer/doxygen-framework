# Puppeteer で利用する Chrome のオフラインインストール方法

Puppeteer でオフライン環境において Chrome を利用するための手順を整理したドキュメントです。

## 概要

Puppeteer は Node.js 上で動作するヘッドレスブラウザ自動化ツールです。通常、`puppeteer` パッケージをインストールすると Chrome for Testing が自動的にダウンロードされますが、オフライン環境ではこの自動ダウンロードが利用できません。

本ドキュメントでは、オフライン環境で Puppeteer を利用するための複数のアプローチを説明します。

## Puppeteer パッケージの種類

Puppeteer には 2 種類のパッケージがあります。

### puppeteer (フルパッケージ)

```bash
npm i puppeteer
```

インストール時に Chrome for Testing (約 170MB macOS、約 282MB Linux、約 280MB Windows) と chrome-headless-shell バイナリを自動的にダウンロードします。

### puppeteer-core (ライブラリのみ)

```bash
npm i puppeteer-core
```

ブラウザをダウンロードせず、ライブラリのみをインストールします。既存の Chrome または Chromium を使用する場合に適しています。

## オフラインインストールの方法

### 方法 1: @puppeteer/browsers CLI ツールを使用

`@puppeteer/browsers` CLI ツールを使用して、事前に Chrome for Testing をダウンロードする方法です。

#### 最新の安定版をダウンロード

```bash
npx @puppeteer/browsers install chrome@stable
```

#### 特定のバージョンをダウンロード

```bash
npx @puppeteer/browsers install chrome@116.0.5793.0
```

#### マイルストーンの最新版をダウンロード

```bash
npx @puppeteer/browsers install chrome@117
```

#### ダウンロード先

Puppeteer v19.0.0 以降、ブラウザは `$HOME/.cache/puppeteer` にグローバルにキャッシュされます。このキャッシュディレクトリは複数のインストール間で共有されるため、一度ダウンロードすればオフライン環境で再利用できます。

### 方法 2: 環境変数を使用したスキップとキャッシュ管理

#### Chrome の自動ダウンロードをスキップ

```bash
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
npm install puppeteer
```

#### キャッシュディレクトリのカスタマイズ

```bash
export PUPPETEER_CACHE_DIR=/path/to/custom/cache
npm install puppeteer
```

デフォルトのキャッシュディレクトリは `os.homedir()/.cache/puppeteer` です。

#### その他の環境変数

- `PUPPETEER_TMP_DIR`: Puppeteer が一時ファイルを作成するディレクトリを指定
- `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`: ブラウザのダウンロードと実行時に使用する HTTP プロキシ設定

### 方法 3: 設定ファイルによる管理

プロジェクトのルートディレクトリに `.puppeteerrc.cjs` を作成し、キャッシュディレクトリを指定します。

```javascript
const { join } = require('path');

module.exports = {
  cacheDirectory: join(__dirname, '.cache', 'puppeteer'),
};
```

**注意**: Puppeteer の設定ファイルと環境変数は `puppeteer-core` では無視されます。

### 方法 4: Chrome for Testing を手動でダウンロード

Chrome for Testing は Google が提供する自動化テスト専用の Chrome ビルドです。

#### JSON API エンドポイント

Chrome for Testing の各バージョンは JSON API から取得できます。

```bash
# 最新の安定版バージョンを取得
curl https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE

# すべての履歴バージョンとダウンロード URL を取得
curl https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json

# ビルドごとの最新パッチバージョンとダウンロード URL を取得
curl https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json
```

#### 直接ダウンロード URL パターン

Chrome for Testing バイナリは以下の URL パターンで直接ダウンロードできます。

```text
https://storage.googleapis.com/chrome-for-testing-public/{VERSION}/{PLATFORM}/{BINARY}-{PLATFORM}.zip
```

##### 対応プラットフォーム

- `linux64`
- `mac-arm64`
- `mac-x64`
- `win32`
- `win64`

##### ダウンロード例

```bash
# Linux 64bit 版 Chrome 118.0.5962.0 をダウンロード
curl -O https://storage.googleapis.com/chrome-for-testing-public/118.0.5962.0/linux64/chrome-linux64.zip

# ダウンロードしたファイルを解凍
unzip chrome-linux64.zip
```

## オフライン環境での使用方法

### executablePath を指定して起動

手動でダウンロードした Chrome や既存の Chrome を使用する場合は、`executablePath` オプションで実行パスを指定します。

```javascript
const puppeteer = require('puppeteer');

const browser = await puppeteer.launch({
  executablePath: '/path/to/chrome/executable',
});

const page = await browser.newPage();
await page.goto('https://example.com');
await browser.close();
```

### キャッシュディレクトリから自動検出

Puppeteer v19.0.0 以降、ブラウザは `~/.cache/puppeteer` から自動的に検出されます。事前にこのディレクトリに Chrome をダウンロードしておけば、`executablePath` を指定せずに使用できます。

```javascript
const puppeteer = require('puppeteer');

// キャッシュディレクトリから自動的に Chrome を検出
const browser = await puppeteer.launch();
const page = await browser.newPage();
await page.goto('https://example.com');
await browser.close();
```

## オフラインインストールの推奨フロー

以下の手順で、オンライン環境で Chrome をダウンロードし、オフライン環境で使用することを推奨します。

### オンライン環境での準備

```bash
# 1. プロジェクトディレクトリに移動
cd /path/to/your/project

# 2. Puppeteer をインストール (Chrome の自動ダウンロードをスキップ)
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
npm install puppeteer

# 3. プロジェクト内にキャッシュディレクトリを作成
mkdir -p .cache/puppeteer

# 4. Chrome for Testing をダウンロード (カスタムキャッシュディレクトリを指定)
export PUPPETEER_CACHE_DIR=$(pwd)/.cache/puppeteer
npx @puppeteer/browsers install chrome@stable

# 5. プロジェクト全体をオフライン環境に転送
# (node_modules と .cache/puppeteer を含む)
```

### オフライン環境での使用

```bash
# 1. プロジェクトディレクトリに移動
cd /path/to/your/project

# 2. キャッシュディレクトリを環境変数に設定 (必要に応じて)
export PUPPETEER_CACHE_DIR=$(pwd)/.cache/puppeteer

# 3. Puppeteer を使用したスクリプトを実行
node your-script.js
```

または、`.puppeteerrc.cjs` を使用してキャッシュディレクトリを指定します。

```javascript
// .puppeteerrc.cjs
const { join } = require('path');

module.exports = {
  cacheDirectory: join(__dirname, '.cache', 'puppeteer'),
};
```

## バージョン互換性

各 Puppeteer バージョンは単一の Chrome バージョンに対応しています。互換性を確保するため、Puppeteer がインストールされているプロジェクトで以下のコマンドを実行することを推奨します。

```bash
npx puppeteer browsers install chrome
```

このコマンドは、インストールされている Puppeteer バージョンに対応する Chrome バージョンを自動的にダウンロードします。

## トラブルシューティング

### Chrome が見つからないエラー

```text
Error: Could not find Chrome
```

このエラーが発生した場合、以下を確認してください。

- Chrome がキャッシュディレクトリにダウンロードされているか
- `PUPPETEER_CACHE_DIR` 環境変数が正しく設定されているか
- `.puppeteerrc.cjs` の `cacheDirectory` が正しいパスを指しているか
- `executablePath` を明示的に指定しているか

### ネットワークエラー

オンライン環境でダウンロード時にネットワークエラーが発生する場合、プロキシ設定を確認してください。

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
npx @puppeteer/browsers install chrome@stable
```

## 参考資料

- [Puppeteer Installation Guide](https://pptr.dev/guides/installation)
- [Puppeteer Configuration Guide](https://pptr.dev/guides/configuration)
- [@puppeteer/browsers NPM Package](https://www.npmjs.com/package/@puppeteer/browsers)
- [Chrome for Testing: reliable downloads for browser automation](https://developer.chrome.com/blog/chrome-for-testing)
- [Chrome for Testing JSON API](https://github.com/GoogleChromeLabs/chrome-for-testing)
- [Stack Overflow: Use puppeteer-core and installing chromium manually](https://stackoverflow.com/questions/56081642/use-puppeteer-core-and-installing-chromium-manually)
