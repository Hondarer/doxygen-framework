#!/bin/bash

set -u

run_tmp_root=""
lock_dir=""

cleanup() {
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

trap cleanup EXIT HUP INT TERM

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

(
    cd "$DOXYGEN_RUNDIR" &&
    doxygen "$temp_doxyfile" > >("$MAKEFILE_DIR/bin/doxygen-colorize-output.sh")
)
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

if [ ! -f "$SKIP_MARKER" ]; then
    "$MARKDOWN_MAKE" -C "$MAKEFILE_DIR" markdown-generation \
        DOXYFW_XML_WORK_DIR="$xml_work_dir" \
        DOCS_DOXYBOOK2_DIR="$docs_doxybook2_stage_dir" \
        DOXY_WARN_OUTPUT="$doxy_warn_stage"
else
    rm -rf "$docs_doxybook2_stage_dir"
    rm -rf "$xml_work_dir"
fi
rm -f "$SKIP_MARKER"

acquire_lock
replace_dir "$docs_doxygen_stage_dir" "$DOCS_DOXYGEN_DIR"
if [ -d "$docs_doxybook2_stage_dir" ]; then
    replace_dir "$docs_doxybook2_stage_dir" "$DOCS_DOXYBOOK2_DIR"
else
    rm -rf "$DOCS_DOXYBOOK2_DIR"
fi
replace_warn_file "$doxy_warn_stage" "$DOXY_WARN_OUTPUT"
if [ -n "$APP_DOCS_DIR" ]; then
    rmdir "$APP_DOCS_DIR" 2>/dev/null || true
fi
