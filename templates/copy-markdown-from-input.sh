#!/bin/bash

# copy-markdown-from-input.sh - Doxyfile の INPUT から Markdown ファイルをコピー
# 使用方法: ./copy-markdown-from-input.sh <markdown_directory>
# 例: ./copy-markdown-from-input.sh docs-src/doxybook

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

# Doxyfile から INPUT を抽出
# - INPUT = で始まる行から開始
# - \ で継続する行をすべて結合
# - # 以降のコメントを除去
# - 空白で区切られた値をリストとして取得
extract_input_from_doxyfile() {
    local doxyfile="$1"

    if [ ! -f "$doxyfile" ]; then
        echo "エラー: Doxyfile が存在しません: $doxyfile" >&2
        return 1
    fi

    awk '
        /^INPUT[[:space:]]*=/ {
            # INPUT 行を検出
            in_input = 1
            # = 以降を取得
            sub(/^INPUT[[:space:]]*=[[:space:]]*/, "")
            # 前の値をクリア（最後の INPUT を使用）
            value = ""
        }

        in_input {
            # # 以降のコメントを除去
            sub(/#.*/, "")

            # 行末の \ をチェック
            if (sub(/\\[[:space:]]*$/, "")) {
                # \ がある場合は値を保存して継続
                gsub(/^[[:space:]]+|[[:space:]]+$/, "")
                if (length($0) > 0) {
                    if (value) value = value " " $0
                    else value = $0
                }
                next
            } else {
                # \ がない場合は最終行
                gsub(/^[[:space:]]+|[[:space:]]+$/, "")
                if (length($0) > 0) {
                    if (value) value = value " " $0
                    else value = $0
                }
                # 最後の INPUT を保存（まだ exit しない）
                last_value = value
                in_input = 0
                value = ""
            }
        }

        END {
            # 最後の INPUT を出力
            if (last_value) print last_value
        }
    ' "$doxyfile"
}

# Doxyfile から USE_MDFILE_AS_MAINPAGE を抽出
extract_use_mdfile_as_mainpage_from_doxyfile() {
    local doxyfile="$1"

    if [ ! -f "$doxyfile" ]; then
        echo "エラー: Doxyfile が存在しません: $doxyfile" >&2
        return 1
    fi

    awk '
        /^USE_MDFILE_AS_MAINPAGE[[:space:]]*=/ {
            # USE_MDFILE_AS_MAINPAGE 行を検出
            # = 以降を取得
            sub(/^USE_MDFILE_AS_MAINPAGE[[:space:]]*=[[:space:]]*/, "")
            # # 以降のコメントを除去
            sub(/#.*/, "")
            # 前後の空白を除去
            gsub(/^[[:space:]]+|[[:space:]]+$/, "")
            # 最後の値を保存
            last_value = $0
        }

        END {
            # 最後の USE_MDFILE_AS_MAINPAGE を出力
            if (last_value) print last_value
        }
    ' "$doxyfile"
}

# .gitignore からディレクトリ除外パターンを抽出
extract_gitignore_patterns() {
    local gitignore_file="$1"

    if [ ! -f "$gitignore_file" ]; then
        return 0
    fi

    # シンプルなディレクトリ名のみを抽出
    # - コメント (# で始まる行) をスキップ
    # - 空行をスキップ
    # - / や * を含むパターンはスキップ（シンプルなディレクトリ名のみ）
    # - ! で始まる否定パターンはスキップ
    grep -v '^#' "$gitignore_file" | \
    grep -v '^[[:space:]]*$' | \
    grep -v '^!' | \
    grep -v '/' | \
    grep -v '\*' | \
    sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Markdown ファイルから参照されている画像ファイルをコピー
copy_referenced_images() {
    local md_src="$1"   # コピー元 .md ファイル
    local md_dest="$2"  # コピー先 .md ファイル

    local src_dir dest_dir
    src_dir="$(dirname "$md_src")"
    dest_dir="$(dirname "$md_dest")"

    # ![alt](path) の参照を抽出し、URL でないものを対象とする
    grep -oE '!\[[^]]*\]\([^)]+\)' "$md_src" 2>/dev/null | \
    sed 's/.*(\(.*\))/\1/' | \
    grep -Ev '^https?://' | \
    while IFS= read -r img_ref; do
        # クエリパラメータ・アンカーを除去
        local img_path="${img_ref%%[?#]*}"
        [ -z "$img_path" ] && continue

        local src_img="$src_dir/$img_path"
        if [ -f "$src_img" ]; then
            local dest_img="$dest_dir/$img_path"
            mkdir -p "$(dirname "$dest_img")"
            cp "$src_img" "$dest_img"
            echo "  Copied image: $img_path (referenced from $(basename "$md_src"))"
        fi
    done
}

# Markdown ファイルとディレクトリ構造をコピー
copy_markdown_files() {
    local base_dir="$1"       # Doxygen 実行ディレクトリ (../prod)
    local input_dirs="$2"     # INPUT ディレクトリリスト (空白区切り)
    local dest_dir="$3"       # コピー先ディレクトリ

    # コピー先をクリーンアップして作成
    rm -rf "$dest_dir"
    mkdir -p "$dest_dir"

    # .gitignore パターンを抽出
    local gitignore_patterns=""
    local gitignore_file="../.gitignore"
    if [ -f "$gitignore_file" ]; then
        gitignore_patterns=$(extract_gitignore_patterns "$gitignore_file")
        if [ -n "$gitignore_patterns" ]; then
            echo "  Loaded .gitignore patterns: $(echo "$gitignore_patterns" | tr '\n' ' ')"
        fi
    fi

    # 各 INPUT ディレクトリを処理
    for input_path in $input_dirs; do
        # 絶対パスに変換
        local src_path
        if [[ "$input_path" == /* ]]; then
            src_path="$input_path"
        else
            src_path="$base_dir/$input_path"
        fi

        # ファイルの場合
        if [ -f "$src_path" ]; then
            # .md ファイルならコピー
            if [[ "$src_path" == *.md ]]; then
                local filename=$(basename "$src_path")
                local dest_file="$dest_dir/$filename"
                cp "$src_path" "$dest_file"
                echo "  Copied file: $input_path"
                copy_referenced_images "$src_path" "$dest_file"
            fi
        # ディレクトリの場合
        elif [ -d "$src_path" ]; then
            # ディレクトリ構造を走査
            # -type d で空ディレクトリも取得
            # -type f で .md ファイルを取得

            # .gitignore パターンから find の -prune 条件を構築
            local prune_args=""
            if [ -n "$gitignore_patterns" ]; then
                local first=1
                for pattern in $gitignore_patterns; do
                    if [ $first -eq 1 ]; then
                        prune_args="\\( -name \"$pattern\""
                        first=0
                    else
                        prune_args="$prune_args -o -name \"$pattern\""
                    fi
                done
                if [ -n "$prune_args" ]; then
                    prune_args="$prune_args \\) -prune -o"
                fi
            fi

            # まず空ディレクトリを含むすべてのディレクトリ構造を作成
            # .gitignore パターンにマッチするディレクトリは除外
            if [ -n "$prune_args" ]; then
                eval "find \"$src_path\" $prune_args -type d -print" | while read -r dir; do
                    local rel_path="${dir#$src_path}"
                    # src_path 自体は除外
                    if [ -n "$rel_path" ] && [ "$rel_path" != "$dir" ]; then
                        # 先頭の / を除去
                        rel_path="${rel_path#/}"
                        mkdir -p "$dest_dir/$input_path/$rel_path"
                    fi
                done
            else
                find "$src_path" -type d | while read -r dir; do
                    local rel_path="${dir#$src_path}"
                    # src_path 自体は除外
                    if [ -n "$rel_path" ] && [ "$rel_path" != "$dir" ]; then
                        # 先頭の / を除去
                        rel_path="${rel_path#/}"
                        mkdir -p "$dest_dir/$input_path/$rel_path"
                    fi
                done
            fi

            # 次に .md ファイルをコピー（.gitignore パターンは除外）
            local find_cmd
            if [ -n "$prune_args" ]; then
                find_cmd="find \"$src_path\" $prune_args -type f -name \"*.md\" -print"
            else
                find_cmd="find \"$src_path\" -type f -name \"*.md\""
            fi

            if eval "$find_cmd" | grep -q .; then
                eval "$find_cmd" | while read -r md_file; do
                    local rel_path="${md_file#$src_path}"
                    # 先頭の / を除去
                    rel_path="${rel_path#/}"
                    local dest_file="$dest_dir/$input_path/$rel_path"
                    local dest_file_dir=$(dirname "$dest_file")
                    mkdir -p "$dest_file_dir"
                    cp "$md_file" "$dest_file"
                    echo "  Copied: $input_path/$rel_path"
                    copy_referenced_images "$md_file" "$dest_file"
                done
            fi
        else
            echo "  Warning: INPUT path not found: $input_path (resolved to: $src_path)"
        fi
    done
}

# メイン処理
echo "Copying Markdown files from INPUT directories..."

# 使用された Doxyfile を特定
# - CATEGORY が指定されている場合は Doxyfile.part.{CATEGORY}
# - それ以外は Doxyfile.part または Doxyfile
DOXYFILE_PATH=""
TEMP_DOXYFILE=""

if [ -n "$CATEGORY" ]; then
    if [ -f "../Doxyfile.part.$CATEGORY" ]; then
        # マージされた内容を再現
        TEMP_DOXYFILE=$(mktemp)
        cat "../doxyfw/Doxyfile" "../Doxyfile.part.$CATEGORY" > "$TEMP_DOXYFILE"
        DOXYFILE_PATH="$TEMP_DOXYFILE"
        echo "  Using merged Doxyfile: Doxyfile + Doxyfile.part.$CATEGORY"
    else
        DOXYFILE_PATH="../doxyfw/Doxyfile"
        echo "  Using base Doxyfile (Doxyfile.part.$CATEGORY not found)"
    fi
elif [ -f "../Doxyfile.part" ]; then
    # マージされた内容を再現
    TEMP_DOXYFILE=$(mktemp)
    cat "../doxyfw/Doxyfile" "../Doxyfile.part" > "$TEMP_DOXYFILE"
    DOXYFILE_PATH="$TEMP_DOXYFILE"
    echo "  Using merged Doxyfile: Doxyfile + Doxyfile.part"
else
    DOXYFILE_PATH="../doxyfw/Doxyfile"
    echo "  Using base Doxyfile"
fi

# INPUT を抽出
INPUT_DIRS=$(extract_input_from_doxyfile "$DOXYFILE_PATH")

if [ -n "$INPUT_DIRS" ]; then
    echo "  INPUT directories: $INPUT_DIRS"

    # 引用符が含まれている場合は警告
    if echo "$INPUT_DIRS" | grep -q '"'; then
        echo "  Warning: Quoted paths in INPUT may not be handled correctly"
    fi

    # Markdown ファイルをコピー
    PAGES_DIR="$MARKDOWN_DIR/Pages"
    copy_markdown_files "../prod" "$INPUT_DIRS" "$PAGES_DIR"
    echo "Markdown files copied to $PAGES_DIR"

    # USE_MDFILE_AS_MAINPAGE を抽出してリネーム
    USE_MDFILE_AS_MAINPAGE=$(extract_use_mdfile_as_mainpage_from_doxyfile "$DOXYFILE_PATH")
    if [ -n "$USE_MDFILE_AS_MAINPAGE" ]; then
        echo "  USE_MDFILE_AS_MAINPAGE: $USE_MDFILE_AS_MAINPAGE"

        # ファイルの basename を取得
        MAINPAGE_BASENAME=$(basename "$USE_MDFILE_AS_MAINPAGE")

        # コピーされたファイルのパスを構築
        MAINPAGE_SRC="$PAGES_DIR/$MAINPAGE_BASENAME"
        MAINPAGE_DEST="$PAGES_DIR/README.md"

        # ファイルが存在する場合はリネーム
        if [ -f "$MAINPAGE_SRC" ]; then
            mv "$MAINPAGE_SRC" "$MAINPAGE_DEST"
            echo "  Renamed $MAINPAGE_BASENAME to README.md"
        else
            echo "  Warning: Mainpage file not found: $MAINPAGE_SRC"
        fi
    fi

    # index_pages.md を生成
    INDEX_PAGES_FILE="$MARKDOWN_DIR/index_pages.md"

    # ヘッダー部分を生成
    cat > "$INDEX_PAGES_FILE" << 'EOF'
---
author: doxygen and doxybook2
---

<!-- IMPORTANT: This is an AUTOMATICALLY GENERATED file by doxygen and doxybook2. Manual edits are NOT allowed. -->

# ページの一覧

EOF

    # Pages ディレクトリ内のディレクトリとファイルをリストアップ（空フォルダも含む）
    if [ -d "$PAGES_DIR" ]; then
        # ファイルリストを一時ファイルに保存
        TEMP_FILE=$(mktemp)

        # Markdown ファイルを検索してソート
        find "$PAGES_DIR" -type f -name "*.md" | LC_ALL=C sort | while read -r md_file; do
            # Pages ディレクトリからの相対パスを取得
            rel_path="${md_file#$PAGES_DIR/}"
            echo "$rel_path" >> "$TEMP_FILE"
        done

        # インデックスファイルの生成
        if [ -s "$TEMP_FILE" ]; then
            # 出力済みエントリを追跡する連想配列
            declare -A printed_dirs

            # ディレクトリを再帰的に処理する関数
            # $1: PAGES_DIR からの相対パス (ルートは空文字列)
            # $2: 現在の深さ (インデントレベル)
            # 各レベルで: 1. サブディレクトリ (昇順) → 2. 非 README ファイル (昇順) の順に出力
            process_directory() {
                local dir_rel="$1"
                local depth="$2"

                # インデントを計算
                local indent=""
                for ((j=0; j<depth; j++)); do
                    indent="    $indent"
                done

                # 対象ディレクトリの絶対パス
                local parent_dir
                if [ -z "$dir_rel" ]; then
                    parent_dir="$PAGES_DIR"
                else
                    parent_dir="$PAGES_DIR/$dir_rel"
                fi

                # 1. サブディレクトリを先に処理 (フォルダをファイルより前に出力)
                while IFS= read -r subdir; do
                    local subdir_name
                    subdir_name=$(basename "$subdir")
                    local subdir_rel
                    if [ -z "$dir_rel" ]; then
                        subdir_rel="$subdir_name"
                    else
                        subdir_rel="$dir_rel/$subdir_name"
                    fi

                    # .md ファイルが存在しない空ディレクトリはスキップ
                    if ! find "$PAGES_DIR/$subdir_rel" -type f -name "*.md" -print -quit | grep -q .; then
                        continue
                    fi

                    # README.md があるかチェック
                    local readme_path="$subdir_rel/README.md"
                    if [ -f "$PAGES_DIR/$readme_path" ]; then
                        local link_path="Pages/$readme_path"
                        local description
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
                        ' "$PAGES_DIR/$readme_path")
                        if [ -n "$description" ]; then
                            echo "${indent}* 📁 [${subdir_name}](${link_path}) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;${description}" >> "$INDEX_PAGES_FILE"
                        else
                            echo "${indent}* 📁 [${subdir_name}](${link_path})" >> "$INDEX_PAGES_FILE"
                        fi
                        printed_dirs[$readme_path]=1
                    else
                        echo "${indent}* 📁 ${subdir_name}" >> "$INDEX_PAGES_FILE"
                    fi
                    printed_dirs[$subdir_rel]=1

                    # 再帰的に処理
                    process_directory "$subdir_rel" $((depth + 1))
                done < <(find "$parent_dir" -mindepth 1 -maxdepth 1 -type d | LC_ALL=C sort)

                # 2. このディレクトリ直下の非 README .md ファイルを出力
                #    サブディレクトリの後に出力することでフォルダ後ファイルの順序を保証する
                #    find | LC_ALL=C sort によりファイル名昇順で挿入する
                while IFS= read -r md_file; do
                    local file_name
                    file_name=$(basename "$md_file")

                    local file_rel
                    if [ -z "$dir_rel" ]; then
                        file_rel="$file_name"
                    else
                        file_rel="$dir_rel/$file_name"
                    fi

                    # 出力済みはスキップ (ディレクトリリンクとして使用済みの README.md もここで除外される)
                    if [ -n "${printed_dirs[$file_rel]}" ]; then continue; fi

                    local description
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
                    ' "$md_file")
                    local link_path="Pages/$file_rel"
                    if [ -n "$description" ]; then
                        echo "${indent}* 📄 [${file_name}](${link_path}) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;${description}" >> "$INDEX_PAGES_FILE"
                    else
                        echo "${indent}* 📄 [${file_name}](${link_path})" >> "$INDEX_PAGES_FILE"
                    fi
                    printed_dirs[$file_rel]=1
                done < <(find "$parent_dir" -mindepth 1 -maxdepth 1 -type f -name "*.md" | LC_ALL=C sort)
            }

            # ルートディレクトリから再帰的に処理
            process_directory "" 0
        fi

        rm -f "$TEMP_FILE"
    fi

    echo "  Generated index_pages.md"
else
    echo "Warning: No INPUT directories found in Doxyfile"
fi

# 一時ファイルをクリーンアップ
if [ -n "$TEMP_DOXYFILE" ] && [ -f "$TEMP_DOXYFILE" ]; then
    rm -f "$TEMP_DOXYFILE"
fi

exit 0
