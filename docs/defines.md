# define 値の展開について

doxygen の `PREDEFINED` 設定について詳しく説明します。

## PREDEFINED とは

`PREDEFINED` は、doxygen の前処理段階で事前に定義されるマクロを指定する設定項目です。これにより、条件付きコンパイル (`#ifdef`、`#if` など) の評価を制御できます。

## 設定方法

### 設定ファイル (Doxyfile) での記述

```text
PREDEFINED = MACRO1 \
             MACRO2=value \
             MACRO3="string value" \
             DEBUG \
             PLATFORM_LINUX
```

## 使用例

### 単純なマクロ定義

```text
PREDEFINED = DEBUG
```

これは以下と同等:

```cpp
#define DEBUG
```

### 値付きマクロ定義

```text
PREDEFINED = VERSION=2 \
             MAX_SIZE=1024
```

これは以下と同等:

```cpp
#define VERSION 2
#define MAX_SIZE 1024
```

### 文字列値マクロ

```text
PREDEFINED = COMPILER="GCC" \
             PLATFORM="Linux"
```

### 複数条件の定義

```text
PREDEFINED = FEATURE_A \
             FEATURE_B \
             HAVE_OPENSSL \
             _WIN32 \
             __cplusplus
```

## 実際のコード例

### ソースコード

```cpp
/**
 * @brief 計算関数
 */
class Calculator {
public:
    int add(int a, int b);
    
#ifdef ADVANCED_FEATURES
    /**
     * @brief 高度な計算機能
     */
    double advanced_calc(double x, double y);
#endif

#ifdef DEBUG
    /**
     * @brief デバッグ用関数
     */
    void debug_print();
#endif

#if VERSION >= 2
    /**
     * @brief バージョン2 以降の機能
     */
    void new_feature();
#endif
};
```

### 設定例: すべての機能を文書化

```text
PREDEFINED = ADVANCED_FEATURES \
             DEBUG \
             VERSION=2
```

### 設定例: 本番環境向け文書化

```text
PREDEFINED = ADVANCED_FEATURES \
             VERSION=2
```

### 設定例: デバッグ版文書化

```text
PREDEFINED = DEBUG \
             VERSION=1
```

## よく使用されるマクロ

### プラットフォーム固有

```text
PREDEFINED = _WIN32 \
             __linux__ \
             __APPLE__ \
             __cplusplus
```

### コンパイラ固有

```text
PREDEFINED = __GNUC__ \
             _MSC_VER \
             __clang__
```

### 一般的な機能フラグ

```text
PREDEFINED = HAVE_OPENSSL \
             ENABLE_THREADING \
             USE_BOOST \
             NDEBUG
```

## 高度な使用法

### 条件付きマクロ展開

```text
PREDEFINED = DOXYGEN_SHOULD_SKIP_THIS= \
             API_EXPORT= \
             DEPRECATED=
```

### 関数修飾子の除去

```cpp
// ソースコード
API_EXPORT DEPRECATED int old_function();
```

```text
PREDEFINED = API_EXPORT= \
             DEPRECATED=
```

結果: `int old_function();` として文書化

### プラットフォーム別 API

```cpp
#ifdef _WIN32
    HANDLE create_file(const char* name);
#else
    int create_file(const char* name);
#endif
```

```text
PREDEFINED = _WIN32
```

または

```text
PREDEFINED = __linux__
```

## 注意点とベストプラクティス

### 長い行の分割

```text
PREDEFINED = MACRO1 \
             MACRO2 \
             MACRO3
```

### 特殊文字のエスケープ

```text
PREDEFINED = STRING_MACRO="\"Hello World\""
```

### 空値の定義

```text
PREDEFINED = EMPTY_MACRO=
```

### 条件の組み合わせ

```text
PREDEFINED = FEATURE_A \
             FEATURE_B \
             COMBINED_FEATURES
```

## トラブルシューティング

### よくある問題

1. **マクロが認識されない**
   - `ENABLE_PREPROCESSING = YES` を確認
   - マクロ名のスペルチェック

2. **値が正しく設定されない**
   - 引用符の使用を確認
   - エスケープ文字の確認

3. **複雑な条件が評価されない**
   - `ENABLE_PREPROCESSING = NO` を検討
   - より単純な条件に分割

### デバッグ方法

```bash
# プリプロセッサの動作確認
doxygen -d Preprocessor
```
