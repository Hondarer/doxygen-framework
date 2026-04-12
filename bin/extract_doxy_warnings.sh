#!/bin/bash

# make doxy 関連ログから warning 行のみを抽出して warn ファイルに保存する
# Extract warning lines from Doxygen / Doxybook2 logs and save them to a warn file.

set -u

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <log_file> <warn_file>" >&2
    exit 1
fi

log_file="$1"
warn_file="$2"
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

# CR を LF に正規化し、ANSI エスケープを除去して warning 行を抽出しやすくする。
tr '\r' '\n' < "$log_file" | sed 's/\x1b\[[0-9;]*[mK]//g' > "$tmpfile"

grep -E '(: warning:|: 警告:|\[warning\]|^Warning:|^警告:)' "$tmpfile" \
    | perl -pe 's#^.*?((?:/[^\s:]+)+(?:\:\d+)?: warning: .*)$#$1#; s#^.*?(([A-Za-z]:[\\\\/][^\s:]+)+(?:\:\d+)?: warning: .*)$#$1#' \
    | grep -Ev '^Warning: (doxygen|doxybook2) command not found\. Skipping ' \
    > "$warn_file" 2>/dev/null || true

if [ ! -s "$warn_file" ]; then
    rm -f "$warn_file"
fi
