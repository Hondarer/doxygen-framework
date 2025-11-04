# Doxygen における画像の仕様

## Markdown 画像参照の対応

Doxygen は `![alt](path_to_png)` 形式の Markdown 画像参照を Pages として処理できます。

`.md` または `.markdown` 拡張子のファイルは自動的にページとして変換され、その中の Markdown 画像構文もサポートされます。

## IMAGE_PATH の設定

画像を正しく表示するには、Doxyfile で `IMAGE_PATH` の設定が必要です。

```{.doxyfile caption="基本設定"}
IMAGE_PATH = path/to/your/images
```

### 複数パスの指定

```{.doxyfile caption="複数のディレクトリを指定"}
IMAGE_PATH = docs/images \
             examples/images \
             ../shared/images
```

IMAGE_PATH は以下の形式で指定できます。

- Doxygen を実行する場所からの相対パス
- 絶対パス

## 画像検索の仕組み

Doxygen の画像検索には特殊な仕組みがあります。

- 画像が見つかるには、ファイル名とパスが実際のフルパスの一部と一致する必要がある
- Markdown ファイルからの相対パスではなく、IMAGE_PATH で指定したディレクトリから画像を探す

### 具体例

```text
/project/docs/page.md
/project/docs/images/screenshot.png
```

この場合の設定は次のようになります。

```{.doxyfile caption="Doxyfile"}
IMAGE_PATH = docs/images
```

Markdown 内では次のように参照できます。

```{.markdown caption="page.md"}
![スクリーンショット](screenshot.png)
```

## ワイルドカードと再帰探索

**重要:** IMAGE_PATH ではワイルドカード記法は使用できません。

- `*/images` のような記法は使えない
- 再帰的な探索オプションも存在しない

すべてのパスを個別に列挙する必要があります。

```{.doxyfile caption="複数の images ディレクトリを列挙"}
IMAGE_PATH = docs/module1/images \
             docs/module2/images \
             docs/module3/images \
             examples/images
```

## 過去の問題と現状

過去には以下の問題がありましたが、現在は修正されています。

- Markdown 構文 `![caption](filename)` を使った場合に画像ファイルがコピーされない問題 → Doxygen 1.8.1 で修正済み

ただし、相対パスを使った場合に画像が出力ディレクトリにコピーされず、パスの変換だけが行われる問題が報告されることもあります。

## 推奨される使い方

確実に動作させるには次のいずれかを選択してください。

### 方法 1: Markdown 構文を使用

IMAGE_PATH に画像ディレクトリを設定し、ファイル名のみで参照します。

```{.doxyfile caption="Doxyfile"}
IMAGE_PATH = docs/images
```

```{.markdown caption="page.md"}
![ロゴ画像](logo.png)
```

### 方法 2: Doxygen コマンドを使用（より確実）

```text
\image html logo.png "ロゴ画像"
```

## 参考情報

- [Doxygen Markdown サポート](https://www.doxygen.nl/manual/markdown.html)
- [Doxygen 設定リファレンス](https://www.doxygen.nl/manual/config.html)
