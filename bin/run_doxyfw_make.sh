#!/bin/bash

set -u

# GNU Make と同じ foreground process group で直接処理すると、Ctrl-C 時に
# make と本スクリプトが同時に終了し、EXIT trap の完了を待てない場合がある。
# Linux では実処理を独立セッションで起動し、外側のプロセスがシグナルを
# プロセス グループ全体へ転送して cleanup の完了まで待つ。
if [ "${DOXYFW_PROCESS_GROUP:-0}" != "1" ]; then
    case "$(uname -s 2>/dev/null)" in
        MINGW* | MSYS* | CYGWIN*) ;;
        *)
            if ! command -v setsid >/dev/null 2>&1; then
                echo "ERROR: setsid is required to manage the Doxygen process group on Linux." >&2
                exit 2
            fi

            doxyfw_group_pid=""
            forward_group_signal() {
                local sig="$1"
                local exit_code="$2"

                trap - INT TERM HUP
                if [ -n "$doxyfw_group_pid" ]; then
                    kill "-$sig" -- "-$doxyfw_group_pid" 2>/dev/null || true
                    wait "$doxyfw_group_pid" 2>/dev/null || true
                fi
                exit "$exit_code"
            }

            trap 'forward_group_signal TERM 130' INT
            trap 'forward_group_signal TERM 143' TERM
            trap 'forward_group_signal HUP 129' HUP
            DOXYFW_PROCESS_GROUP=1 setsid --wait "${BASH:-/bin/bash}" "$0" "$@" &
            doxyfw_group_pid="$!"
            if wait "$doxyfw_group_pid"; then
                doxyfw_group_exit=0
            else
                doxyfw_group_exit=$?
            fi
            trap - INT TERM HUP
            exit "$doxyfw_group_exit"
            ;;
    esac
fi

case "$(uname -s 2>/dev/null)" in
    MINGW* | MSYS* | CYGWIN*) doxyfw_is_windows=1 ;;
    *) doxyfw_is_windows=0 ;;
esac

run_tmp_root=""
lock_dir=""
cleanup_done=0
temp_doxyfile=""
warn_logfile=""
normalize_warn_log=""
normalize_warn_extract=""
dependency_warn_log=""
dependency_warn_extract=""
managed_child_pid=""

# Windows では bash がフォアグラウンドの子プロセスの終了までトラップの実行を
# 保留するため、doxygen などの長時間処理をフォアグラウンドで実行すると
# シグナルを受けても後処理を開始できない。バックグラウンドで起動して wait で
# 待つことで、シグナル受信時に即座にトラップを実行できるようにする。
# see: https://www.gnu.org/software/bash/manual/html_node/Signals.html
# Linux では setsid によるプロセス グループ配送が機能するため従来どおり
# フォアグラウンドで実行する。
run_interruptible() {
    local rc=0

    if [ "$doxyfw_is_windows" -eq 1 ]; then
        "$@" &
        managed_child_pid=$!
        wait "$managed_child_pid"
        rc=$?
        managed_child_pid=""
    else
        "$@"
        rc=$?
    fi
    return "$rc"
}

cleanup() {
    if [ "$cleanup_done" -eq 1 ]; then
        return 0
    fi
    cleanup_done=1

    # 管理下の子プロセスが実行中なら先に終了する。子プロセスが run_tmp_root
    # 配下のファイルを開いたままだと Windows では rm -rf が失敗するため、
    # 一時領域の削除より前に行う必要がある。
    if [ -n "$managed_child_pid" ] && kill -0 "$managed_child_pid" 2>/dev/null; then
        if [ "$doxyfw_is_windows" -eq 1 ] && command -v taskkill.exe >/dev/null 2>&1; then
            managed_child_winpid="$managed_child_pid"
            # MSYS の pid は Windows の pid と一致しない場合があるため変換する。
            # see: https://cygwin.com/cygwin-ug-net/proc.html
            if [ -r "/proc/$managed_child_pid/winpid" ]; then
                managed_child_winpid=$(cat "/proc/$managed_child_pid/winpid" 2>/dev/null || printf '%s' "$managed_child_pid")
            fi
            MSYS2_ARG_CONV_EXCL='*' taskkill.exe /PID "$managed_child_winpid" /T /F >/dev/null 2>&1 || true
        else
            kill -KILL "$managed_child_pid" 2>/dev/null || true
        fi
        wait "$managed_child_pid" 2>/dev/null || true
        managed_child_pid=""
    fi

    rm -f "$temp_doxyfile" "$warn_logfile" \
        "$normalize_warn_log" "$normalize_warn_extract" \
        "$dependency_warn_log" "$dependency_warn_extract"
    if [ -n "${SKIP_MARKER:-}" ]; then
        rm -f "$SKIP_MARKER"
    fi
    if [ -n "$lock_dir" ] && [ -d "$lock_dir" ]; then
        rmdir "$lock_dir" 2>/dev/null || true
    fi
    if [ -n "${DOXYFW_LOCK_ROOT:-}" ]; then
        rmdir "$DOXYFW_LOCK_ROOT" 2>/dev/null || true
    fi
    if [ -n "$run_tmp_root" ] && [ -d "$run_tmp_root" ]; then
        rm -rf "$run_tmp_root"
    fi
    if [ -n "${tmp_base_dir:-}" ]; then
        rmdir "$tmp_base_dir" 2>/dev/null || true
    fi
    if [ -n "${DOXYFW_TMP_ROOT:-}" ]; then
        rmdir "$DOXYFW_TMP_ROOT" 2>/dev/null || true
    fi
}

