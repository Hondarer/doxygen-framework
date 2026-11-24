# Doxygen コード スパン末尾バックスラッシュ検査コマンド

`check-doxygen-code-span-backslash.py` は、Doxygen コメント内のインライン コード スパン (バッククォートで囲んだ範囲) の末尾が奇数個のバックスラッシュで終わる箇所を検出し、行番号つきで報告するコマンドです。

## 背景

Doxygen 1.12.0 以降では、コード スパンなどの字面どおりの本文を含む要素を処理するとき、開始位置と終了位置へ内部コマンド `\iskip` と `\endiskip` を挿入します (`see: https://doxygen.github.io/doxygen-docs/d6/d57/pg_cmds_int.html`)。

コード スパンの末尾に奇数個のバックスラッシュがあると、Doxygen が直後へ挿入する `\endiskip` の先頭の `\` と結び付き、`\\` (エスケープされたバックスラッシュ) と文字列 `endiskip` として XML や Doxybook2 の Markdown へ出力されます。

- 奇数個の例: `` `\\?\` ``、`` `\\.\` ``、`` `a\` `` -> `endiskip` が漏れる
- 偶数個の例: `` `\\` `` -> `\\` だけが残り、`\endiskip` はコマンドとして消費される
- バックスラッシュ以外の文字で終わる例: `` `\\?\C:\...` ``、`` `\\?\x` `` -> `endiskip` は漏れない

## 使用方法

```bash
# 単一ファイルを検査
python3 framework/doxyfw/bin/check-doxygen-code-span-backslash.py app/cplat/prod/include/cplat/crt/sys/stat.h

# 複数のディレクトリを検査
python3 framework/doxyfw/bin/check-doxygen-code-span-backslash.py app/cplat/prod
```

問題が見つからない場合の出力例:

```text
OK: 120 ファイルを検査し、末尾のバックスラッシュが奇数個のコード スパンはありません。
```

問題が見つかった場合の出力例:

```text
app/cplat/prod/include/cplat/crt/sys/stat.h:129: 検出: コード スパンの末尾のバックスラッシュが奇数個です (`\\?\`)
NG: 1 件の該当コード スパンを検出しました。
```

## 終了コード

| 終了コード | 意味 |
| --- | --- |
| `0` | 該当するコード スパンなし (または対象ファイルなし) |
| `1` | 1 件以上の該当コード スパンを検出、または指定パスが存在しない |

Table: `check-doxygen-code-span-backslash.py` の終了コード

## 対処方法

検出されたコード スパンは、`` `\\?\C:\...` `` や `` `\\.\...` `` のように、末尾のバックスラッシュの後ろへ文字を続けて、バックスラッシュで終わらない例へ直してください。  
`<code>\\?\</code>` は閉じタグ不足の警告が出て元の文字列が崩れ、`@c \\?\` は先頭の `\` だけがコードになるため使いません。

## 関連ドキュメント

- [生成処理の保守と検証](maintenance-verification.md)
- [Doxygen 記法の要点](cheatsheet.md)
- [コマンド一覧](commands.md)
