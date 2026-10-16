# 関数リソース記載ガイドライン (ドラフト)

関数が使用・操作するリソース (ファイル、テーブル、API など) を機械可読フォーマットで記載するためのガイドラインです。

## 概要

関数が依存するリソースや操作対象を明示的に文書化することで、以下のメリットを得られます。

- 影響範囲分析の自動化
- リソース依存関係の可視化
- CRUD マトリクスの自動生成
- コードレビューの効率化
- セキュリティ監査の支援

## 参考事例

### 業界標準フォーマット

- **OpenAPI/Swagger**: REST API のリソースと操作を JSON/YAML で記述 ([参考](https://stoplight.io/api-documentation-guide))
- **Dataform**: テーブル依存関係を config ブロックや ref 関数で宣言 ([参考](https://docs.cloud.google.com/dataform/docs/dependencies))
- **ARM Template**: Azure リソースの dependsOn プロパティで依存関係を管理 ([参考](https://techcommunity.microsoft.com/blog/appsonazureblog/dive-into-arm-template-from-a-function-app/4234337))

### 機械可読ドキュメント

API ドキュメントの自動化では、構造化された機械可読フォーマット (JSON, YAML, XML) が重要です ([参考](https://idratherbewriting.com/learnapidoc/nativelibraryapis_doxygen.html))。

## 推奨フォーマット

### 基本構文

Doxygen の `@par` タグを使用し、YAML 形式でリソース情報を記述します。

```c
/**
 *******************************************************************************
 *  @brief          ユーザー情報をデータベースから取得します。
 *  @param[in]      userId ユーザー ID
 *  @param[out]     userInfo ユーザー情報を格納する構造体
 *  @return         成功時は 0、失敗時は -1
 *
 *  @par Resources
 *  ```yaml
 *  - type: table
 *    name: users
 *    operations: [read]
 *    description: ユーザーマスタテーブル
 *
 *  - type: table
 *    name: user_profiles
 *    operations: [read]
 *    description: ユーザープロファイルテーブル
 *
 *  - type: file
 *    name: /var/log/app.log
 *    operations: [create, update]
 *    description: アプリケーションログファイル
 *  ```
 *******************************************************************************
 */
int getUserInfo(int userId, UserInfo *userInfo);
```

### CRUD 複数操作の例

```c
/**
 *******************************************************************************
 *  @brief          注文情報を登録し、在庫を更新します。
 *  @param[in]      order 注文情報
 *  @return         成功時は注文 ID、失敗時は -1
 *
 *  @par Resources
 *  ```yaml
 *  - type: table
 *    name: orders
 *    operations: [create, read]
 *    description: 注文テーブル (新規注文を登録)
 *
 *  - type: table
 *    name: order_details
 *    operations: [create]
 *    description: 注文明細テーブル
 *
 *  - type: table
 *    name: inventory
 *    operations: [read, update]
 *    description: 在庫テーブル (在庫数を減算)
 *
 *  - type: table
 *    name: products
 *    operations: [read]
 *    description: 商品マスタテーブル (価格・在庫情報を参照)
 *  ```
 *
 *  @note           トランザクション内で実行されます。
 *******************************************************************************
 */
int createOrder(const Order *order);
```

### ファイル操作の例

```c
/**
 *******************************************************************************
 *  @brief          設定ファイルを読み込み、パースします。
 *  @param[in]      configPath 設定ファイルのパス
 *  @param[out]     config 設定情報を格納する構造体
 *  @return         成功時は 0、失敗時は -1
 *
 *  @par Resources
 *  ```yaml
 *  - type: file
 *    name: $configPath
 *    operations: [read]
 *    description: アプリケーション設定ファイル
 *    format: ini
 *
 *  - type: file
 *    name: /etc/app/default.conf
 *    operations: [read]
 *    description: デフォルト設定ファイル (フォールバック)
 *    optional: true
 *  ```
 *******************************************************************************
 */
int loadConfig(const char *configPath, Config *config);
```

### API 呼び出しの例

```c
/**
 *******************************************************************************
 *  @brief          外部 API から天気情報を取得します。
 *  @param[in]      location 場所
 *  @param[out]     weather 天気情報
 *  @return         成功時は 0、失敗時は -1
 *
 *  @par Resources
 *  ```yaml
 *  - type: api
 *    name: weather-api.example.com/v1/current
 *    operations: [read]
 *    protocol: https
 *    description: 天気情報 API
 *
 *  - type: file
 *    name: /var/cache/weather.cache
 *    operations: [read, create, update]
 *    description: 天気情報キャッシュファイル
 *  ```
 *
 *  @note           キャッシュが有効な場合は API 呼び出しをスキップします。
 *******************************************************************************
 */
int getWeather(const char *location, Weather *weather);
```

### 削除操作の例

```c
/**
 *******************************************************************************
 *  @brief          ユーザーを削除します (論理削除)。
 *  @param[in]      userId ユーザー ID
 *  @return         成功時は 0、失敗時は -1
 *
 *  @par Resources
 *  ```yaml
 *  - type: table
 *    name: users
 *    operations: [read, update]
 *    description: ユーザーマスタテーブル (deleted_at を更新)
 *
 *  - type: table
 *    name: user_sessions
 *    operations: [delete]
 *    description: ユーザーセッションテーブル (物理削除)
 *
 *  - type: table
 *    name: audit_log
 *    operations: [create]
 *    description: 監査ログテーブル
 *  ```
 *******************************************************************************
 */
int deleteUser(int userId);
```

## リソースタイプ一覧

### 必須フィールド

| フィールド | 型 | 説明 | 例 |
| --- | --- | --- | --- |
| type | string | リソースタイプ (下記参照) | table, file, api |
| name | string | リソース名・識別子 | users, /var/log/app.log |
| operations | array | CRUD 操作のリスト | [read, update] |
| description | string | リソースの説明 | ユーザーマスタテーブル |

Table: 必須フィールド定義

### オプションフィールド

| フィールド | 型 | 説明 | 例 |
| --- | --- | --- | --- |
| format | string | ファイル形式・プロトコル | json, xml, csv, ini, https |
| optional | boolean | オプショナルリソースか | true, false |
| access_pattern | string | アクセスパターン | sequential, random, index |
| estimated_size | string | 推定サイズ・レコード数 | 1M records, 100KB |

Table: オプションフィールド定義

### サポートされるリソースタイプ

| タイプ | 説明 | 例 |
| --- | --- | --- |
| table | データベーステーブル | users, orders, inventory |
| view | データベースビュー | user_summary_view |
| file | ファイルシステム上のファイル | /var/log/app.log, config.ini |
| directory | ディレクトリ | /tmp/uploads |
| api | 外部 API エンドポイント | api.example.com/v1/users |
| memory | 共有メモリ・メモリマップドファイル | /dev/shm/cache |
| queue | メッセージキュー | rabbitmq://localhost/tasks |
| cache | キャッシュストア | redis://localhost:6379/0 |
| config | 設定リソース | environment variable, registry |

Table: リソースタイプ定義

### サポートされる操作 (operations)

| 操作 | 説明 | 該当する処理 |
| --- | --- | --- |
| create | 新規作成 | INSERT, ファイル新規作成、POST |
| read | 読み取り | SELECT, ファイル読み込み、GET |
| update | 更新 | UPDATE, ファイル上書き・追記、PUT/PATCH |
| delete | 削除 | DELETE, ファイル削除、DELETE |

Table: CRUD 操作定義

## 機械処理の例

### パースと検証

YAML パーサーを使用してリソース情報を抽出・検証できます。

```python
import yaml
import re

def extract_resources_from_doxygen(source_code):
    """Doxygen コメントからリソース情報を抽出"""
    pattern = r'@par\s+Resources\s+```yaml\s+(.*?)\s+```'
    matches = re.findall(pattern, source_code, re.DOTALL)

    resources = []
    for match in matches:
        try:
            parsed = yaml.safe_load(match)
            resources.extend(parsed)
        except yaml.YAMLError as e:
            print(f"YAML parse error: {e}")

    return resources

def validate_resource(resource):
    """リソース定義の必須フィールドを検証"""
    required_fields = ['type', 'name', 'operations', 'description']
    for field in required_fields:
        if field not in resource:
            return False, f"Missing required field: {field}"

    valid_operations = ['create', 'read', 'update', 'delete']
    for op in resource['operations']:
        if op not in valid_operations:
            return False, f"Invalid operation: {op}"

    return True, "OK"
```

### CRUD マトリクス生成

```python
def generate_crud_matrix(resources_by_function):
    """関数 × リソースの CRUD マトリクスを生成"""
    matrix = {}

    for func_name, resources in resources_by_function.items():
        for resource in resources:
            res_key = f"{resource['type']}:{resource['name']}"
            if res_key not in matrix:
                matrix[res_key] = {}

            ops = {
                'C': 'create' in resource['operations'],
                'R': 'read' in resource['operations'],
                'U': 'update' in resource['operations'],
                'D': 'delete' in resource['operations']
            }
            matrix[res_key][func_name] = ops

    return matrix
```

### 依存関係グラフ生成

```python
def generate_dependency_graph(resources_by_function):
    """リソース依存関係グラフを生成 (PlantUML 形式)"""
    lines = ["@startuml", "caption リソース依存関係図"]

    for func_name, resources in resources_by_function.items():
        for resource in resources:
            res_name = resource['name']
            ops_label = ", ".join(resource['operations'])
            lines.append(f'[{func_name}] --> ({res_name}) : {ops_label}')

    lines.append("@enduml")
    return "\n".join(lines)
```

## 運用ガイドライン

### 記載タイミング

- 関数の新規作成時に必ず記載
- リソースアクセスが追加・変更された際に更新
- コードレビュー時にリソース記載の妥当性を確認

### CI/CD 統合

```bash
# リソース定義の検証スクリプト
python scripts/validate_resources.py prod/src/*.c

# CRUD マトリクスの自動生成
python scripts/generate_crud_matrix.py prod/src/*.c > docs/crud-matrix.md
```

### ベストプラクティス

1. **粒度**: リソース名は具体的に (テーブル名、ファイルパスなど)
2. **精度**: 実際に行う操作のみを記載 (推測や将来の拡張は含めない)
3. **保守性**: リソースが変更されたら必ず更新
4. **トレーサビリティ**: optional フラグや条件を明記

### 注意事項

- パラメータで動的に決まるリソース名は `$parameterName` で表記
- オプショナルなリソースは `optional: true` を明記
- トランザクション境界を `@note` で補足説明
- セキュリティ上重要なリソースは `@warning` で注意喚起

## 今後の検討事項

- [ ] CI パイプラインでの自動検証スクリプト実装
- [ ] CRUD マトリクス自動生成ツール作成
- [ ] 既存コードへの段階的適用計画
- [ ] IDE プラグインでのリソース定義補完機能
- [ ] リソースタイプの拡張 (gRPC, GraphQL など)
- [ ] アクセス権限情報の追加 (read-only, admin-only など)
- [ ] パフォーマンス特性の記載 (インデックス使用有無など)

## Sources

調査した参考資料:

- [Doxygen, a document generator mainly for C++](https://idratherbewriting.com/learnapidoc/nativelibraryapis_doxygen.html)
- [How to Write API Documentation: a Best Practices Guide](https://stoplight.io/api-documentation-guide)
- [Set dependencies | Dataform | Google Cloud Documentation](https://docs.cloud.google.com/dataform/docs/dependencies)
- [Dive into ARM template from a Function App](https://techcommunity.microsoft.com/blog/appsonazureblog/dive-into-arm-template-from-a-function-app/4234337)
- [Resource | dlt Docs](https://dlthub.com/docs/general-usage/resource)