on_signal() {
    local signal_exit="$1"
    trap - INT TERM HUP
    exit "$signal_exit"
}

acquire_lock() {
    lock_path="$DOXYFW_LOCK_ROOT/$DOXYFW_RUNTIME_KEY.lock"
    mkdir -p "$DOXYFW_LOCK_ROOT"
    while ! mkdir "$lock_path" 2>/dev/null; do
        sleep 0.05
    done
    lock_dir="$lock_path"
}

to_doxygen_path() {
    path_value="$1"

    if command -v cygpath >/dev/null 2>&1; then
        cygpath -m "$path_value"
    else
        printf '%s\n' "$path_value"
    fi
}

replace_dir() {
    stage_dir="$1"
    final_dir="$2"
    parent_dir=$(dirname "$final_dir")
    backup_dir="$final_dir.doxyfw-old.$PPID.$RANDOM"

    if [ ! -d "$stage_dir" ]; then
        echo "ERROR: Staged Doxygen output does not exist: $stage_dir" >&2
        return 1
    fi

    mkdir -p "$parent_dir"
    rm -rf "$backup_dir"
    if [ -d "$final_dir" ]; then
        mv "$final_dir" "$backup_dir"
    fi
    if [ -d "$stage_dir" ]; then
        mv "$stage_dir" "$final_dir"
    fi
    rm -rf "$backup_dir"
}

replace_warn_file() {
    stage_file="$1"
    final_file="$2"

    if [ -s "$stage_file" ]; then
        mv "$stage_file" "$final_file"
    else
        rm -f "$final_file"
        rm -f "$stage_file"
    fi
}

parse_yaml_config_value() {
    config_file="$1"
    key="$2"

    if [ ! -f "$config_file" ]; then
        return
    fi

    awk -v k="$key" 'BEGIN { FS=":" } $1 == k { sub(/[ \t]*#.*$/, "", $2); sub(/^[ \t]+/, "", $2); print $2; exit }' "$config_file"
}

remove_obsolete_outputs() {
    rm -rf "$DOCS_DOXYGEN_DIR" "$DOCS_DOXYBOOK2_DIR"
    rm -f "$DOXY_WARN_OUTPUT"
    if [ -n "$APP_DOCS_DIR" ]; then
        rmdir "$APP_DOCS_DIR" 2>/dev/null || true
    fi
    rmdir "$WORKSPACE_DIR/pages/doxygen" 2>/dev/null || true
    rmdir "$WORKSPACE_DIR/docs/doxybook2" 2>/dev/null || true
}

prepare_doxyfile() {
    local input_doxyfile="$1"
    local output_file="$2"
    local warn_logfile_doxy="$3"
    local xml_work_dir_doxy="$4"
    local docs_doxygen_stage_dir_doxy="$5"

    sed -e "s|^\(OUTPUT_DIRECTORY[[:space:]]*=\).*|\1 $docs_doxygen_stage_dir_doxy/|" \
        -e "s|^\(XML_OUTPUT[[:space:]]*=\).*|\1 $xml_work_dir_doxy|" \
        -e "s|^\(GENERATE_TAGFILE[[:space:]]*=\).*|\1 $xml_work_dir_doxy/doxyfw.tag|" \
        -e "s|^\(INPUT_FILTER[[:space:]]*=\).*|\1 \"python3 $INPUT_FILTER_ABS\"|" \
        -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $warn_logfile_doxy|" \
        "$input_doxyfile" > "$output_file"
}

