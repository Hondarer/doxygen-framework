#!/bin/bash
# Doxygen 出力を着色するフィルタースクリプト
# エラーを赤、ワーニングを黄色で表示

# ANSI カラーコード
RED='\033[0;31m'
YELLOW='\033[0;33m'
RESET='\033[0m'

# 標準入力から1行ずつ読み取り、着色して出力
while IFS= read -r line; do
    if [[ "$line" == *" error: "* ]]; then
        # エラー行を赤で出力
        echo -e "${RED}${line}${RESET}"
    elif [[ "$line" == *" warning: "* ]]; then
        # ワーニング行を黄色で出力
        echo -e "${YELLOW}${line}${RESET}"
    else
        # その他の行はそのまま出力
        echo "$line"
    fi
done
