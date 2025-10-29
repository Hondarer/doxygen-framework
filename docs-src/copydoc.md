# Doxygen の @copydoc 活用ガイド

Doxygen で関数のドキュメントを書く際、ほぼ同じ説明を持つ関数が複数ある場合に役立つテクニックをまとめました。  
オーバーロードされた関数や、似た動作をする関数のドキュメント作成を効率化できます。

## 基本的な使い方

ある関数の説明を別の関数で再利用するには、`@copydoc` コマンドを使います。  
片方の関数に完全な説明を書いておき、もう片方では `@copydoc` で参照するだけで済みます。

```{.cpp caption="example.cpp"}
/**
 * @brief データを処理する
 * @param data 入力データ
 * @return 処理結果
 * 
 * この関数は入力データを解析し、
 * 正規化された結果を返します。
 */
int processData(const char* data);

/**
 * @copydoc processData(const char*)
 */
int processData(const std::string& data);
```

`@copydoc` の後ろには、コピー元の関数のシグネチャを指定します。オーバーロードがある場合は引数の型まで書くと、関数を正確に特定できます。

部分的にコピーしたい場合は `@copybrief` (概要のみ) や `@copydetails` (詳細のみ) も使えますが、完全に同一な説明なら `@copydoc` が最も簡潔です。

## 項目のオーバーライド

`@copydoc` の後に追加のコマンドを書くと、特定の項目だけを上書きできます。ベースの説明を再利用しつつ、関数固有の情報を追加したい場合に便利です。

```{.cpp caption="example.cpp"}
/**
 * @brief データを処理する
 * @param data 入力データ
 * @param flags 処理フラグ
 * @return 処理結果
 * 
 * この関数は入力データを解析し、
 * 正規化された結果を返します。
 */
int processData(const char* data, int flags);

/**
 * @copydoc processData(const char*, int)
 * @param data std::string 形式の入力データ
 * 
 * @note この版では UTF-8 エンコーディングを想定しています
 */
int processData(const std::string& data, int flags);
```

この例では、2 番目の関数は `@copydoc` でベースの説明をコピーしつつ、`@param data` の説明だけを独自のものに置き換え、さらに `@note` を追加しています。

上書きできる主な項目は次のとおりです。

- `@param` で特定のパラメータの説明を変更
- `@return` で戻り値の説明を変更
- `@note`, `@warning` などの追加情報を付与

`@brief` や本文の詳細説明は `@copydoc` でコピーされたものがそのまま使われます。完全に別の説明にしたい場合は、`@copydoc` を使わず最初から書いた方が明確です。

## グループへの所属

`@copydoc` の後に `@ingroup` を追加すれば、その関数だけを特定のグループに所属させられます。

```{.cpp caption="example.cpp"}
/**
 * @brief データを処理する
 * @param data 入力データ
 * @return 処理結果
 */
int processData(const char* data);

/**
 * @copydoc processData(const char*)
 * @ingroup string_utilities
 */
int processData(const std::string& data);
```

この例では、2 番目の `processData` 関数だけが `string_utilities` グループに含まれます。1 番目の関数はどのグループにも属しません。

`@ingroup` は構造的な情報なので、`@copydoc` でコピーされる説明内容とは独立して扱われます。そのため、コピー先だけに追加しても問題なく動作します。

逆に、コピー元に `@ingroup` があってもコピー先には引き継がれないので、必要なら明示的に書く必要があります。

## まとめ

`@copydoc` を活用すると、似た関数のドキュメントを効率よく管理できます。基本の説明を共有しつつ、関数ごとの違いだけを上書きすることで、メンテナンス性の高いドキュメントを作成できます。

参考: [Doxygen Manual - Special Commands](https://www.doxygen.nl/manual/commands.html#cmdcopydoc)
