#!/bin/bash

# postprocess.sh - Doxybook2 後処理スクリプト
# 使用方法: ./postprocess.sh <markdown_directory>
# 例: ./postprocess.sh docs-src/doxybook2

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
            local include_heading_offset=0
            
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
                # Classes/ のページをインクルードする場合、
                # Files/ でも Namespaces/ でも見出し階層は同じ構造のため、
                # 常に 2 段下げて埋め込み先の ### クラス名 に揃える。
                # (H2 → H4、H3 → H5 など)
                # ※ Classes 側ファイルそのものは変更しない。
                if [[ "$include_file" == Classes/*.md ]]; then
                    include_heading_offset=2
                fi
                #echo "  -> インクルード: $include_file"
                # YAML フロントマター、HTML コメント行、H1 見出しを除いてファイル内容を出力
                # (インクルード先はファイルルート Markdown のため、埋め込み時にヘッダー部分を除去する)
                awk '
                BEGIN { in_frontmatter = 0; frontmatter_done = 0; h1_removed = 0 }
                NR==1 && /^---[[:space:]]*$/ { in_frontmatter = 1; next }
                in_frontmatter && /^---[[:space:]]*$/ { in_frontmatter = 0; frontmatter_done = 1; next }
                in_frontmatter { next }
                frontmatter_done && !h1_removed && /^<!--/ { next }
                frontmatter_done && !h1_removed && /^# / { h1_removed = 1; next }
                { print }
                ' "$include_path" | \
                awk -v heading_offset="$include_heading_offset" '
                {
                    if (heading_offset > 0 && match($0, /^(#{1,6})[[:space:]]+/, m)) {
                        level = length(m[1])
                        new_level = level + heading_offset
                        if (new_level > 6) {
                            new_level = 6
                        }
                        hash = ""
                        for (i = 0; i < new_level; i++) {
                            hash = hash "#"
                        }
                        rest = substr($0, RLENGTH + 1)
                        print hash " " rest
                        next
                    }
                    print
                }
                '
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
    # コードフェンス・LaTeX ブロック数式前の改行不足対策
    # Doxybook2 が以下のケースでテキストと数式/コードを同一行に連結する問題を修正する。
    #
    # (1) コードフェンス: テキストに続いて ```lang が同一行にある場合、間に空行を挿入。
    #     ※ !dunder! 変換より先に実行しないと、テキスト+コードフェンスが同一行のまま
    #       !dunder! 変換の split 処理に渡されてコードフェンスが破壊されるため、
    #       この awk を先に配置する。
    #
    # (2) LaTeX ブロック数式 \[: テキストに続いて \[ が同一行にある場合、
    #     テキスト → 空行 → \[ → (同行に数式内容が続く場合は次行に分離) と出力する。
    awk '
    BEGIN { in_code_block = 0 }
    /^[[:space:]]*```/ {
        if (in_code_block) { in_code_block = 0 } else { in_code_block = 1 }
        print
        next
    }
    !in_code_block && match($0, /[[:space:]]*```[a-zA-Z0-9]/) && RSTART > 1 {
        text = substr($0, 1, RSTART - 1)
        fence = substr($0, RSTART)
        sub(/^[[:space:]]*/, "", fence)
        sub(/[[:space:]]*$/, "", text)
        print text
        print ""
        print fence
        in_code_block = 1
        next
    }
    !in_code_block && !($0 ~ /^[[:space:]]*\\\[/) && match($0, /\\\[/) {
        # \[ が行頭以外にある: 前のテキストと \[ を分離し空行を挿入
        text = substr($0, 1, RSTART - 1)
        rest = substr($0, RSTART + RLENGTH)
        sub(/[[:space:]]*$/, "", text)
        # rest のインデントは LaTeX 数式の可読性のため保持する (先頭空白を除去しない)
        print text
        print ""
        if (rest ~ /[^[:space:]]/) {
            # \[ の後に数式内容が続く場合は \[ と内容を別行に分離
            print "\\["
            print rest
        } else {
            print "\\["
        }
        next
    }
    { print }
    ' | \
    # !dunder! を __ に変換 (preprocess.sh で保護した __ を復元)
    # コードブロックの種別に応じて変換先を切り替える。
    # - PlantUML コードブロック内: !dunder! と __ の両方を ~_~_ に変換
    #   PlantUML では __ がアンダーライン記法として解釈されるため、
    #   ~ (エスケープ文字) で1文字ずつエスケープする。
    # - 通常コードブロック内 (cpp など): !dunder! を __ に復元
    # - コードブロック外:
    #   - インラインコード (`...`) 内: !dunder! を __ に復元 (エスケープ不要)
    #   - インラインコード外: !dunder! を &#95;&#95; にエスケープ (Markdown 強調記法を防ぐ)
    #     テキストに直接 __ が残る場合も同様にエスケープする。
    #   awk の gsub では & がマッチ全体を表すため &#95; は \&#95; と記述する。
    awk '
    /^[[:space:]]*```/ {
        if (in_code_block) { in_code_block = 0; is_plantuml = 0 }
        else { in_code_block = 1; is_plantuml = ($0 ~ /```[[:space:]]*plantuml/) }
        print; next
    }
    in_code_block && is_plantuml { gsub(/!dunder!/, "~_~_"); gsub(/__/, "~_~_") }
    in_code_block && !is_plantuml { gsub(/!dunder!/, "__") }
    !in_code_block {
        # バッククォートで分割し、インラインコード内外を区別して処理する
        # split はバッククォートを区切りとして除去するため、偶数インデックスが
        # インラインコード内 (バッククォアペアの間)、奇数が外側テキストとなる
        n = split($0, parts, /`/)
        result = ""
        for (i = 1; i <= n; i++) {
            if (i % 2 == 1) {
                # インラインコード外: __ を &#95;&#95; にエスケープ
                part = parts[i]
                gsub(/!dunder!/, "\\&#95;\\&#95;", part)
                gsub(/__/, "\\&#95;\\&#95;", part)
                # $\ 以外の $ を \$ にエスケープ (Pandoc の tex_math_dollars 誤認識防止)
                # awk に先読み否定がないため、$\ を一時マーカーで保護してから残りをエスケープし、
                # 最後にマーカーを $\ に戻す。
                # LaTeX コマンドは $\ で始まる形式 ($\sum 等) のため除外される。
                gsub(/\$\\/, "!latexdollar!", part)
                gsub(/\$/, "\\$", part)
                gsub(/!latexdollar!/, "$\\", part)
                result = result part
            } else {
                # インラインコード内: !dunder! を __ に復元するだけ
                part = parts[i]
                gsub(/!dunder!/, "__", part)
                result = result "`" part "`"
            }
        }
        print result
        next
    }
    { print }
    ' | \

    # コードフェンス内のポインタ型スペース除去
    # Doxygen の XML には型とポインタのスペースが複数の形で出現するため、それぞれ正規化する。
    #   パス0: "型(* 変数名)" → "型 (*変数名)"
    #          Doxygen が <definition> に "typedef int(* func_t)" のように出力するケース。
    #   パス1: "型*+ 変数名" → "型 *+変数名"
    #          Doxygen が <definition> に "typedef void* TYPEDEF_VOID" や
    #          "typedef void** TYPEDEF_VOID_PP" のように出力するケース。
    #          ※ [a-zA-Z_0-9] に限定することで "(* name)" のような関数ポインタ構文を除外する。
    #   パス2: "型 * 変数名" → "型 *変数名"
    #          Doxygen が型 ("int *") と変数名 ("b") を別々に XML 出力し
    #          Doxybook2 テンプレートで "int * b" のように結合されるケース。
    # コードフェンス内のみに適用し、文字列リテラル ("...") 内はスキップする。
    # ※ inja の文字列末尾チェック手段がないためテンプレート側では対処不可。
    #   (at() は文字列に使用不可、split() は末尾空トークンを除去する)
    awk '
    # 変換対象の文字列 s にポインタスペース正規化を適用して返す。
    # 文字列リテラル内 ("...") は変換しない前提で、s はリテラル外の断片を受け取る。
    function fix_ptr(s,    result, n_stars) {
        result = ""
        # パス0: "型(* 変数名)" → "型 (*変数名)" (関数ポインタ typedef の括弧前スペース正規化)
        # [^ ] で括弧前が既にスペースの場合はスキップし、二重スペースを防ぐ。
        while (match(s, /[^ ]\(\* [a-zA-Z_]/)) {
            result = result substr(s, 1, RSTART) " (*" substr(s, RSTART + 4, 1)
            s = substr(s, RSTART + RLENGTH)
        }
        s = result s
        result = ""
        # パス1: "型*+ 変数名" → "型 *+変数名" (アスタリスクが型に密着し後ろにスペースのケース)
        # \*+ でシングル/ダブルポインタ両方に対応する。
        while (match(s, /[a-zA-Z_0-9]\*+ [a-zA-Z_]/)) {
            n_stars = RLENGTH - 3
            result = result substr(s, 1, RSTART) " " substr(s, RSTART + 1, n_stars) substr(s, RSTART + n_stars + 2, 1)
            s = substr(s, RSTART + RLENGTH)
        }
        s = result s
        result = ""
        # パス2: "型 * 変数名" → "型 *変数名" (型とアスタリスクの間にスペースのケース)
        while (match(s, /\* [a-zA-Z_]/)) {
            result = result substr(s, 1, RSTART) substr(s, RSTART + 2, 1)
            s = substr(s, RSTART + RLENGTH)
        }
        return result s
    }
    /^[[:space:]]*```/ {
        if (in_code_block) { in_code_block = 0 } else { in_code_block = 1 }
        print; next
    }
    in_code_block {
        # ダブルクォートで分割し、リテラル外 (奇数インデックス) のみ fix_ptr を適用する。
        n = split($0, parts, "\"")
        line = ""
        for (i = 1; i <= n; i++) {
            if (i > 1) line = line "\""
            line = line (i % 2 == 1 ? fix_ptr(parts[i]) : parts[i])
        }
        print line
        next
    }
    { print }
    ' | \

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

    # Parameters セクション内の箇条書きネスト修正
    # Doxybook2 は @param の説明テキスト中の箇条書き (@param a 説明\n- 子項目) を
    # param.text に含めるが、インデントなしで展開するため、
    # パラメータのサブアイテムが最上位リストと同列になってしまう。
    # details.tmpl で付与した !paramitem! マーカーでパラメータ行を識別し、
    # マーカーのない * 行に 2 スペースインデントを追加して
    # 直前のパラメータ行の子リストとして正しくネストする。
    # また、パラメータ行とサブ箇条書きの間の空行は Markdown 上は問題ないが、
    # レンダリングの一貫性のためにここで除去する。
    awk '
    BEGIN { in_params_section = 0; in_param_item = 0; pending_blank = 0 }
    /^[[:space:]]*####[[:space:]]+引数[[:space:]]*$/ {
        in_params_section = 1; in_param_item = 0; pending_blank = 0
        print; next
    }
    in_params_section && /^[[:space:]]*####/ {
        in_params_section = 0; in_param_item = 0
        if (pending_blank) { print ""; pending_blank = 0 }
        print; next
    }
    in_params_section && /^\* !paramitem!/ {
        if (pending_blank) { print ""; pending_blank = 0 }
        in_param_item = 1
        sub(/!paramitem!/, "")
        print; next
    }
    in_params_section && in_param_item && /^[[:space:]]*$/ {
        pending_blank = 1; next
    }
    in_params_section && in_param_item && /^\* / {
        pending_blank = 0
        sub(/^\* /, "  * ")
        print; next
    }
    {
        if (pending_blank) { print ""; pending_blank = 0 }
        print
    }
    ' | \

    # #### 見出し前の空行確保
    # inja テンプレートの -%} による空白除去で #### 見出し直前の空行が
    # 失われる場合があるため、直前が空行でなければ空行を挿入する。
    awk '
    {
        if (/^[[:space:]]*####/ && NR > 1 && prev !~ /^[[:space:]]*$/) {
            print ""
        }
        print
        prev = $0
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
# ※ Enums/ はこの時点でまだ削除しない (!include 処理で参照するため)
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
# 画像は doxybook2 ルートの images/ に置かれるため、
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

# サブディレクトリ内 Markdown のファイル間リンクを削除
# Doxybook2 はクロスリファレンスを [text](Files/xxx.md#anchor) 形式で出力するが、
# サブフォルダ間の相対パスが正しくないため、テキストのみ残してリンクを除去する。
# 画像リンク ![text](url) は除外する。
# コードブロック内の [text](url) は変換しない。
# awk は後方参照が使えないため、ループで [text](url) → text に変換する。
for file in "${md_files[@]}"; do
    rel_path="${file#$MARKDOWN_DIR/}"
    if [[ "$rel_path" == */* ]]; then
        awk '
        /^[[:space:]]*```/ {
            if (in_code_block) { in_code_block = 0 } else { in_code_block = 1 }
            print; next
        }
        in_code_block { print; next }
        {
            line = $0
            result = ""
            while (length(line) > 0) {
                if (match(line, /!?\[[^]]*\]\([^)]*\)/)) {
                    before = substr(line, 1, RSTART - 1)
                    matched = substr(line, RSTART, RLENGTH)
                    line = substr(line, RSTART + RLENGTH)
                    if (substr(matched, 1, 1) == "!") {
                        # 画像リンク: そのまま保持
                        result = result before matched
                    } else {
                        # テキストリンク: テキストのみ抽出
                        paren_pos = index(matched, "](")
                        text = substr(matched, 2, paren_pos - 2)
                        result = result before text
                    }
                } else {
                    result = result line
                    line = ""
                }
            }
            print result
        }' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
    fi
done

# Enums/ (inject-cs-enums.py が生成した !include 用中間ファイル) を削除
# リンク除去ループの後に削除する (ループ内で Enums/*.md への .tmp 生成が必要なため)
find "$MARKDOWN_DIR" -name "Enums" -type d -exec rm -rf {} + 2>/dev/null || true

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
