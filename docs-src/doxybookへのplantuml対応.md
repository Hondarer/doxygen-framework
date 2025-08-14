# doxybook への PlantUML 対応

doxygen の出力した xml ファイルを以下のようにパッチすることで、`[warning] Text tag "plantuml" not recognised, please contact the author` のメッセージを出すことなく出力の Markdown を生成する。

## 変換ルール

`<plantuml>` を

````
```plantuml
@startuml
````

`</plantuml>` を

````
**Figure**: 

@enduml
```
````
