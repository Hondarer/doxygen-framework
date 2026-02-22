#!/bin/bash

# postprocess.sh - Doxybook 後処理スクリプト
# 使用方法: ./postprocess.sh <markdown_directory>
# 例: ./postprocess.sh docs-src/doxybook

# set -x # デバッグ時のみ有効にする

# 引数チェック
if [ $# -ne 1 ]; then
    echo "使用方法: $0 <markdown_directory>"
    echo "例: $0 docs-src/doxybook"
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
    sed '/^|/ s/[[:space:]]*\!linebreak\![[:space:]]*/<br \/>/g' | \
    sed '/^[^|]/ s/[[:space:]]*\!linebreak\![[:space:]]*/  \n/g' | \
    
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

# 不要ファイルの削除
# 現段階で対象としていない Markdown を削除する
#
# - 使用例インデックス
# - Examples
# - ディレクトリページ
# - ページインデックス
# - Pages
# - グループインデックス
# - Modules
# - インデックスページ
rm -rf "$MARKDOWN_DIR"/index_examples.md \
       "$MARKDOWN_DIR"/Examples \
       "$MARKDOWN_DIR"/Files/dir_*.md \
       "$MARKDOWN_DIR"/index_pages.md \
       "$MARKDOWN_DIR"/Pages \
       "$MARKDOWN_DIR"/index_groups.md \
       "$MARKDOWN_DIR"/Modules \
       "$MARKDOWN_DIR"/indexpage.md

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

# サブディレクトリ内 Markdown の画像パスを修正
# Doxybook2 は Files/ 等のサブディレクトリに Markdown を配置するが、
# 画像は doxybook ルートの images/ に置かれるため、
# 相対パス images/{name} は ../images/{name} に修正する必要がある
#
# 修正対象ファイルで参照された画像ファイル名を収集し、
# Pages のみで参照される画像の後処理 (削除) に使用する
SUBDIR_IMAGES="$TEMP_DIR/subdir_images.txt"
touch "$SUBDIR_IMAGES"

for file in "${md_files[@]}"; do
    rel_path="${file#$MARKDOWN_DIR/}"
    # スラッシュが含まれる = サブディレクトリ内のファイル
    if [[ "$rel_path" == */* ]] && grep -qE '!\[[^]]*\]\([^)]+\)' "$file" 2>/dev/null; then
        # パス修正前に参照画像の basename を収集 (外部 URL は除外)
        # ([^/)]*\/)* でディレクトリ部分を読み飛ばし、([^/)?# ]+) で basename を取得する
        grep -oE '!\[[^]]*\]\([^)]+\)' "$file" | \
            grep -Ev '\(https?://' | \
            sed -E 's/!\[[^]]*\]\(([^/)]*\/)*([^/)?# ]+)\).*/\2/' >> "$SUBDIR_IMAGES"
        # 画像パスの修正とキャプション補正を同時に適用
        # - ディレクトリ部分を strip して ../images/{basename} に統一する
        #   ([^/)]*\/)* でディレクトリ部分を除去し basename のみ残す
        # - ![filename](url)caption → ![caption](url):
        #   Doxybook2 は @image html のキャプションを ) 直後にスペースなしで連結する。
        #   ) の直後が非スペース文字で始まる場合にキャプションと判定する。
        sed -i -E \
            -e 's/!\[([^]]*)\]\(([^/)]*\/)*([^/)?# ]+)\)/![\1](..\/images\/\3)/g' \
            -e 's/!\[[^]]*\]\(([^)]+)\)([^ ].*)/![\2](\1)/g' \
            "$file"
        echo "  Fixed image path/caption: $rel_path"
    fi
done

if [ -f "$MARKDOWN_DIR/index_pages.md" ]; then
    # 各フォルダに配置する README.md のタイトルには、相対パスを記載するルールにする。
    sed -i -e 's/\(\*\* *file \[\)[^/]*\/\([^]]*\]\)/\1\2/g' \
           -e 's/\(\.md\)#[^)]*/\1/g' \
           -e '/(Pages\/)/d' \
           "$MARKDOWN_DIR/index_pages.md"
#    # ファイルパスを抽出してタイトルに付与
#    # 例: * page [markdown のサンプル](Pages/md_src_README.md#page-md-src-readme)
#    #  → * page [src/README.md (markdown のサンプル)](Pages/md_src_README.md)
#    # (Pages/) を含む行は削除
#    awk '{
#        # (Pages/) を含む行はスキップ
#        if (match($0, /\(Pages\/\)$/)) {
#            next
#        }
#        if (match($0, /\* page \[([^\]]+)\]\(Pages\/md_([^)#]+)/, arr)) {
#            filepath = arr[2]
#            gsub(/_/, "/", filepath)
#            title = arr[1]
#            printf "* page [%s (%s)](Pages/md_%s)\n", filepath, title, arr[2]
#        } else {
#            print $0
#        }
#    }' "$MARKDOWN_DIR/index_pages.md" > "$MARKDOWN_DIR/index_pages.md.tmp"
#    mv "$MARKDOWN_DIR/index_pages.md.tmp" "$MARKDOWN_DIR/index_pages.md"
fi
if [ -f "$MARKDOWN_DIR/index_examples.md" ]; then
    sed -i -e 's/\(\*\* *file \[\)[^/]*\/\([^]]*\]\)/\1\2/g' \
           -e 's/\(\.md\)#[^)]*/\1/g' \
           -e '/(Pages\/)/d' \
           -e 's/<br\/>\([^&]\)/<br\/>\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\1/g' \
           "$MARKDOWN_DIR/index_examples.md"
fi

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Markdown ファイルのコピー処理
# copy-markdown-from-input.sh を呼び出して INPUT からの Markdown をコピー
"$SCRIPT_DIR/copy-markdown-from-input.sh" "$MARKDOWN_DIR" || exit 1

# Pages のみで参照される画像を images/ から削除
# サブディレクトリ (Files/ 等) から参照されていない画像は
# Pages/ 以下に正しい相対パスでコピー済みのため、images/ の該当ファイルは不要
IMAGES_DIR="$MARKDOWN_DIR/images"
if [ -d "$IMAGES_DIR" ]; then
    # awk 連想配列で SUBDIR_IMAGES を一括ロードし、O(M+N) で削除対象を抽出
    # NR==FNR フェーズ: SUBDIR_IMAGES の全エントリを subdir[] に格納 (O(M))
    # 第2フェーズ: 各画像 basename を O(1) ルックアップし、未登録のみ出力 (O(N))
    while IFS= read -r img_name; do
        rm "$IMAGES_DIR/$img_name"
        echo "  Removed Pages-only image: $img_name from images/"
    done < <(
        awk '
            NR==FNR { subdir[$0]=1; next }
            !subdir[$0]
        ' "$SUBDIR_IMAGES" \
          <(find "$IMAGES_DIR" -maxdepth 1 -type f -exec basename {} \;)
    )
fi

# ファイルインデックスのパッチ
# Doxybook2 が出力するディレクトリ名・ファイル名は Doxygen INPUT ルートからの相対パス形式。
# 例: calc/include, calc/src/add/add.c
# merge-index-files.py でのマージ時に index_pages.md のローカル名と対応付けるため、
# patch-index-files.py によって末尾コンポーネントのみに変換する。
if [ -f "$MARKDOWN_DIR/index_files.md" ]; then
    python3 "$SCRIPT_DIR/patch-index-files.py" "$MARKDOWN_DIR/index_files.md" || exit 1
fi

# index_files.md と index_pages.md のマージ処理
# merge-index-files.py を呼び出して index_files_and_pages.md を生成
python3 "$SCRIPT_DIR/merge-index-files.py" "$MARKDOWN_DIR" || exit 1

# 処理終了
exit 0