trap cleanup EXIT
trap 'on_signal 130' INT
trap 'on_signal 143' TERM
trap 'on_signal 129' HUP

tmp_base_dir="$DOXYFW_TMP_ROOT/$DOXYFW_RUNTIME_KEY"
mkdir -p "$tmp_base_dir"
run_tmp_root=$(mktemp -d "$tmp_base_dir/run.XXXXXX") || exit 1

xml_work_dir="$run_tmp_root/xml"
docs_doxygen_stage_dir="$run_tmp_root/doxygen"
docs_doxybook2_stage_dir="$run_tmp_root/doxybook2"
doxy_warn_stage="$run_tmp_root/$DOXY_WARN_BASENAME"

mkdir -p "$xml_work_dir" "$docs_doxygen_stage_dir"
rm -f "$doxy_warn_stage"

xml_work_dir_doxy=$(to_doxygen_path "$xml_work_dir")
docs_doxygen_stage_dir_doxy=$(to_doxygen_path "$docs_doxygen_stage_dir")

if ! command -v doxygen >/dev/null 2>&1; then
    echo "Warning: doxygen command not found. Skipping documentation generation."
    acquire_lock
    remove_obsolete_outputs
    exit 0
fi

if [ -f "$DOXYFILE_PART" ]; then
    echo "Merging $DOXYFILE_PART..."
    temp_doxyfile=$(mktemp)
    warn_logfile=$(mktemp)
    cat "$MAKEFILE_DIR/Doxyfile" "$DOXYFILE_PART" > "$temp_doxyfile" || exit 1
    temp_doxyfile_modified=$(mktemp)
    : > "$warn_logfile"
    warn_logfile_doxy=$(to_doxygen_path "$warn_logfile")
    prepare_doxyfile "$temp_doxyfile" "$temp_doxyfile_modified" "$warn_logfile_doxy" "$xml_work_dir_doxy" "$docs_doxygen_stage_dir_doxy" || exit 1
    rm -f "$temp_doxyfile"
    temp_doxyfile="$temp_doxyfile_modified"
else
    temp_doxyfile=$(mktemp)
    warn_logfile=$(mktemp)
    : > "$warn_logfile"
    warn_logfile_doxy=$(to_doxygen_path "$warn_logfile")
    prepare_doxyfile "$MAKEFILE_DIR/Doxyfile" "$temp_doxyfile" "$warn_logfile_doxy" "$xml_work_dir_doxy" "$docs_doxygen_stage_dir_doxy" || exit 1
fi

run_doxygen_pass() {
    (
        cd "$DOXYGEN_RUNDIR" &&
        doxygen "$temp_doxyfile" > >("$MAKEFILE_DIR/bin/doxygen-colorize-output.sh")
    )
}

run_interruptible run_doxygen_pass
doxygen_exit=$?
"$DOXY_WARNING_COLORIZE" < "$warn_logfile" || true
if [ -x "$EXTRACT_DOXY_WARNINGS" ]; then
    "$EXTRACT_DOXY_WARNINGS" "$warn_logfile" "$doxy_warn_stage"
fi
fatal_warning=0
if [ -s "$doxy_warn_stage" ] && grep -Fq "is ambiguous" "$doxy_warn_stage"; then
    fatal_warning=1
fi
rm -f "$warn_logfile" "$temp_doxyfile"
if [ $doxygen_exit -ne 0 ]; then
    exit $doxygen_exit
fi
if [ $fatal_warning -ne 0 ]; then
    exit $fatal_warning
fi

