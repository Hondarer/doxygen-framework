# Doxygen の @copydoc 活用ガイド

Doxygen で関数のドキュメントを書く際、ほぼ同じ説明を持つ関数が複数ある場合に役立つテクニックをまとめました。  
オーバーロードされた関数や、似た動作をする関数のドキュメント作成を効率化できます。

## 重要な考慮事項

`@copydoc` は Doxygen の仕様としては正しく機能しますが、**VS Code のインテリセンスや LLM エージェントなどの開発支援ツールでは制限があります**。

- VS Code でホバー時に参照先のドキュメントが展開されない
- LLM エージェントが間接参照を正確に理解できない可能性がある

これらの問題の詳細と対応方針については、「[ツール対応の観点からの考慮事項](#ツール対応の観点からの考慮事項)」を参照してください。Doxygen 生成ドキュメントの品質とメンテナンス性を優先する場合は `@copydoc` を、開発時のツールサポートを重視する場合は愚直なドキュメントコピーを検討してください。

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

## ツール対応の観点からの考慮事項

`@copydoc` は Doxygen の仕様としては正しく機能しますが、開発環境やコード支援ツールとの統合を考慮すると、いくつかの制限があります。

### VS Code インテリセンスの制限

VS Code の C/C++ 拡張機能は、ホバー時に Doxygen コメントを表示する機能を提供していますが、**`@copydoc` コマンドはサポートされていません**。

サポートされている Doxygen タグ: `@brief`, `@tparam`, `@param`, `@return`, `@exception`, `@deprecated`, `@note`, `@attention`, `@pre`

`@copydoc` を使用した場合、ホバー時に参照先のドキュメントは展開されず、開発者は元の関数を探してドキュメントを確認する必要があります。この問題は [GitHub Issue #5718](https://github.com/microsoft/vscode-cpptools/issues/5718) で 2020 年から報告されていますが、2025 年時点でも未実装です。

### LLM エージェントの理解度

Claude Code や GitHub Copilot などの LLM ベースのコード支援ツールは、ソースコードを直接読んで理解します。`@copydoc` による間接参照は、LLM が以下の処理を行う必要があるため、理解の妨げになる可能性があります。

- 参照先の関数を特定
- 参照先のドキュメントを取得
- 元のコンテキストと統合

特に大規模なコードベースでは、LLM のコンテキストウィンドウの制限により、参照先のドキュメントが含まれない可能性があります。直接的なドキュメントがその場にある方が、LLM はより正確にコードを理解し、適切な支援を提供できます。

### 推奨される対応方針

プロジェクトの優先事項に応じて、以下のいずれかのアプローチを選択してください。

#### Doxygen 生成ドキュメントを重視する場合

`@copydoc` を使用してドキュメントの重複を避け、メンテナンス性を向上させます。生成された HTML や PDF では正しく展開されます。

#### 開発時のツールサポートを重視する場合

`@copydoc` を使用せず、各関数に完全なドキュメントを記述します。これにより、以下の利点があります。

- VS Code でホバー時に完全なドキュメントが表示される
- LLM エージェントがコンテキストを正確に理解できる
- コードレビュー時に参照先を探す手間が不要

重複するドキュメントのメンテナンスは手間ですが、現代の開発環境では IDE やエディタでの即座のフィードバックが重要です。

## まとめ

`@copydoc` を活用すると、似た関数のドキュメントを効率よく管理できます。基本の説明を共有しつつ、関数ごとの違いだけを上書きすることで、メンテナンス性の高いドキュメントを作成できます。

ただし、VS Code のインテリセンスや LLM エージェントとの統合を考慮すると、**愚直にドキュメントをコピーして各関数に記述する方が、開発者体験の向上につながる**場合があります。プロジェクトの優先事項に応じて、適切なアプローチを選択してください。

参考:

- [Doxygen Manual - Special Commands](https://www.doxygen.nl/manual/commands.html#cmdcopydoc)
- [Add support for doxygen `\copydoc` command · Issue #5718 · microsoft/vscode-cpptools](https://github.com/microsoft/vscode-cpptools/issues/5718)
- [Visual Studio Code C++ Extension July 2020 Update: Doxygen comments and Logpoints](https://devblogs.microsoft.com/cppblog/visual-studio-code-c-extension-july-2020-update-doxygen-comments-and-logpoints/)
