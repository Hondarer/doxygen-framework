SHELL := /bin/bash

# この makefile のディレクトリ (絶対パス) を取得
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
INPUT_FILTER_ABS := $(MAKEFILE_DIR)/input-filter.py
DOXY_WARNING_COLORIZE := $(MAKEFILE_DIR)/bin/doxygen-warning-colorize-output.sh
EXTRACT_DOXY_WARNINGS := $(MAKEFILE_DIR)/bin/extract_doxy_warnings.sh

# ドキュメント大分類オプション (デフォルトは空)
CATEGORY ?=

# CATEGORY を環境変数としてエクスポート (postprocess.sh で使用)
export CATEGORY

# ガードファイル用の変数 (PID を含む一意なファイル名)
SKIP_MARKER_PID := $(shell echo $$$$)
SKIP_MARKER := /tmp/.skip_markdown_generation.$(SKIP_MARKER_PID)
export SKIP_MARKER

# CATEGORY に応じたパスの設定
ifneq ($(strip $(CATEGORY)),)
    CATEGORY_SUFFIX := /$(CATEGORY)
    DOXYGEN_WORKDIR := $(abspath ../../app/$(CATEGORY))
    DOXYFILE_PART := $(DOXYGEN_WORKDIR)/Doxyfile.part
else
    CATEGORY_SUFFIX :=
    DOXYGEN_WORKDIR := $(abspath ../../prod)
    DOXYFILE_PART := $(abspath ../../Doxyfile.part)
endif
export DOXYGEN_WORKDIR

ifneq ($(wildcard $(DOXYFILE_PART)),)
    DOXYFILE_PART_PATH := $(DOXYFILE_PART)
else
    DOXYFILE_PART_PATH :=
endif
export DOXYFILE_PART_PATH

DOCS_DOXYGEN_DIR := ../../pages/doxygen$(CATEGORY_SUFFIX)
DOCS_DOXYBOOK2_DIR := ../../docs/doxybook2$(CATEGORY_SUFFIX)
XML_DIR := ../../xml$(CATEGORY_SUFFIX)
XML_ORG_DIR := ../../xml_org$(CATEGORY_SUFFIX)
DOXY_WARN_OUTPUT := $(DOXYGEN_WORKDIR)/doxy.warn

.DEFAULT_GOAL := default

.PHONY: default
default: clean
# doxygen コマンドが存在しない場合は全体をスキップ
	@if ! command -v doxygen >/dev/null 2>&1; then \
		echo "Warning: doxygen command not found. Skipping documentation generation."; \
		exit 0; \
	fi
	mkdir -p $(DOCS_DOXYGEN_DIR)
	mkdir -p $(XML_DIR)