if [ -f "$xml_work_dir/index.xml" ] && grep -q '<compound ' "$xml_work_dir/index.xml"; then
    normalize_warn_log=$(mktemp)
    normalize_warn_extract=$(mktemp)
    python3 "$FUNCTION_REFERENCE_NORMALIZER" "$xml_work_dir" 2> "$normalize_warn_log"
    normalize_exit=$?
    if [ -s "$normalize_warn_log" ]; then
        "$DOXY_WARNING_COLORIZE" < "$normalize_warn_log" || true
    fi
    if [ -x "$EXTRACT_DOXY_WARNINGS" ]; then
        "$EXTRACT_DOXY_WARNINGS" "$normalize_warn_log" "$normalize_warn_extract"
        if [ -s "$normalize_warn_extract" ]; then
            cat "$normalize_warn_extract" >> "$doxy_warn_stage"
        fi
    fi
    rm -f "$normalize_warn_log" "$normalize_warn_extract"
    if [ $normalize_exit -ne 0 ]; then
        exit $normalize_exit
    fi

    dependency_warn_log=$(mktemp)
    dependency_warn_extract=$(mktemp)
    # 対象 Doxyfile.part の所在ディレクトリを渡し、その所属 Git のブランチ名と
    # コミット ハッシュを対象欄へ付加する (Git 管理下でない場合は非表示)。
    dependency_source_dir=""
    if [ -f "$DOXYFILE_PART" ]; then
        dependency_source_dir=$(dirname "$DOXYFILE_PART")
    fi
    dependency_git_link_host_provider=$(parse_yaml_config_value "$WORKSPACE_DIR/.vscode/git_link.yaml" "gitLinkHostProvider")
    export GIT_LINK_HOST_PROVIDER="$dependency_git_link_host_provider"
    python3 "$DEPENDENCY_REPORT_GENERATOR" "$xml_work_dir" "$docs_doxygen_stage_dir/dependency" "$CATEGORY_ID" "$dependency_source_dir" "$DEPENDENCY_PAGE_TEMPLATE" "$DEPENDENCY_PAGE_LANGS" 2> "$dependency_warn_log"
    dependency_report_exit=$?
    if [ -s "$dependency_warn_log" ]; then
        "$DOXY_WARNING_COLORIZE" < "$dependency_warn_log" || true
    fi
    if [ -x "$EXTRACT_DOXY_WARNINGS" ]; then
        "$EXTRACT_DOXY_WARNINGS" "$dependency_warn_log" "$dependency_warn_extract"
        if [ -s "$dependency_warn_extract" ]; then
            cat "$dependency_warn_extract" >> "$doxy_warn_stage"
        fi
    fi
    rm -f "$dependency_warn_log" "$dependency_warn_extract"
    if [ $dependency_report_exit -ne 0 ]; then
        exit $dependency_report_exit
    fi
fi

rm -f "$SKIP_MARKER"
if ! command -v doxybook2 >/dev/null 2>&1; then
    echo "Warning: doxybook2 command not found. Skipping Markdown generation."
    touch "$SKIP_MARKER"
elif [ ! -f "$xml_work_dir/index.xml" ] || ! grep -q '<compound ' "$xml_work_dir/index.xml"; then
    echo "Info: No compound elements found in $xml_work_dir/index.xml. Skipping Markdown generation."
    touch "$SKIP_MARKER"
fi

run_markdown_make() {
    "$MARKDOWN_MAKE" -C "$MAKEFILE_DIR" markdown-generation \
        DOXYFW_XML_WORK_DIR="$xml_work_dir" \
        DOCS_DOXYBOOK2_DIR="$docs_doxybook2_stage_dir" \
        DOXY_WARN_OUTPUT="$doxy_warn_stage"
}

if [ ! -f "$SKIP_MARKER" ]; then
    run_interruptible run_markdown_make
    markdown_exit=$?
    if [ $markdown_exit -ne 0 ]; then
        exit $markdown_exit
    fi
else
    rm -rf "$docs_doxybook2_stage_dir"
    rm -rf "$xml_work_dir"
fi
rm -f "$SKIP_MARKER"

# 公開置換の途中でシグナルの trap が実行されると、退避の mv と差し替えの
# mv の間で中断した場合に、公開済み出力が退避ディレクトリに残ったまま
# 公開先から消失する。置換の区間ではシグナルを記録するだけにとどめ、
# 置換の完了後に改めて処理する。区間の内容は mv と rm だけであり、
# 短時間で完了するため中断の応答性への影響は小さい。
publish_pending_signal=""
trap 'publish_pending_signal=130' INT
trap 'publish_pending_signal=143' TERM
trap 'publish_pending_signal=129' HUP
acquire_lock
replace_dir "$docs_doxygen_stage_dir" "$DOCS_DOXYGEN_DIR" || exit $?
if [ -d "$docs_doxybook2_stage_dir" ]; then
    replace_dir "$docs_doxybook2_stage_dir" "$DOCS_DOXYBOOK2_DIR" || exit $?
else
    rm -rf "$DOCS_DOXYBOOK2_DIR"
fi
replace_warn_file "$doxy_warn_stage" "$DOXY_WARN_OUTPUT"
if [ -n "$APP_DOCS_DIR" ]; then
    rmdir "$APP_DOCS_DIR" 2>/dev/null || true
fi
trap 'on_signal 130' INT
trap 'on_signal 143' TERM
trap 'on_signal 129' HUP
if [ -n "$publish_pending_signal" ]; then
    on_signal "$publish_pending_signal"
fi
