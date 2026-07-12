# doxybook2 への PlantUML 対応

doxygen の出力した xml ファイルを以下のようにパッチすることで、`[warning] Text tag "plantuml" not recognised, please contact the author` のメッセージを出すことなく出力の Markdown を生成する。

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