# Doxyfile.part がある場合は結合した一時 Doxyfile を作成
	@if [ -f "$(DOXYFILE_PART)" ]; then \
		echo "Merging $(DOXYFILE_PART)..."; \
		TEMP_DOXYFILE=$$(mktemp); \
		WARN_LOGFILE=$$(mktemp); \
		cat "$(MAKEFILE_DIR)/Doxyfile" "$(DOXYFILE_PART)" > $$TEMP_DOXYFILE || exit 1; \
		TEMP_DOXYFILE_MODIFIED=$$(mktemp); \
		: > "$$WARN_LOGFILE"; \
		rm -f "$(DOXY_WARN_OUTPUT)"; \
		if [ -n "$(CATEGORY)" ]; then \
			sed -e 's|^\(OUTPUT_DIRECTORY[[:space:]]*=\).*|\1 ../../pages/doxygen/$(CATEGORY)/|' \
			    -e 's|^\(XML_OUTPUT[[:space:]]*=\).*|\1 ../../../xml/$(CATEGORY)|' \
			    -e 's|^\(INPUT_FILTER[[:space:]]*=\).*|\1 "python3 $(INPUT_FILTER_ABS)"|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE|" \
			    $$TEMP_DOXYFILE > $$TEMP_DOXYFILE_MODIFIED || exit 1; \
		else \
			sed -e 's|^\(INPUT_FILTER[[:space:]]*=\).*|\1 "python3 $(INPUT_FILTER_ABS)"|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE|" \
			    $$TEMP_DOXYFILE > $$TEMP_DOXYFILE_MODIFIED || exit 1; \
		fi; \
		rm -f $$TEMP_DOXYFILE; \
		TEMP_DOXYFILE=$$TEMP_DOXYFILE_MODIFIED; \
		( cd "$(DOXYGEN_WORKDIR)" && doxygen $$TEMP_DOXYFILE > >("$(MAKEFILE_DIR)/doxygen-colorize-output.sh") ) & \
		DOXYGEN_PID=$$!; \
		tail --pid=$$DOXYGEN_PID -n +1 -f "$$WARN_LOGFILE" 2>/dev/null | "$(DOXY_WARNING_COLORIZE)" || true; \
		wait $$DOXYGEN_PID; \
		DOXYGEN_EXIT=$$?; \
		if [ -x "$(EXTRACT_DOXY_WARNINGS)" ]; then \
			"$(EXTRACT_DOXY_WARNINGS)" "$$WARN_LOGFILE" "$(DOXY_WARN_OUTPUT)"; \
		fi; \
		FATAL_WARNING=0; \
		if [ -s "$(DOXY_WARN_OUTPUT)" ] && grep -Fq "is ambiguous" "$(DOXY_WARN_OUTPUT)"; then \
			FATAL_WARNING=1; \
		fi; \
		rm -f "$$WARN_LOGFILE" "$$TEMP_DOXYFILE"; \
		if [ $$DOXYGEN_EXIT -ne 0 ]; then exit $$DOXYGEN_EXIT; fi; \
		exit $$FATAL_WARNING; \
	else \
		TEMP_DOXYFILE=$$(mktemp); \
		WARN_LOGFILE=$$(mktemp); \
		: > "$$WARN_LOGFILE"; \
		rm -f "$(DOXY_WARN_OUTPUT)"; \
		if [ -n "$(CATEGORY)" ]; then \
			sed -e 's|^\(OUTPUT_DIRECTORY[[:space:]]*=\).*|\1 ../../pages/doxygen/$(CATEGORY)/|' \
			    -e 's|^\(XML_OUTPUT[[:space:]]*=\).*|\1 ../../../xml/$(CATEGORY)|' \
			    -e 's|^\(INPUT_FILTER[[:space:]]*=\).*|\1 "python3 $(INPUT_FILTER_ABS)"|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE|" \
			    "$(MAKEFILE_DIR)/Doxyfile" > $$TEMP_DOXYFILE || exit 1; \
			( cd "$(DOXYGEN_WORKDIR)" && doxygen $$TEMP_DOXYFILE > >("$(MAKEFILE_DIR)/doxygen-colorize-output.sh") ) & \
			DOXYGEN_PID=$$!; \
			tail --pid=$$DOXYGEN_PID -n +1 -f "$$WARN_LOGFILE" 2>/dev/null | "$(DOXY_WARNING_COLORIZE)" || true; \
			wait $$DOXYGEN_PID; \
			DOXYGEN_EXIT=$$?; \
			if [ -x "$(EXTRACT_DOXY_WARNINGS)" ]; then \
				"$(EXTRACT_DOXY_WARNINGS)" "$$WARN_LOGFILE" "$(DOXY_WARN_OUTPUT)"; \
			fi; \
			FATAL_WARNING=0; \
			if [ -s "$(DOXY_WARN_OUTPUT)" ] && grep -Fq "is ambiguous" "$(DOXY_WARN_OUTPUT)"; then \
				FATAL_WARNING=1; \
			fi; \
			rm -f "$$WARN_LOGFILE" "$$TEMP_DOXYFILE"; \
			if [ $$DOXYGEN_EXIT -ne 0 ]; then exit $$DOXYGEN_EXIT; fi; \
			exit $$FATAL_WARNING; \
		else \
			sed -e 's|^\(INPUT_FILTER[[:space:]]*=\).*|\1 "python3 $(INPUT_FILTER_ABS)"|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE|" \
			    "$(MAKEFILE_DIR)/Doxyfile" > $$TEMP_DOXYFILE || exit 1; \
			( cd "$(DOXYGEN_WORKDIR)" && doxygen $$TEMP_DOXYFILE > >("$(MAKEFILE_DIR)/doxygen-colorize-output.sh") ) & \
			DOXYGEN_PID=$$!; \
			tail --pid=$$DOXYGEN_PID -n +1 -f "$$WARN_LOGFILE" 2>/dev/null | "$(DOXY_WARNING_COLORIZE)" || true; \
			wait $$DOXYGEN_PID; \
			DOXYGEN_EXIT=$$?; \
			if [ -x "$(EXTRACT_DOXY_WARNINGS)" ]; then \
				"$(EXTRACT_DOXY_WARNINGS)" "$$WARN_LOGFILE" "$(DOXY_WARN_OUTPUT)"; \
			fi; \
			FATAL_WARNING=0; \
			if [ -s "$(DOXY_WARN_OUTPUT)" ] && grep -Fq "is ambiguous" "$(DOXY_WARN_OUTPUT)"; then \
				FATAL_WARNING=1; \
			fi; \
			rm -f "$$WARN_LOGFILE" "$$TEMP_DOXYFILE"; \
			if [ $$DOXYGEN_EXIT -ne 0 ]; then exit $$DOXYGEN_EXIT; fi; \
			exit $$FATAL_WARNING; \
		fi; \
	fi

    # doxybook2 コマンドが存在しない場合、または処理対象がない場合は前処理～doxybook2～後処理をスキップ
	@rm -f $(SKIP_MARKER)
	@if ! command -v doxybook2 >/dev/null 2>&1; then \
		echo "Warning: doxybook2 command not found. Skipping Markdown generation."; \
		touch $(SKIP_MARKER); \
	elif [ ! -f "$(XML_DIR)/index.xml" ] || ! grep -q '<compound ' "$(XML_DIR)/index.xml"; then \
		echo "Info: No compound elements found in $(XML_DIR)/index.xml. Skipping Markdown generation."; \
		touch $(SKIP_MARKER); \
	fi
	@if [ ! -f $(SKIP_MARKER) ]; then \
		$(MAKE) markdown-generation; \
	else \
		rm -rf $(XML_DIR); \
	fi
	@rm -f $(SKIP_MARKER)

