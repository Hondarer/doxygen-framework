# Doxygen における画像の仕様

Doxygen 1.14.0 を使用した実験、および Doxygen ソースコード (`src/doxygen.cpp`, `src/docparser.cpp`, `src/docnode.cpp`) の調査に基づく仕様をまとめます。

## IMAGE_PATH の設定

画像を HTML 出力に含めるには、Doxyfile で `IMAGE_PATH` を設定します。

```text
IMAGE_PATH = path/to/dir
```

Doxygen を実行するディレクトリからの相対パス、または絶対パスで指定します。

### 再帰探索

`RECURSIVE = YES` が設定されている場合、`IMAGE_PATH` で指定したディレクトリは再帰的に検索されます。画像が深いサブディレクトリにある場合でも、共通の親ディレクトリを一つ指定するだけで十分です。

```text
# images/calc-flow.png も images/sub/diagram.png も対象になる
IMAGE_PATH = ./src
RECURSIVE  = YES
```

`INPUT` と同じディレクトリを `IMAGE_PATH` に指定するのが確実です。

## コピーされる画像の条件

**Markdown から参照された画像のみが HTML 出力ディレクトリにコピーされます。**

`IMAGE_PATH` に画像ファイルを配置しても、Markdown から参照されていなければコピーされません。

| 状況 | コピーされるか |
|---|---|
| Markdown で `![...](filename.png)` と参照している | ✅ コピーされる |
| `IMAGE_PATH` に置いているが Markdown から未参照 | ❌ コピーされない |

### コピー対象の拡張子

**Doxygen のソースコードに拡張子フィルタは存在しません。**

`src/doxygen.cpp` の `adjustConfiguration()` では、IMAGE_PATH のディレクトリを `readFileOrDirectory()` でスキャンする際に `patList=nullptr` を渡しており、すべてのファイルが `imageNameLinkedMap` に登録されます。Markdown から参照されたファイルをコピーする `findAndCopyImage()` にも拡張子チェックはありません。

```text
(Doxygen ソースコード: src/doxygen.cpp / adjustConfiguration())
readFileOrDirectory(path,
    Doxygen::imageNameLinkedMap,
    nullptr,   // exclSet
    nullptr,   // patList  ← 拡張子フィルタなし
    ...
```

つまり、Markdown から参照したファイルは拡張子に関係なくコピーされます。

HTML での表示はブラウザに依存します。公式ドキュメントの `\image` コマンドには次の記載があります。

> "The image format for HTML is limited to what your browser supports."
> "Doxygen does not check if the image is in the correct format."
>
> — [Doxygen: Special Commands — \image](https://www.doxygen.nl/manual/commands.html#cmdimage)

HTML 出力での実用的な対応形式は以下の通りです。

| 拡張子 | HTML 出力での扱い | ブラウザでの表示 |
|---|---|---|
| `.png` | `<img>` タグ | ✅ |
| `.jpg` / `.jpeg` | `<img>` タグ | ✅ |
| `.gif` | `<img>` タグ | ✅ |
| `.webp` | `<img>` タグ | ✅ (主要ブラウザ) |
| `.svg` | `<object type="image/svg+xml">` タグ | ✅ |
| その他 | `<img>` タグ | ブラウザ依存 |

`.svg` のみ、Doxygen ソースコード内の `DocImage::isSVG()` (`src/docnode.cpp`) が拡張子を判定して `<object>` タグに切り替えます。

```html
<!-- SVG の場合 -->
<object type="image/svg+xml" data="sample.svg" style="pointer-events: none;"></object>

<!-- それ以外の場合 -->
<img src="sample.png" alt=""/>
```

## Markdown からの参照記法と VS Code プレビューとの共存

VS Code のプレビューでは、Markdown ファイルから画像を相対パスで参照する必要があります。

```markdown
![キャプション](images/diagram.png)
```

この記法を使った場合の Doxygen の動作を確認します。

- Doxygen は `IMAGE_PATH` を再帰的に検索してファイル名 (`diagram.png`) のみで照合する
- 見つかった画像を HTML 出力ルートにフラットにコピーする
- HTML には `<img src="diagram.png">` とファイル名のみを出力する (パスが置き換えられる)

```text
Markdown の記述:   images/diagram.png
↓
HTML の出力:       <img src="diagram.png">
コピー先:          docs/doxygen/diagram.png (フラット)
```

この置き換えにより、VS Code プレビューと Doxygen HTML の両方で画像が表示されます。

| 環境 | パスの解決 | 結果 |
|---|---|---|
| VS Code プレビュー | `images/diagram.png` (相対パス) | ✅ 表示される |
| Doxygen HTML | `diagram.png` (ファイル名のみ) | ✅ 表示される |

### 注意点

異なるディレクトリに同名の画像ファイルが存在する場合、Doxygen は以下の警告を出し、どちらか一方のみをコピーします (ファイル名のユニーク化は行われません)。

```text
warning: image file name 'images/duplicate.png' is ambiguous.
  /path/to/dir1/images/duplicate.png
  /path/to/dir2/images/duplicate.png
```

ドキュメントセットが意図した出力になるためには、画像ファイル名がプロジェクト全体で一意であることが必要です。  
本フレームワークでは、同名画像ファイルの警告を検出した場合、`make doxy` にて失敗します。これにより、CI/CD で問題を発見、対処できます。
