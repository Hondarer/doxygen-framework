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
    # <plantuml ...> と </plantuml> をコードフェンス + @startuml / @enduml に変換する。
    sed -e 's|\s*<plantuml\([^>]*\)>|\n\n```plantuml\n@startuml\n|g' \
        -e 's|</plantuml>|\n@enduml\n```|g' \
        "$xml_file" | \
    # パラメータ direction 変換
    sed -e 's|<parametername direction="in">\([^<]*\)</parametername>|<parametername>[in] \1</parametername>|g' \
        -e 's|<parametername direction="out">\([^<]*\)</parametername>|<parametername>[out] \1</parametername>|g' \
        -e 's|<parametername direction="in,out">\([^<]*\)</parametername>|<parametername>[in,out] \1</parametername>|g' \
        -e 's|<parametername direction="in, out">\([^<]*\)</parametername>|<parametername>[in,out] \1</parametername>|g' \
        -e 's|<parametername direction="inout">\([^<]*\)</parametername>|<parametername>[inout] \1</parametername>|g' | \
    # linebreak 変換 (<linebreak/> を !linebreak! に変換、postprocess で最終的に改行に置換)
    sed ':a;N;$!ba;s|<linebreak/>\n|!linebreak!|g' | \
    # ダブルアンダースコア保護
    # Doxygen は __identifier__ を Markdown 強調として解釈し <bold>identifier</bold> に変換する。
    # doxybook2 はこれをさらに **identifier** (Markdown bold) に変換するため、
    # __attribute__ が **attribute** に化けてしまう。
    # XML 段階で <bold>C識別子</bold> を !dunder!識別子!dunder! に変換して保護し、
    # postprocess で __ に戻す。
    sed 's|<bold>\([a-zA-Z_][a-zA-Z0-9_]*\)</bold>|!dunder!\1!dunder!|g' | \
    # <name>/<title> タグ内の __ を !dunder! に変換
    # doxybook2 は <name> タグの内容を見出しやテンプレートの変数として直接展開するため、
    # <bold> 変換とは別に <name> タグ内の __ も保護が必要。
    # <title> タグは extract-graphs.py が挿入するグラフ見出しで使用される。
    # ループ展開で複数の __ を含む識別子 (__foo__bar__ など) にも対応する。
    sed ':loop; s|<name>\([^<]*\)__\([^<]*\)</name>|<name>\1!dunder!\2</name>|; t loop' | \
    sed ':loop; s|<title>\([^<]*\)__\([^<]*\)</title>|<title>\1!dunder!\2</title>|; t loop' | \
    # セクション見出しレベル変換
    # doxybook2 は <sect1> を Markdown の # (レベル1) に変換するが、
    # ファイルドキュメントの構造上 ##### (レベル5) が正しい。
    # doxybook2 はセクションレベルのオフセット機能を持たないため、
    # XML 段階で sect1→sect5, sect2→sect6 に変換して対応する。
    sed -e 's|<sect1|<sect5|g' \
        -e 's|</sect1>|</sect5>|g' \
        -e 's|<sect2|<sect6|g' \
        -e 's|</sect2>|</sect6>|g' \
        > "${xml_file}.tmp" && mv "${xml_file}.tmp" "$xml_file"
    
done <<< "$XML_FILES"
