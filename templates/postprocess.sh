#!/bin/bash

# postprocess.sh - Doxybook 後処理スクリプト
# 使用方法: ./postprocess.sh <markdown_directory>
# 例: ./postprocess.sh docs-src/doxybook

# set -x # デバッグ時のみ有効にする

# 引数チェック
if [ $# -ne 1 ]; then
    echo "使用方法: $0 <markdown_directory>"
    echo "例: $0 docs-src/doxybook2"
    exit 1
fi

MARKDOWN_DIR="$1"

# ディレクトリの存在チェック
if [ ! -d "$MARKDOWN_DIR" ]; then
    echo "エラー: ディレクトリが存在しません: $MARKDOWN_DIR"
    exit 1
fi

# 一時ディレクトリを作成
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Markdown ファイルのポストプロセッシング関数
process_markdown_file() {
    local file="$1"
    local temp_file
    temp_file=$(mktemp "$TEMP_DIR/$(basename "$file").XXXXXX") || {
        echo "エラー: 一時ファイルの作成に失敗しました: $file"
        return 1
    }
    
    # インクルード処理
    local include_temp
    include_temp=$(mktemp "$TEMP_DIR/$(basename "$file").include.XXXXXX")
    
    while IFS= read -r line; do
        # !include {filename} パターンをチェック
        if [[ "$line" =~ ^[[:space:]]*\!include[[:space:]]+([^[:space:]]+) ]]; then
            local include_file="${BASH_REMATCH[1]}"
            local include_path
            
            # 相対パスとして解決 (markdownディレクトリを基準)
            if [[ "$include_file" == /* ]]; then
                # 絶対パス
                include_path="$include_file"
            else
                # 相対パス
                include_path="$MARKDOWN_DIR/$include_file"
            fi
            
            # インクルードファイルの存在チェック
            if [ -f "$include_path" ]; then
                #echo "  -> インクルード: $include_file"
                # ファイルの内容を出力
                cat "$include_path"
            else
                echo "  -> 警告: インクルードファイルが見つかりません: $include_file"
                # 元の行をそのまま出力
                echo "$line"
            fi
        else
            # 通常の行をそのまま出力
            echo "$line"
        fi
    done < "$file" > "$include_temp"
    
    # YAML フロントマター処理
    # - YAML フロントマター内の空行を除去
    awk '
    BEGIN { 
        in_frontmatter = 0
        frontmatter_started = 0
        line_count = 0
    }
    
    # 最初の行が --- で始まる場合、フロントマターの開始
    line_count == 0 && /^---[[:space:]]*$/ {
        frontmatter_started = 1
        in_frontmatter = 1
        print $0
        line_count++
        next
    }
    
    # フロントマター内で --- が見つかった場合、フロントマターの終了
    in_frontmatter && /^---[[:space:]]*$/ {
        in_frontmatter = 0
        print $0
        line_count++
        next
    }
    
    # フロントマター内の処理
    in_frontmatter {
        # 空行または空白のみの行をスキップ
        if (/^[[:space:]]*$/) {
            line_count++
            next
        }
        # 非空行はそのまま出力
        print $0
        line_count++
        next
    }
    
    # フロントマター外の処理 (通常の行)
    {
        print $0
        line_count++
    }
    ' "$include_temp" | \
    
    # 行末空白除去と !linebreak! 処理
    # - sedを使用して行末の空白文字を削除し、
    # - !linebreak! を空白 2 つ + 改行に変換
    # - 表内 (| で始まる) の !linebreak! は <br/> に変換
    sed 's/[[:space:]]*$//' | \
    sed '/^|/ s/[[:space:]]*\!linebreak\![[:space:]]*/<br \/>/' | \
    sed '/^[^|]/ s/[[:space:]]*\!linebreak\![[:space:]]*/  \n/' | \
    
    # 連続空行統合
    # - 空白文字のみの行 (空行含む) を空行として扱う
    # - 連続する空行を1つの空行に置換
    # - 文末の複数の空行も1つの空行に置換
    awk '
    BEGIN { blank_count = 0 }
    
    # 空白文字のみの行 (空行含む) をチェック
    /^[[:space:]]*$/ {
        blank_count++
        # 最初の空行のみ保持
        if (blank_count == 1) {
            blank_line = ""  # 完全な空行として保存
        }
        next
    }
    
    # 非空行の場合
    {
        # 前に空行があった場合、1つだけ出力
        if (blank_count > 0) {
            print blank_line
            blank_count = 0
        }
        # 現在の行を出力
        print $0
    }
    ' | \
    
    # Markdown 空白整理
    # - Markdown ファイルから不要な行頭空白を除去
    # - 箇条書き (*, -, +) やコード ブロック (```) のインデントは保持
    awk '
    BEGIN {
        in_code_block = 0
        in_code_block_first = 0
    }
    
    # コード ブロックの開始/終了を検出
    /^[[:space:]]*```/ {
        if (in_code_block) {
            in_code_block = 0
            in_code_block_first = 0
        } else {
            in_code_block = 1
            in_code_block_first = 1
        }
        print $0
        next
    }
    
    # コード ブロックの直後の行が空行の場合、その空行をスキップ
    in_code_block_first && /^[[:space:]]*$/ {
        in_code_block_first = 0
        next
    }
    
    in_code_block_first {
        in_code_block_first = 0
    }
    
    # コード ブロック内の場合は元の行をそのまま保持
    in_code_block {
        print $0
        next
    }
    
    # 以下の場合は元の行をそのまま保持
    # - 箇条書きマーカー (*, -, +)
    # - 番号付きリスト (数字 + . + 空白)
    # - インデントされたコード (4 つ以上の空白で始まる)
    /^[[:space:]]*[*+-][[:space:]]/ || /^[[:space:]]*[0-9]+\.[[:space:]]/ || /^[[:space:]]{4,}[^[:space:]]/ {
        print $0
        next
    }
    
    {
        # いずれでもない場合は行頭の空白を除去
        gsub(/^[[:space:]]*/, "")
        print $0
    }
    ' > "$temp_file"
    
    rm -f "$include_temp"
    
    # ファイル更新
    if mv "$temp_file" "$file" 2>/dev/null; then
        return 0
    else
        rm -f "$temp_file"
        return 1
    fi
}

# .mdファイルを配列に収集
mapfile -t md_files < <(find "$MARKDOWN_DIR" -name "*.md" -type f)

# 処理対象ファイル数をカウント
total_files=${#md_files[@]}
processed_files=0

# 各ファイルを処理
for file in "${md_files[@]}"; do
    if process_markdown_file "$file"; then
        ((processed_files++))
    fi
done

# 不要ファイルの削除
# 現段階で対象としていない Markdown を削除する
#
# - 構造体ファイル (それぞれに include するので処理後は不要)
# - クラスインデックス
# - 名前空間インデックス
# - Pages インデックス
# - Exanples インデックス
# - ディレクトリページ
# - Todo リスト
# - Deprecated リスト
rm -f "$MARKDOWN_DIR"/struct*.md \
      "$MARKDOWN_DIR"/index_classes.md \
      "$MARKDOWN_DIR"/index_namespaces.md \
      "$MARKDOWN_DIR"/index_pages.md \
      "$MARKDOWN_DIR"/index_examples.md \
      "$MARKDOWN_DIR"/dir_*.md \
      "$MARKDOWN_DIR"/todo.md \
      "$MARKDOWN_DIR"/deprecated.md

# ファイルインデックスの編集
# テンプレートでは正しく置換できなかったため、シェルで加工する
#
# オリジナル
# * **dir [src]**
#     * **file [src/calculator.c](calculator_8c.md#file-calculator.c)** <br/>計算機の実装ファイル
#     * **file [src/calculator.h](calculator_8h.md#file-calculator.h)** <br/>簡単な計算機のヘッダーファイル
#
# 編集後
# * **dir [src]**
#     * **file [calculator.c](calculator_8c.md)** <br/>計算機の実装ファイル
#     * **file [calculator.h](calculator_8h.md)** <br/>簡単な計算機のヘッダーファイル
#
if [ -f "$MARKDOWN_DIR/index_files.md" ]; then
    sed -i -e 's/\(\*\* *file \[\)[^/]*\/\([^]]*\]\)/\1\2/g' \
           -e 's/\(\.md\)#[^)]*/\1/g' \
           "$MARKDOWN_DIR/index_files.md"
fi

# 処理終了
exit 0
