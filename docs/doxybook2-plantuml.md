# doxybook2 への PlantUML 対応

Doxygen が出力した XML ファイルに以下のようにパッチを適用することで、`[warning] Text tag "plantuml" not recognised, please contact the author` のメッセージを出力することなく Markdown を生成します。

## 変換ルール

`<plantuml>` を

````
```plantuml
@startuml
````

`</plantuml>` を

````
@enduml
```
````

## XML へ挿入する PlantUML の注意点

XML へ挿入する PlantUML 記述の中で `<--` を使うと、Doxybook2 が XML のパース エラーを起こします。  
エッジを逆向きに描きたい場合は、エッジの両端を入れ替えたうえで `-->` を使用します。