.PHONY: markdown-generation
markdown-generation:
	mkdir -p $(DOCS_DOXYBOOK2_DIR)
    # デバッグ用にオリジナルの xml をバックアップ
#	rm -rf $(XML_ORG_DIR)
#	mkdir -p $(XML_ORG_DIR)
#	cp -rp $(XML_DIR)/* $(XML_ORG_DIR)/
    # グラフ抽出 (XML のグラフ情報から PlantUML を生成し XML に挿入)
	python3 templates/extract-graphs.py $(XML_DIR) || exit 1
    # プリプロセッシング
	templates/preprocess.sh $(XML_DIR) || exit 1
    # xml -> md 変換
	@DOXYBOOK2_LOG=$$(mktemp); \
	doxybook2 \
		-i $(XML_DIR) \
		-o $(DOCS_DOXYBOOK2_DIR) \
		--config doxybook2-config.json \
		--templates templates 2>&1 | tee "$$DOXYBOOK2_LOG" | $(MAKEFILE_DIR)/doxybook2-decolorize-output.sh; \
	DOXYBOOK2_EXIT=$${PIPESTATUS[0]}; \
	if [ -x "$(EXTRACT_DOXY_WARNINGS)" ]; then \
		TEMP_WARN=$$(mktemp); \
		"$(EXTRACT_DOXY_WARNINGS)" "$$DOXYBOOK2_LOG" "$$TEMP_WARN"; \
		if [ -s "$$TEMP_WARN" ]; then \
			cat "$$TEMP_WARN" >> "$(DOXY_WARN_OUTPUT)"; \
		fi; \
		rm -f "$$TEMP_WARN"; \
	fi; \
	rm -f "$$DOXYBOOK2_LOG"; \
	if [ $$DOXYBOOK2_EXIT -ne 0 ]; then exit $$DOXYBOOK2_EXIT; fi
    # C# enum を Files ドキュメントに挿入
	python3 templates/inject-cs-enums.py $(XML_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # グループ (@defgroup) を Files ドキュメントに挿入
	python3 templates/inject-groups.py $(XML_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # 正常に変換できたら xml は不要なため削除
	rm -rf $(XML_DIR)
#	rm -rf $(XML_ORG_DIR)
    # rmdir コマンドは空のディレクトリのみを削除する
	@rmdir ../../xml 2>/dev/null || true
	@rmdir ../../xml_org 2>/dev/null || true
    # ポストプロセッシング
	templates/postprocess.sh $(DOCS_DOXYBOOK2_DIR) || exit 1

.PHONY: clean
clean:
	-rm -rf $(DOCS_DOXYGEN_DIR) $(DOCS_DOXYBOOK2_DIR) $(XML_DIR) $(XML_ORG_DIR)
    # rmdir コマンドは空のディレクトリのみを削除する
	@rmdir ../../pages/doxygen 2>/dev/null || true
	@rmdir ../../docs/doxybook2 2>/dev/null || true
	@rmdir ../../xml 2>/dev/null || true
	@rmdir ../../xml_org 2>/dev/null || true
