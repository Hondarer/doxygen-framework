#!/bin/bash

# postprocess.sh - Doxybook2 後処理スクリプト
# 使用方法: ./postprocess.sh <markdown_directory>
# 例: ./postprocess.sh output/doxybook2

# set -x # デバッグ時のみ有効にする

# 引数チェック
if [ $# -ne 1 ]; then
    echo "使用方法: $0 <markdown_directory>"
    echo "例: $0 output/doxybook2"
    exit 1
fi

MARKDOWN_DIR="$1"

# ディレクトリの存在チェック
if [ ! -d "$MARKDOWN_DIR" ]; then
    echo "エラー: ディレクトリが存在しません: $MARKDOWN_DIR"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRAMEWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="${WORKSPACE_DIR:-$(cd "$FRAMEWORK_DIR/../.." && pwd)}"

# 一時ディレクトリを作成
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Doxyfile から PROJECT_NAME を抽出する
# 複数の PROJECT_NAME 行がある場合は最後の値 (Doxyfile.part が上書きした値) を採用する。
# 値が二重引用符で囲まれている場合は除去する。
extract_project_name_from_doxyfile() {
    local doxyfile="$1"

    if [ ! -f "$doxyfile" ]; then
        return 1
    fi

    awk '
        /^PROJECT_NAME[[:space:]]*=/ {
            sub(/^PROJECT_NAME[[:space:]]*=[[:space:]]*/, "")
            sub(/#.*/, "")
            gsub(/^[[:space:]]+|[[:space:]]+$/, "")
            gsub(/^"|"$/, "")
            last_value = $0
        }
        END {
            if (last_value) print last_value
        }
    ' "$doxyfile"
}

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
                # Modules/ のページをインクルードする場合、
                # 埋め込み先の ### グループタイトル (H3) 配下に揃えるため
                # 2 段下げる (H2 → H4、H3 → H5 など)。
                # ※ Modules 側ファイルそのものは変更しない。
                if [[ "$include_file" == Modules/*.md ]]; then
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
                    if (heading_offset > 0 && match($0, /^[[:space:]]*(#{1,6})[[:space:]]+/, m)) {
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
    # - summary が複数行に分割された場合は 1 行へ正規化
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
    awk '
    function trim_spaces(s) {
        gsub(/^[[:space:]]+/, "", s)
        gsub(/[[:space:]]+$/, "", s)
        return s
    }
    function append_summary(part) {
        part = trim_spaces(part)
        if (part == "") {
            return
        }
        if (summary_text == "") {
            summary_text = part
        } else {
            summary_text = summary_text " " part
        }
    }
    function flush_summary() {
        if (!summary_active) {
            return
        }
        safe = summary_text
        gsub(/\\/, "\\\\", safe)
        gsub(/"/, "\\\"", safe)
        print "summary: \"" safe "\""
        summary_active = 0
        summary_text = ""
    }
    BEGIN {
        in_frontmatter = 0
        summary_active = 0
        summary_text = ""
        line_count = 0
    }
    line_count == 0 && /^---[[:space:]]*$/ {
        in_frontmatter = 1
        print $0
        line_count++
        next
    }
    in_frontmatter && /^---[[:space:]]*$/ {
        flush_summary()
        in_frontmatter = 0
        print $0
        line_count++
        next
    }
    in_frontmatter {
        if (summary_active) {
            if ($0 ~ /^[[:space:]]*[A-Za-z0-9_-]+:[[:space:]]*/) {
                flush_summary()
                print $0
            } else {
                append_summary($0)
            }
            line_count++
            next
        }
        if ($0 ~ /^summary:[[:space:]]*/) {
            summary_active = 1
            summary_text = ""
            summary_line = $0
            sub(/^summary:[[:space:]]*/, "", summary_line)
            append_summary(summary_line)
            line_count++
            next
        }
        print $0
        line_count++
        next
    }
    {
        print $0
        line_count++
    }
    END {
        flush_summary()
    }
    ' | \

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
    # __DETAILS_ONLY__ マーカー付き見出しブロックを詳細タグで囲む
    # extract-graphs.py が details_only=True のグラフタイトルに付与した
    # "__DETAILS_ONLY__" プレフィックスを検出し、その見出しと plantuml
    # コードフェンスを <!--details:--> / <!--:details--> で囲む。
    awk '
    BEGIN { details_open = 0; in_fence = 0 }
    /^#{1,6}[[:space:]]+DOXYFW_DETAILS_ONLY[[:space:]]/ {
        sub(/DOXYFW_DETAILS_ONLY /, "")
        print "<!--details:-->"
        print
        details_open = 1
        next
    }
    /^```/ && details_open {
        if (in_fence) {
            print
            in_fence = 0
            print ""
            print "<!--:details-->"
            details_open = 0
        } else {
            in_fence = 1
            print
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
    #   - Markdown リンク URL ](url) 内: !dunder! を __ に復元 (URL 中の __ はエスケープしない)
    #   - インラインコード (`...`) 内: !dunder! を __ に復元 (エスケープ不要)
    #   - 上記以外のインラインコード外: !dunder! を &#95;&#95; にエスケープ (Markdown 強調記法を防ぐ)
    #     テキストに直接 __ が残る場合も同様にエスケープする。
    #   awk の gsub では & がマッチ全体を表すため &#95; は \&#95; と記述する。
    awk '
    function escape_text(s) {
        gsub(/!dunder!/, "\\&#95;\\&#95;", s)
        gsub(/__/, "\\&#95;\\&#95;", s)
        gsub(/\$\\/, "!latexdollar!", s)
        gsub(/\$/, "\\$", s)
        gsub(/!latexdollar!/, "$\\", s)
        return s
    }
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
                # ただし Markdown リンクの URL 部分 ](url) 内では __ を保持する
                text = parts[i]
                seg = ""
                while (length(text) > 0) {
                    if (match(text, /\]\([^)]*\)/)) {
                        seg = seg escape_text(substr(text, 1, RSTART - 1))
                        url_span = substr(text, RSTART, RLENGTH)
                        gsub(/!dunder!/, "__", url_span)
                        seg = seg url_span
                        text = substr(text, RSTART + RLENGTH)
                    } else {
                        seg = seg escape_text(text)
                        text = ""
                    }
                }
                result = result seg
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
        # [^ ] で括弧前がすでにスペースの場合はスキップし、二重スペースを防ぐ。
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
    /^[[:space:]]*#{1,6}[[:space:]]+引数[[:space:]]*$/ {
        in_params_section = 1; in_param_item = 0; pending_blank = 0
        print; next
    }
    in_params_section && /^[[:space:]]*#{1,6}[[:space:]]/ {
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
    ' | \

    # 見出し行のインラインコード（バッククォート）除去
    # # で始まる見出し行から `text` → text の変換を行う。
    # コードブロック内の見出し行は変換しない。
    awk '
    BEGIN { in_code_block = 0 }
    /^[[:space:]]*```/ { in_code_block = !in_code_block; print; next }
    !in_code_block && /^#{1,6} / {
        line = $0
        while (match(line, /`[^`]+`/)) {
            inner = substr(line, RSTART + 1, RLENGTH - 2)
            line = substr(line, 1, RSTART - 1) inner substr(line, RSTART + RLENGTH)
        }
        print line; next
    }
    { print }
    ' | \

    # !itembreak! を Markdown の改行 + 継続行インデントに変換
    # details.tmpl は項目名と説明文の間に !itembreak! を出力できるため、
    # ここで "  " を行末に付けた 1 行目と、2 文字インデント付きの 2 行目へ分割する。
    # Markdown 空白整理の前段で展開すると継続行インデントが削られるため、最終段で処理する。
    awk '
    {
        line = $0
        while (index(line, "!itembreak!") > 0) {
            marker_pos = index(line, "!itembreak!")
            head = substr(line, 1, marker_pos - 1)
            tail = substr(line, marker_pos + length("!itembreak!"))
            print head "  "
            line = "  " tail
        }
        print line
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
# - ディレクトリページ
# - ページインデックス
# - Pages
# - インデックスページ
rm -rf "$MARKDOWN_DIR"/Files/dir_*.md \
       "$MARKDOWN_DIR"/index_pages.md \
       "$MARKDOWN_DIR"/Pages \
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

# Files/ を実フォルダ構造へ再編
# (process_markdown_file ループ後に実施: !include 展開済みが前提)
python3 "$SCRIPT_DIR/restructure-files.py" "$MARKDOWN_DIR" || exit 1

# Files/ 再編後に md_files を再収集
# (画像パス補正・リンク除去ループが新しいネスト パスを対象にするため)
mapfile -t md_files < <(find "$MARKDOWN_DIR" -name "*.md" -type f)

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

# perfile__*.md / perchild__*.md (inject-groups.py が生成した !include 用中間ファイル) を削除
# Modules/group__*.md スタンドアロンページは保持し、perfile__* / perchild__* のみ削除する
find "$MARKDOWN_DIR" -path "*/Modules/perfile__*.md" -type f -delete 2>/dev/null || true
find "$MARKDOWN_DIR" -path "*/Modules/perchild__*.md" -type f -delete 2>/dev/null || true

# 内容が空の Namespaces/*.md を削除し、index_namespaces.md の該当エントリ行も除去する。
# 空 = フロントマター + 自動生成コメント + H1 見出しのみで本文がない名前空間
# (例: C# が参照するのみで本プロジェクトに文書化メンバーを持たない System::IO 等)。
# この処理を空フォルダ削除ループの前に実行することで、全エントリが空の場合に
# 既存ループがフォルダ + index ごと自動的に削除する動作と整合する。
if [ -d "$MARKDOWN_DIR/Namespaces" ]; then
    NS_INDEX="$MARKDOWN_DIR/index_namespaces.md"
    find "$MARKDOWN_DIR/Namespaces" -name 'namespace*.md' -type f | while IFS= read -r ns_file; do
        body=$(awk '
            NR == 1 && $0 == "---" { in_fm = 1; next }
            in_fm && $0 == "---"   { in_fm = 0; next }
            in_fm                  { next }
            /^<!--/                { next }
            /^#[[:space:]]/        { next }
            /^[[:space:]]*$/       { next }
            { print; exit }
        ' "$ns_file")
        if [ -z "$body" ]; then
            base=$(basename "$ns_file")
            rm -f "$ns_file"
            if [ -f "$NS_INDEX" ]; then
                esc_base=$(printf '%s' "$base" | sed 's/[.[\*^$/]/\\&/g')
                sed -i "/](Namespaces\/${esc_base})/d" "$NS_INDEX"
            fi
            echo "  Removed empty namespace: Namespaces/$base"
        fi
    done
fi

# 空の Namespaces / Classes / Modules / Examples フォルダを index ごと削除する。
# メンバー md を 1 つも含まないフォルダ (例: C のみのカテゴリーの名前空間・クラス) は
# 対応する index_*.md も中身が空になるため、両方とも削除する。
# Files は常に内容を持つ想定のため対象外。
# ※ フォルダ名と index 名の対応は一様でない (Modules ↔ index_groups.md)。
# ※ この処理は Enums/・perfile__*・perchild__* の中間ファイルをすべて削除した後に
#   実行することで、Modules/ に残るのが正規の group__*.md のみとなり正しく判定できる。
for pair in "Namespaces:index_namespaces.md" \
            "Classes:index_classes.md" \
            "Modules:index_groups.md" \
            "Examples:index_examples.md"; do
    dir_name="${pair%%:*}"
    index_name="${pair##*:}"
    dir_path="$MARKDOWN_DIR/$dir_name"
    if [ -d "$dir_path" ] && \
       [ -z "$(find "$dir_path" -name '*.md' -type f -print -quit)" ]; then
        rm -rf "$dir_path"
        rm -f "$MARKDOWN_DIR/$index_name"
        echo "  Removed empty $dir_name/ and $index_name"
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
# Markdown ファイルのコピー処理
# copy-markdown-from-input.sh を呼び出して INPUT からの Markdown をコピー
# (Pages/ ステージングと index_pages.md 生成を行う)
"$SCRIPT_DIR/copy-markdown-from-input.sh" "$MARKDOWN_DIR" || exit 1

# ファイルインデックスのパッチ
# Doxybook2 が出力するディレクトリ名・ファイル名は Doxygen INPUT ルートからの相対パス形式。
# 例: calc/include, calc/src/add/add.c
# merge-index-files.py でのマージ時に index_pages.md のローカル名と対応付けるため、
# patch-index-files.py によって末尾コンポーネントのみに変換する。
if [ -f "$MARKDOWN_DIR/index_files.md" ]; then
    python3 "$SCRIPT_DIR/patch-index-files.py" "$MARKDOWN_DIR/index_files.md" || exit 1
fi

# index_files.md と index_pages.md のマージ処理
# merge-index-files.py を呼び出してマージ結果を index_files.md へ上書きする
# (index_files_and_pages.md は生成しない)
python3 "$SCRIPT_DIR/merge-index-files.py" "$MARKDOWN_DIR" || exit 1

# Pages/ の内容を Files/ へ物理統合
# copy-markdown-from-input.sh が Pages/ へステージングした md と隣接画像を、
# Files/ 配下の同一相対パスへ移動する。両者はディレクトリ構造が一致し、
# ファイル名はユニーク (ソース由来は *.c.md 等、ページは README.md 等) という前提。
if [ -d "$MARKDOWN_DIR/Pages" ]; then
    echo "Merging Pages/ into Files/..."
    find "$MARKDOWN_DIR/Pages" -type f | while IFS= read -r src_file; do
        rel="${src_file#$MARKDOWN_DIR/Pages/}"
        dest_file="$MARKDOWN_DIR/Files/$rel"
        if [ -e "$dest_file" ]; then
            echo "  警告: 移動先が既に存在します (ユニーク前提違反): Files/$rel"
        else
            mkdir -p "$(dirname "$dest_file")"
            mv "$src_file" "$dest_file"
            echo "  Merged: Pages/$rel -> Files/$rel"
        fi
    done
    # 空になった Pages/ を削除し、後処理ファイルも削除
    rm -rf "$MARKDOWN_DIR/Pages"
    rm -f "$MARKDOWN_DIR/index_pages.md"
    # 統合時に生じた空ディレクトリを除去
    find "$MARKDOWN_DIR/Files" -type d -empty -delete 2>/dev/null || true
    echo "  Removed Pages/ and index_pages.md"
fi

# Pages→Files 統合後に md_files を再収集
# 画像分散配置ループが Pages 由来 md を含む Files/ 全体を対象にするため再収集する。
mapfile -t md_files < <(find "$MARKDOWN_DIR/Files" -name "*.md" -type f 2>/dev/null)

# サブディレクトリ内 Markdown の画像を分散配置
# Doxybook2 がルート images/ に出力した画像を各 md と同階層の images/ へ移動する。
# Pages→Files 統合後に実施することで、Pages 由来 md の参照画像も対象にできる。
#
# Doxybook2 はプロジェクト内で画像 basename を一意に管理するため、
# 同一画像を複数 md が参照する場合の考慮は Doxybook2 の制約として不要。
# mv で移動することで root images/ が空になり、処理後の削除を保証する。
#
# Pages 由来 md の画像は copy_referenced_images + Pages 統合で既に隣接 images/ に
# 配置済みの場合がある。移動先に既存なら root 側を削除して root を確実に空にする。

DOXYBOOK2_IMAGES_DIR="$MARKDOWN_DIR/images"

if [ -d "$DOXYBOOK2_IMAGES_DIR" ]; then
    for file in "${md_files[@]}"; do
        rel_path="${file#$MARKDOWN_DIR/}"
        # スラッシュが含まれる = サブディレクトリ内のファイル
        if [[ "$rel_path" == */* ]] && grep -qE '!\[[^]]*\]\([^)]+\)' "$file" 2>/dev/null; then
            file_dir="$(dirname "$file")"
            local_images_dir="$file_dir/images"

            # 参照画像の basename を収集し、Doxybook2 ルート images/ から各 md の隣接へ移動
            # 既に隣接 images/ に配置済みなら root 側を削除して root を確実に空にする
            while IFS= read -r img_name; do
                [ -z "$img_name" ] && continue
                if [ -f "$DOXYBOOK2_IMAGES_DIR/$img_name" ]; then
                    mkdir -p "$local_images_dir"
                    if [ ! -f "$local_images_dir/$img_name" ]; then
                        mv "$DOXYBOOK2_IMAGES_DIR/$img_name" "$local_images_dir/$img_name"
                        echo "  Moved image: $img_name -> ${rel_path%/*}/images/"
                    else
                        # 配置済み (Pages 統合で既に存在) → root 側を削除して root を空にする
                        rm "$DOXYBOOK2_IMAGES_DIR/$img_name"
                        echo "  Removed from root (already placed): $img_name"
                    fi
                fi
            done < <(
                grep -oE '!\[[^]]*\]\([^)]+\)' "$file" | \
                    grep -Ev '\(https?://' | \
                    sed -E 's/!\[[^]]*\]\(([^/)]*\/)*([^/)?# ]+)\).*/\2/'
            )

            # 画像パスを images/<name> に正規化 (ディレクトリ部分を除去) し、
            # キャプション補正 (![filename](url)caption → ![caption](url)) も適用。
            # - ディレクトリ部分を strip して images/{basename} に統一
            # - Doxybook2 は @image html のキャプションを ) 直後にスペースなしで連結する
            sed -i -E \
                -e 's/!\[([^]]*)\]\(([^/)]*\/)*([^/)?# ]+)\)/![\1](images\/\3)/g' \
                -e 's/!\[[^]]*\]\(([^)]+)\)([^ ].*)/![\2](\1)/g' \
                "$file"
        fi
    done

    # 分散配置後に root images/ が空になっていれば削除
    if [ -z "$(find "$DOXYBOOK2_IMAGES_DIR" -maxdepth 1 -type f -print -quit)" ]; then
        rm -rf "$DOXYBOOK2_IMAGES_DIR"
        echo "  Removed empty root images/ directory"
    fi
fi

# PROJECT_NAME を merged Doxyfile から取得する (mainpage README タイトル置換用)
# DOXYFILE_PART_PATH が設定されていればベース Doxyfile と結合し、なければベースのみを参照する。
DOXYFW_PROJECT_NAME=""
if [ -n "$DOXYFILE_PART_PATH" ] && [ -f "$DOXYFILE_PART_PATH" ]; then
    _pn_temp=$(mktemp)
    cat "$FRAMEWORK_DIR/Doxyfile" "$DOXYFILE_PART_PATH" > "$_pn_temp"
    DOXYFW_PROJECT_NAME=$(extract_project_name_from_doxyfile "$_pn_temp")
    rm -f "$_pn_temp"
else
    DOXYFW_PROJECT_NAME=$(extract_project_name_from_doxyfile "$FRAMEWORK_DIR/Doxyfile")
fi

# mainpage README (Files/README.md) を出力フォルダ直下へ移動する。
# README は元々 Files/ 直下にあり相対リンクは Files/ 基準で解決されていたため、
# ルートへ移動後も同じ先を指すよう、Files/ 内の実ファイルを指す相対リンクには
# Files/ を前置する (テキスト リンク・画像リンク両方が対象)。
# URL・絶対パス・アンカーのみ・既に Files/ で始まるものは対象外。
README_SRC="$MARKDOWN_DIR/Files/README.md"
if [ -f "$README_SRC" ]; then
    while IFS= read -r target; do
        [ -z "$target" ] && continue
        path="${target%%[?#]*}"     # アンカー/クエリを除いたパス部
        [ -z "$path" ] && continue  # 純アンカー (#...) は対象外
        case "$path" in
            http://*|https://*|/*|mailto:*|Files/*) continue ;;
        esac
        if [ -f "$MARKDOWN_DIR/Files/$path" ]; then
            esc_t=$(printf '%s' "$target" | sed 's/[&/\]/\\&/g')
            sed -i "s|](${esc_t})|](Files/${esc_t})|g" "$README_SRC"
        fi
    done < <(grep -oE '\]\([^)]+\)' "$README_SRC" | sed -E 's/^\]\(([^)]+)\)$/\1/')
    mv "$README_SRC" "$MARKDOWN_DIR/README.md"
    echo "  Moved Files/README.md -> README.md"
    # mainpage README の先頭 H1 を PROJECT_NAME に置換する
    # PROJECT_NAME が空またはベース既定値 Doxygen の場合は置換しない
    if [ -n "$DOXYFW_PROJECT_NAME" ] && [ "$DOXYFW_PROJECT_NAME" != "Doxygen" ]; then
        _readme_tmp=$(mktemp "$TEMP_DIR/readme.XXXXXX")
        awk -v t="$DOXYFW_PROJECT_NAME" '
        BEGIN { done = 0 }
        !done && /^# / { print "# " t; done = 1; next }
        { print }
        ' "$MARKDOWN_DIR/README.md" > "$_readme_tmp" && mv "$_readme_tmp" "$MARKDOWN_DIR/README.md"
        echo "  Updated README.md title: $DOXYFW_PROJECT_NAME"
    fi
fi

# ファイル一覧 (index_files.md) からホーム README のエントリ行を削除する。
# ホームは出力フォルダ直下に配置するため、一覧に重複して載せない。
# mainpage は必ず "Files/README.md"。サブディレクトリ README は
# "Files/src/README.md" 等のため、この厳密一致では誤って消えない。
if [ -f "$MARKDOWN_DIR/index_files.md" ]; then
    sed -i '/\](Files\/README\.md)/d' "$MARKDOWN_DIR/index_files.md"
fi

# フォルダ目次 README.md のフロントマターから不要キーを除去する
# - page-break-before-heading: true は全ページに付与されるが、フォルダ目次では不要
# - toc: true は Classes/Namespaces インデックスに付与されるが、フォルダ目次では不要
strip_folder_index_frontmatter() {
    local readme="$1"
    [ -f "$readme" ] || return 0
    sed -i -e '/^page-break-before-heading:[[:space:]]*true[[:space:]]*$/d' \
           -e '/^toc:[[:space:]]*true[[:space:]]*$/d' \
           "$readme"
}

# 各 index 一覧を対応フォルダの README.md (フォルダの目次) へ移動する。
# フォルダ内ページを指すリンクはフォルダ基準へ変換するため先頭の "<フォルダ>/" を除去する
# (例: ](Files/include/calc.h.md) -> ](include/calc.h.md))。
# ※ 空の Namespaces/Classes/Modules/Examples は前段で index ごと削除済みのため、
#   ここで存在する index は非空フォルダのものに限られる。
move_index_to_folder_readme() {
    local index_name="$1" folder="$2"
    local index_path="$MARKDOWN_DIR/$index_name"
    [ -f "$index_path" ] || return 0
    mkdir -p "$MARKDOWN_DIR/$folder"
    sed -i "s|](${folder}/|](|g" "$index_path"
    mv "$index_path" "$MARKDOWN_DIR/$folder/README.md"
    strip_folder_index_frontmatter "$MARKDOWN_DIR/$folder/README.md"
    echo "  Moved $index_name -> $folder/README.md"
}
move_index_to_folder_readme "index_files.md"      "Files"
move_index_to_folder_readme "index_groups.md"     "Modules"
move_index_to_folder_readme "index_namespaces.md" "Namespaces"
move_index_to_folder_readme "index_examples.md"   "Examples"

# index_classes.md は名前空間でグルーピングされ Namespaces/ へのフォルダ外リンクを
# 親行に含む。名前空間は Namespaces/README.md に一覧があるためグルーピング行を削除し、
# 残るクラス項目をフラット化したうえで Classes/ 接頭辞を除去して Classes/README.md とする。
CLASSES_INDEX="$MARKDOWN_DIR/index_classes.md"
if [ -f "$CLASSES_INDEX" ]; then
    mkdir -p "$MARKDOWN_DIR/Classes"
    awk '
        /\]\(Namespaces\// { next }
        {
            if (match($0, /^[[:space:]]*\* /)) { sub(/^[[:space:]]+/, "") }
            gsub(/\]\(Classes\//, "](")
            print
        }
    ' "$CLASSES_INDEX" > "$CLASSES_INDEX.tmp" && mv "$CLASSES_INDEX.tmp" "$CLASSES_INDEX"
    mv "$CLASSES_INDEX" "$MARKDOWN_DIR/Classes/README.md"
    strip_folder_index_frontmatter "$MARKDOWN_DIR/Classes/README.md"
    echo "  Moved index_classes.md -> Classes/README.md"
fi

# 処理終了
exit 0
