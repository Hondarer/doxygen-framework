# Doxyfile で複数の個別ディレクトリを対象に指定する方法

Doxygen の `Doxyfile` で複数の個別ディレクトリを対象に指定する方法を説明します。

## INPUT 設定での複数ディレクトリ指定

最も一般的な方法は、`INPUT` 設定で複数のディレクトリをスペース区切りで指定することです。

```text
INPUT = /path/to/dir1 /path/to/dir2 /path/to/dir3
```

または、改行とバックスラッシュを使用して見やすく記述することもできます。

```text
INPUT = /path/to/dir1 \
        /path/to/dir2 \
        /path/to/dir3
```

## 相対パスでの指定

相対パスでも指定可能です。

```text
INPUT = src include examples
```

## ワイルドカードの使用

ワイルドカードパターンも使用できます。

```text
INPUT = src/* libs/*/include
```

## RECURSIVE 設定との組み合わせ

`RECURSIVE` を `YES `に設定すると、指定したディレクトリのサブディレクトリも再帰的に処理されます。

```text
INPUT = dir1 dir2 dir3
RECURSIVE = YES
```

## EXCLUDE 設定での除外

特定のディレクトリやファイルを除外したい場合は `EXCLUDE` 設定を使用します。

```
INPUT = src libs
EXCLUDE = src/deprecated libs/external
RECURSIVE = YES
```

## FILE_PATTERNS 設定

特定の拡張子のファイルのみを対象にしたい場合は以下のように設定します。

```text
INPUT = src include
FILE_PATTERNS = *.cpp *.h *.hpp
RECURSIVE = YES
```

これらの方法により、プロジェクトの構造に応じて柔軟にドキュメント生成の対象を指定できます。
