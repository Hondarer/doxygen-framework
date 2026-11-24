# Doxygen 生成処理の保守と検証

## 出力変換を変更する場合

テンプレート、`postprocess`、`templates/*.py` の出力変換を変更する場合は、対象の変更前生成 Markdown を退避します。  
同じ入力から再生成した結果を `diff -ru` などで比較し、意図した差分だけであることを確認します。  
生成物は Git 管理対象外のため、`git diff` だけでは比較できません。

テンプレート変更が利用側の `make_doxy.stamp` のシグネチャに含まれない場合は、対象 app のスタンプを除いて再生成します。  
ワークスペースと対象 app の絶対パスを確認し、対象外のスタンプを削除しないでください。  
この場合、`make clean` は不要です。  
実行方法は [makefile の利用方法](makefile-usage.md) を参照してください。

## Python の日本語出力

Windows で日本語を出力する処理を追加する場合は、既存スクリプトの stdout / stderr の UTF-8 設定に合わせます。  
出力の文字化けが発生した場合は実行環境のエンコーディングも確認します。

```python
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
```

## 文書の表記と図

本文の文末を全角コロンで終わらせず、括弧とコロンは半角を使います。  
日本語と英単語の間には半角スペースを置き、コード ブロックには `text` などの形式を明示します。  
`Markdown` の表記を優先します。

図を追加または変更する場合は Mermaid を基本とします。  
Markdown の図には、閉じコード フェンスの後に空行を挟んで `Figure: キャプション` を記載します。記法は [コード ブロックと図のキャプション](../../docsfw/docs/codeblock-caption.md) を参照してください。  
フロー説明はフローチャート、シーケンス性が主題の場合はシーケンス図を使います。

PlantUML は互換の記法です。PlantUML を使う場合は、`@startuml` と `caption` に同じタイトル文字列を記載し、`title` は使用しません。  
フロー説明はアクティビティ図、シーケンス性が主題の場合はシーケンス図を使います。

### Doxygen コメントの図

Doxygen コメントへ記述する図は、次の規範に従います。

- Mermaid の図は `@mermaid "キャプション"` 〜 `@endmermaid` で記述します。キャプションは `@mermaid` の直後に指定します。`@mermaid{caption="..."}` の形式は、波括弧を含む全体がキャプション文字列になるため使用しません。
- PlantUML の図は `@startuml` 〜 `@enduml` で記述します。
- 図ブロックは、エディターのプレビューを利用できるよう、行頭の `*` を置かずに記述できます。この場合、開始行と終了行はコメント本文と同じ桁に置き、図の本文は開始行より浅い位置に置きません。コメント本文の桁は、`*` を持つ行で `*` と後続の空白の次に来る文字の位置です。

```c
    /**
     *  @brief          関数の説明です。
     *
        @mermaid "処理の流れ"
            sequenceDiagram
                A->>B: 要求
        @endmermaid
     *
     *  @par            スレッド セーフ
     *  本関数はスレッド セーフです。
     */
```

開始行がコメント本文より浅いと、Doxygen は警告を出さずに前後の `@par` の節を字下げコード ブロックとして出力します。開始行がコメント本文より深いと、図ブロック自体がコード ブロックになります。  
この字下げの違反は、[Doxygen コメント字下げレベル チェック・修正コマンド](check-doxygen-indent.md) (`check-doxygen-indent.py`) で検出できます。検出だけを行い、図ブロックは書き換えません。

### コード スパン末尾のバックスラッシュと内部コマンド iskip / endiskip

Doxygen 1.12.0 以降では、`\verbatim`、`<code>`、バッククォートのコード スパンなど、字面どおりの本文を含む要素を処理する際、字下げ判定用の空白評価を一時停止するために内部コマンド `\iskip` と `\endiskip` を挿入します (`see: https://doxygen.github.io/doxygen-docs/d6/d57/pg_cmds_int.html`)。

コード スパンの末尾が奇数個のバックスラッシュで終わると、Doxygen が直後へ挿入する `\endiskip` の先頭の `\` と対になり、`\\` と文字列 `endiskip` が XML と Doxybook2 の生成 Markdown へ漏れます。  
Doxygen 1.18.0 に最小入力を与えた検証 (手順 1) の結果は次のとおりです。

| 事例 | コメントの記載 | XML の `<detaileddescription>` | 結果 |
| --- | --- | --- | --- |
| C1 | `` `\\?\` `` | `\\?\\endiskip` | `endiskip` が漏れる |
| C2 | `` `\\.\` `` | `\\.\\endiskip` | `endiskip` が漏れる |
| C3 | `` `\\?\x` `` | `\\?\x` | 漏れない |
| C4 | `` `a\` `` | `a\\endiskip` | `endiskip` が漏れる |
| C5 | `` `\\` `` | `\\` | 漏れない (末尾の `\` が偶数個) |
| C6 | `` `/` と `\\` `` | `/` と `\\` | 漏れない (末尾の `\` が偶数個) |
| C7 | `<code>\\?\</code>` | `\?&lt;/code&gt;` | 漏れないが `</code>` 不足の警告が出て元の記載を保てない |
| C8 | `@c \\?\` | `<computeroutput>\</computeroutput>?\` | 漏れないが先頭の `\` だけがコードになり元の記載を保てない |

Table: コード スパン末尾のバックスラッシュに対する Doxygen 1.18.0 の検証結果

この結果を踏まえ、Doxygen コメントではコード スパンの末尾を奇数個のバックスラッシュにしないでください。  
拡張パス接頭辞などを示す場合は、`` `\\?\C:\...` `` や `` `\\.\...` `` のように後ろへ文字を続けて記述します。`check-doxygen-code-span-backslash.py` で再発を検出できます。

## 既存の検査コマンド一覧

Doxygen コメントの記述規約を確認するために、次の検査コマンドを `framework/doxyfw/bin/` に配置しています。

| コマンド | 検査内容 | 文書 |
| --- | --- | --- |
| `check-doxygen-indent.py` | コメント ブロックと図ブロックの字下げ統一 | [Doxygen コメント字下げレベル チェック・修正コマンド](check-doxygen-indent.md) |
| `check-doxygen-separators.py` | `@file` 以外の Doxygen コメントのセパレータ行検出 | - |
| `check-doxygen-code-span-backslash.py` | 末尾のバックスラッシュが奇数個のコード スパン検出 | [Doxygen コード スパン末尾バックスラッシュ検査コマンド](check-doxygen-code-span-backslash.md) |

Table: `framework/doxyfw/bin/` の検査コマンド一覧
