#!/bin/bash
# Doxygen の通常出力を整形するフィルタースクリプト
# warning は WARN_LOGFILE 側で別表示するため、ここでは通常出力と error のみを扱う

# ANSI カラーコード
RED='\033[0;31m'
RESET='\033[0m'

# 標準入力の CR を LF に正規化してから 1 行ずつ読み取り、整形して出力
while IFS= read -r line; do
    if [[ "$line" == *" error: "* ]]; then
        # エラー行を赤で出力
        printf '%b%s%b\n' "${RED}" "${line}" "${RESET}"
    else
        # その他の行はそのまま出力
        printf '%s\n' "$line"
    fi
done < <(tr '\r' '\n')
