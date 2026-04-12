#!/bin/bash

# Doxygen の warning 専用ログを着色して表示する

RED='\033[0;31m'
YELLOW='\033[0;33m'
RESET='\033[0m'

while IFS= read -r line; do
    clean_line=$(printf '%s' "$line" | tr -d '\r')

    if [ -z "$clean_line" ]; then
        continue
    fi

    if [[ "$clean_line" == *"is ambiguous"* ]]; then
        printf '%b%s%b\n' "${RED}" "${clean_line}" "${RESET}"
    else
        printf '%b%s%b\n' "${YELLOW}" "${clean_line}" "${RESET}"
    fi
done < <(tr '\r' '\n')
