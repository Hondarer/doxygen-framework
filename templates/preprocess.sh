#!/bin/bash

# preprocess.sh - Doxybook 前処理スクリプト
# 使用方法: ./preprocess.sh <xml_directory>
# 例: ./preprocess.sh ../xml

set -e  # エラーで停止

# 引数チェック
if [ $# -ne 1 ]; then
    echo "エラー: 引数が正しくありません"
    exit 1
fi

XML_FOLDER="$1"

# フォルダ存在チェック
if [ ! -d "$XML_FOLDER" ]; then
    echo "エラー: 指定されたフォルダが見つかりません: $XML_FOLDER"
    exit 1
fi

# XML ファイル検索
XML_FILES=$(find "$XML_FOLDER" -type f \( -name "*.xml" -o -name "*.XML" \) 2>/dev/null)

if [ -z "$XML_FILES" ]; then
    echo "警告: 指定されたフォルダにXMLファイルが見つかりません: $XML_FOLDER"
    exit 0
fi

# XML ファイル数をカウント
XML_COUNT=$(echo "$XML_FILES" | wc -l)
PROCESSED_COUNT=0

# 各 XML ファイルを処理
while IFS= read -r xml_file; do
    PROCESSED_COUNT=$((PROCESSED_COUNT + 1))
    
    # PlantUML 変換
    # 「```plantuml 」のように、 の直前にすでに三連バッククオート付きの plantuml コードフェンスがある場合は、それを消してから通常の変換を行う。
    # 「\n ``` 」のように、 の直後に改行して三連バッククオートがある場合は、それを消してから通常の変換を行う。
    # 上記に当てはまらない場合は、<plantuml> と </plantuml> をコードフェンス + @startuml / @enduml に変換する。
    sed -z -E \
        -e 's/```plantuml[[:space:]]*<plantuml>/<plantuml>/g' \
        -e 's|</plantuml>[[:space:]]*\n[[:space:]]*```[[:space:]]*|</plantuml>|g' \
        -e 's|[[:space:]]*<plantuml>|\n\n```plantuml\n@startuml|g' \
        -e 's|</plantuml>|@enduml\n```|g' \
        -- "$xml_file" | \
    # パラメータ direction 変換
    sed -e 's|<parametername direction="in">\([^<]*\)</parametername>|<parametername>[in] \1</parametername>|g' \
        -e 's|<parametername direction="out">\([^<]*\)</parametername>|<parametername>[out] \1</parametername>|g' \
        -e 's|<parametername direction="in,out">\([^<]*\)</parametername>|<parametername>[in,out] \1</parametername>|g' \
        -e 's|<parametername direction="in, out">\([^<]*\)</parametername>|<parametername>[in,out] \1</parametername>|g' \
        -e 's|<parametername direction="inout">\([^<]*\)</parametername>|<parametername>[inout] \1</parametername>|g' | \
    # linebreak 変換 (<linebreak/> を !linebreak! に変換、postprocess で最終的に改行に置換)
    sed ':a;N;$!ba;s|<linebreak/>\n|!linebreak!|g' \
        > "${xml_file}.tmp" && mv "${xml_file}.tmp" "$xml_file"
    
done <<< "$XML_FILES"
