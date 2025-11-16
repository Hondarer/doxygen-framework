#!/bin/bash

# collect-pages.sh - Markdown ファイルをツリー構造を維持してコピーするスクリプト
#
# 使用方法:
#   ./collect-pages.sh <基準ディレクトリ> <コピー元> <コピー先>
#
# 例:
#   ./collect-pages.sh D:\Users\tetsuo\Local\repos\c-modernization-kit prod docs-src\doxybook\Pages

set -e

# 引数チェック
if [ $# -ne 3 ]; then
    echo "Usage: $0 <base-dir> <source-dir> <dest-dir>" >&2
    echo "Example: $0 /path/to/base prod docs-src/doxybook/Pages" >&2
    exit 1
fi

BASE_DIR="$1"
SOURCE_DIR="$2"
DEST_DIR="$3"

# パスの正規化 (Windows パスを Unix 形式に変換)
BASE_DIR=$(cd "$BASE_DIR" && pwd)
SOURCE_DIR="${SOURCE_DIR//\\//}"
DEST_DIR="${DEST_DIR//\\//}"

# 絶対パスの構築
SOURCE_PATH="${BASE_DIR}/${SOURCE_DIR}"
DEST_PATH="${BASE_DIR}/${DEST_DIR}"

# コピー元の存在確認
if [ ! -d "$SOURCE_PATH" ]; then
    echo "Error: Source directory does not exist: $SOURCE_PATH" >&2
    exit 1
fi

# コピー先ディレクトリのクリーンアップと作成
if [ -d "$DEST_PATH" ]; then
    echo "Cleaning up destination directory: $DEST_PATH"
    rm -rf "$DEST_PATH"
fi

mkdir -p "$DEST_PATH"
echo "Created destination directory: $DEST_PATH"

echo "Starting to collect Markdown files..."
echo "  Base directory: $BASE_DIR"
echo "  Source: $SOURCE_PATH"
echo "  Destination: $DEST_PATH"
echo ""

# インデックスファイルのパス (コピー先の1階層上位)
INDEX_DIR=$(dirname "$DEST_PATH")
INDEX_FILE="${INDEX_DIR}/index_pages.md"

# インデックスファイルの初期化
cat > "$INDEX_FILE" << 'EOF'
---
author: doxygen and doxybook2
---

<!-- IMPORTANT: This is an AUTOMATICALLY GENERATED file by doxygen and doxybook2. Manual edits are NOT allowed. -->

# ページの一覧

EOF

# ファイルリストを一時ファイルに保存
TEMP_FILE=$(mktemp)

# Markdown ファイルの検索とコピー
find "$SOURCE_PATH" -type f -name "*.md" | LC_ALL=C sort | while read -r md_file; do
    # 基準ディレクトリからの相対パスを取得
    rel_path="${md_file#$BASE_DIR/}"

    # コピー先のファイルパス
    dest_file="${DEST_PATH}/${rel_path#$SOURCE_DIR/}"

    # コピー先のディレクトリを作成
    dest_dir=$(dirname "$dest_file")
    mkdir -p "$dest_dir"

    # ファイルをコピー
    cp "$md_file" "$dest_file"

    # インデックス用の相対パスを保存
    index_rel_path="${rel_path#$SOURCE_DIR/}"
    echo "$index_rel_path" >> "$TEMP_FILE"

    echo "Copied: $index_rel_path"
done

# インデックスファイルの生成
if [ -f "$TEMP_FILE" ]; then
    # 出力済みディレクトリを追跡する連想配列
    declare -A printed_dirs

    # 一時ファイルをソートして順序を統一
    LC_ALL=C sort "$TEMP_FILE" -o "$TEMP_FILE"

    while IFS= read -r file_path; do
        # ディレクトリとファイル名を分離
        dir_path=$(dirname "$file_path")
        file_name=$(basename "$file_path")

        # ディレクトリ構造を出力
        if [ "$dir_path" != "." ]; then
            IFS='/' read -ra DIR_PARTS <<< "$dir_path"

            # 各階層のディレクトリを出力 (未出力の場合のみ)
            current_path=""
            for ((i=0; i<${#DIR_PARTS[@]}; i++)); do
                part="${DIR_PARTS[$i]}"

                # 現在のパスを構築
                if [ -z "$current_path" ]; then
                    current_path="$part"
                else
                    current_path="$current_path/$part"
                fi

                # まだ出力していない場合のみ出力
                if [ -z "${printed_dirs[$current_path]}" ]; then
                    indent=""
                    for ((j=0; j<i; j++)); do
                        indent="    $indent"
                    done

                    echo "${indent}* dir ${part}" >> "$INDEX_FILE"
                    printed_dirs[$current_path]=1
                fi
            done
        fi

        # ファイルを出力
        indent=""
        if [ "$dir_path" != "." ]; then
            IFS='/' read -ra DIR_PARTS <<< "$dir_path"
            for ((j=0; j<${#DIR_PARTS[@]}; j++)); do
                indent="    $indent"
            done
        fi

        # Pages サブディレクトリからの相対パスでリンクを作成
        link_path="Pages/${file_path}"

        # コピー済みファイルから最初の見出しを抽出
        copied_file="${DEST_PATH}/${file_path}"
        description=""
        if [ -f "$copied_file" ]; then
            # YAML フロントマター以降の最初の # 見出しを取得
            description=$(awk '
                BEGIN { in_frontmatter=0; found=0 }
                /^---$/ {
                    if (NR==1) { in_frontmatter=1; next }
                    else if (in_frontmatter) { in_frontmatter=0; next }
                }
                in_frontmatter { next }
                /^# / && !found {
                    sub(/^# /, "");
                    print;
                    found=1;
                    exit
                }
            ' "$copied_file")
        fi

        # ファイルエントリを出力
        if [ -n "$description" ]; then
            echo "${indent}* page [${file_path}](${link_path}) <br/>${description}" >> "$INDEX_FILE"
        else
            echo "${indent}* page [${file_path}](${link_path})" >> "$INDEX_FILE"
        fi

    done < "$TEMP_FILE"

    rm -f "$TEMP_FILE"
fi

echo ""
echo "Created index file: $INDEX_FILE"
echo "Markdown collection completed."
