#!/bin/bash
# Doxygen の通常出力を整形するフィルタースクリプト
# warning は WARN_LOGFILE 側で別表示するため、ここでは通常出力と error のみを扱う

# ANSI カラーコード
RED='\033[0;31m'
RESET='\033[0m'

# 標準入力を 1 行ずつ読み取り、CRLF 入力時は行末の CR のみ除去して処理する
while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    if [[ "$line" == *" error: "* ]]; then
        # エラー行を赤で出力
        printf '%b%s%b\n' "${RED}" "${line}" "${RESET}"
    else
        # その他の行はそのまま出力
        printf '%s\n' "$line"
    fi
done
