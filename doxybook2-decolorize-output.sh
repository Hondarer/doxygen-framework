#!/bin/bash
# Doxybook2 出力から過剰な着色を除去するフィルタースクリプト
# [info] を完全脱色、[warning] / [error] / [critical] の太字を除去

# 標準入力から1行ずつ読み取り、脱色・調整して出力
while IFS= read -r line; do
    if [[ "$line" == *"[info]"* ]]; then
        # [info] 行から全ての ANSI エスケープコードを削除
        echo "$line" | sed 's/\x1b\[[0-9;]*m//g'
    elif [[ "$line" == *"[critical]"* ]]; then
        # [critical] の太字と背景色を除去し、通常の赤文字に変換
        # \033[1;41m → \033[0;31m (太字 + 赤背景 → 通常 + 赤文字)
        echo "$line" | sed 's/\x1b\[1;41m/\x1b[0;31m/g'
    elif [[ "$line" == *"[warning]"* ]] || [[ "$line" == *"[error]"* ]]; then
        # [warning] / [error] 行の太字コードを通常の太さに変換
        # \033[1;XX → \033[0;XX
        echo "$line" | sed 's/\x1b\[1;/\x1b[0;/g'
    else
        # その他の行はそのまま出力
        echo "$line"
    fi
done
