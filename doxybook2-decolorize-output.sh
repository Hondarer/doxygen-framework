#!/bin/bash
# Doxybook2 出力から過剰な着色を除去するフィルタースクリプト
# [info] を完全脱色、[warning] / [error] / [critical] の太字を除去

# 標準入力から1行ずつ読み取り、脱色・調整して出力
while IFS= read -r line; do
    if [[ "$line" == *"[info]"* ]]; then
        # [info] 行から全ての ANSI エスケープコードを削除
        echo "$line" | sed 's/\x1b\[[0-9;]*m//g'
    elif [[ "$line" == *"[critical]"* ]]; then
        # [critical] 行から全ての ANSI エスケープコードを削除して赤色で出力
        cleaned=$(echo "$line" | sed 's/\x1b\[[0-9;]*m//g')
        echo -e "\033[0;31m${cleaned}\033[0m"
    elif [[ "$line" == *"[warning]"* ]] || [[ "$line" == *"[error]"* ]]; then
        # [warning] / [error] 行の太字コードを通常の太さに変換
        # \033[1;XX → \033[0;XX
        echo "$line" | sed 's/\x1b\[1;/\x1b[0;/g'
    else
        # その他の行はそのまま出力
        echo "$line"
    fi
done
