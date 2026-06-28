SHELL := /bin/bash

# この makefile のディレクトリ (絶対パス) を取得
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
WORKSPACE_DIR ?= $(abspath $(MAKEFILE_DIR)/../..)
INPUT_FILTER_ABS := $(MAKEFILE_DIR)/bin/input-filter.py
DOXY_WARNING_COLORIZE := $(MAKEFILE_DIR)/bin/doxygen-warning-colorize-output.sh
EXTRACT_DOXY_WARNINGS := $(MAKEFILE_DIR)/bin/extract_doxy_warnings.sh
DEPENDENCY_REPORT_GENERATOR := $(MAKEFILE_DIR)/templates/generate-dependency-report.py

# ドキュメント大分類オプション (デフォルトは空)
CATEGORY ?=
# ドキュメント小分類オプション (デフォルトは空)
SUBCATEGORY ?=

# CATEGORY、SUBCATEGORY を環境変数としてエクスポート (postprocess.sh で使用)
export CATEGORY
export SUBCATEGORY
export WORKSPACE_DIR

# ガードファイル用の変数 (PID を含む一意なファイル名)
SKIP_MARKER_PID := $(shell echo $$$$)
SKIP_MARKER := /tmp/.skip_markdown_generation.$(SKIP_MARKER_PID)
export SKIP_MARKER

# CATEGORY、SUBCATEGORY に応じたパスの設定
ifneq ($(strip $(CATEGORY)),)
    DOXYGEN_WORKDIR := $(WORKSPACE_DIR)/app/$(CATEGORY)
    DOXYGEN_RUNDIR  := $(DOXYGEN_WORKDIR)/prod
    DOCS_DOXYBOOK2_BASE_DIR := $(DOXYGEN_WORKDIR)/docs
    APP_DOCS_DIR := $(DOXYGEN_WORKDIR)/docs
    ifneq ($(strip $(SUBCATEGORY)),)
        ifneq ($(words $(SUBCATEGORY)),1)
            $(error SUBCATEGORY must be a single value without whitespace: $(SUBCATEGORY))
        endif
        ifneq ($(filter . ..,$(SUBCATEGORY)),)
            $(error SUBCATEGORY must not be "." or "..": $(SUBCATEGORY))
        endif
        ifneq ($(findstring /,$(SUBCATEGORY)),)
            $(error SUBCATEGORY must not contain "/": $(SUBCATEGORY))
        endif
        ifneq ($(findstring \,$(SUBCATEGORY)),)
            $(error SUBCATEGORY must not contain "\\" : $(SUBCATEGORY))
        endif
        CATEGORY_ID     := $(CATEGORY)_$(SUBCATEGORY)
        CATEGORY_SUFFIX := /$(CATEGORY_ID)
        DOXYFILE_PART   := $(DOXYGEN_RUNDIR)/Doxyfile.part.$(SUBCATEGORY)
        DOXYBOOK2_OUTPUT_DIR_DEFAULT := doxybook2_$(SUBCATEGORY)
        DOXY_WARN_BASENAME := doxy_$(SUBCATEGORY).warn
    else
        CATEGORY_ID     := $(CATEGORY)
        CATEGORY_SUFFIX := /$(CATEGORY)
        DOXYFILE_PART   := $(DOXYGEN_RUNDIR)/Doxyfile.part
        DOXYBOOK2_OUTPUT_DIR_DEFAULT := doxybook2
        DOXY_WARN_BASENAME := doxy.warn
    endif
else
    ifneq ($(strip $(SUBCATEGORY)),)
        $(error SUBCATEGORY requires CATEGORY to be set)
    endif
    CATEGORY_ID     :=
    CATEGORY_SUFFIX :=
    DOXYGEN_WORKDIR := $(WORKSPACE_DIR)/prod
    DOXYGEN_RUNDIR  := $(DOXYGEN_WORKDIR)
    DOXYFILE_PART   := $(WORKSPACE_DIR)/Doxyfile.part
    DOCS_DOXYBOOK2_BASE_DIR := $(WORKSPACE_DIR)/docs
    APP_DOCS_DIR :=
    DOXYBOOK2_OUTPUT_DIR_DEFAULT := doxybook2
    DOXY_WARN_BASENAME := doxy.warn
endif
export DOXYGEN_WORKDIR
export DOXYGEN_RUNDIR
export CATEGORY_ID

ifneq ($(wildcard $(DOXYFILE_PART)),)
    DOXYFILE_PART_PATH := $(DOXYFILE_PART)
else
    DOXYFILE_PART_PATH :=
endif
export DOXYFILE_PART_PATH

DOXYBOOK2_OUTPUT_DIR_DIRECTIVE := DOXYFW_DOXYBOOK2_OUTPUT_DIR_NAME

ifneq ($(strip $(CATEGORY)),)
ifneq ($(DOXYFILE_PART_PATH),)
    DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_COUNT := $(shell awk -v directive='$(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE)' 'BEGIN { pattern = "^[[:space:]]*" sprintf("%c", 35) "[[:space:]]*" directive "[[:space:]]*=" } $$0 ~ pattern { value = $$0; sub(pattern "[[:space:]]*", "", value); sub(/[[:space:]]*$$/, "", value); if (value != "") count++ } END { print count + 0 }' "$(DOXYFILE_PART_PATH)")
    DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_VALUE := $(shell awk -v directive='$(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE)' 'BEGIN { pattern = "^[[:space:]]*" sprintf("%c", 35) "[[:space:]]*" directive "[[:space:]]*=" } $$0 ~ pattern { value = $$0; sub(pattern "[[:space:]]*", "", value); sub(/[[:space:]]*$$/, "", value); if (value != "") { print value; exit } }' "$(DOXYFILE_PART_PATH)")
else
    DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_COUNT := 0
    DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_VALUE :=
endif
else
    DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_COUNT := 0
    DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_VALUE :=
endif

ifneq ($(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_COUNT),0)
    DOXYBOOK2_OUTPUT_DIR_NAME := $(strip $(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE_VALUE))
    ifneq ($(words $(DOXYBOOK2_OUTPUT_DIR_NAME)),1)
        $(error $(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE) must be a single directory name in $(DOXYFILE_PART_PATH): $(DOXYBOOK2_OUTPUT_DIR_NAME))
    endif
    ifneq ($(filter /%,$(DOXYBOOK2_OUTPUT_DIR_NAME)),)
        $(error $(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE) must not be an absolute path in $(DOXYFILE_PART_PATH): $(DOXYBOOK2_OUTPUT_DIR_NAME))
    endif
    ifneq ($(filter . ..,$(DOXYBOOK2_OUTPUT_DIR_NAME)),)
        $(error $(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE) must not be "." or ".." in $(DOXYFILE_PART_PATH))
    endif
    ifneq ($(findstring /,$(DOXYBOOK2_OUTPUT_DIR_NAME)),)
        $(error $(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE) must not contain "/" in $(DOXYFILE_PART_PATH): $(DOXYBOOK2_OUTPUT_DIR_NAME))
    endif
    ifneq ($(findstring \,$(DOXYBOOK2_OUTPUT_DIR_NAME)),)
        $(error $(DOXYBOOK2_OUTPUT_DIR_DIRECTIVE) must not contain "\\" in $(DOXYFILE_PART_PATH): $(DOXYBOOK2_OUTPUT_DIR_NAME))
    endif
else
    DOXYBOOK2_OUTPUT_DIR_NAME := $(DOXYBOOK2_OUTPUT_DIR_DEFAULT)
endif

DOCS_DOXYBOOK2_DIR := $(DOCS_DOXYBOOK2_BASE_DIR)/$(DOXYBOOK2_OUTPUT_DIR_NAME)
DOCS_DOXYGEN_DIR := $(WORKSPACE_DIR)/pages/doxygen$(CATEGORY_SUFFIX)
XML_DIR := $(WORKSPACE_DIR)/xml$(CATEGORY_SUFFIX)
XML_ORG_DIR := $(WORKSPACE_DIR)/xml_org$(CATEGORY_SUFFIX)
DOXY_WARN_OUTPUT := $(DOXYGEN_WORKDIR)/$(DOXY_WARN_BASENAME)

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
		if command -v cygpath >/dev/null 2>&1; then \
			WARN_LOGFILE_DOXY=$$(cygpath -m "$$WARN_LOGFILE"); \
		else \
			WARN_LOGFILE_DOXY=$$WARN_LOGFILE; \
		fi; \
		rm -f "$(DOXY_WARN_OUTPUT)"; \
		if [ -n "$(CATEGORY)" ]; then \
			sed -e 's|^\(OUTPUT_DIRECTORY[[:space:]]*=\).*|\1 $(WORKSPACE_DIR)/pages/doxygen/$(CATEGORY_ID)/|' \
			    -e 's|^\(XML_OUTPUT[[:space:]]*=\).*|\1 $(WORKSPACE_DIR)/xml/$(CATEGORY_ID)|' \
			    -e 's|^\(GENERATE_TAGFILE[[:space:]]*=\).*|\1 $(XML_DIR)/doxyfw.tag|' \
			    -e 's|^\(INPUT_FILTER[[:space:]]*=\).*|\1 "python3 $(INPUT_FILTER_ABS)"|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE_DOXY|" \
			    $$TEMP_DOXYFILE > $$TEMP_DOXYFILE_MODIFIED || exit 1; \
		else \
			sed -e 's|^\(INPUT_FILTER[[:space:]]*=\).*|\1 "python3 $(INPUT_FILTER_ABS)"|' \
			    -e 's|^\(GENERATE_TAGFILE[[:space:]]*=\).*|\1 $(XML_DIR)/doxyfw.tag|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE_DOXY|" \
			    $$TEMP_DOXYFILE > $$TEMP_DOXYFILE_MODIFIED || exit 1; \
		fi; \
		rm -f $$TEMP_DOXYFILE; \
		TEMP_DOXYFILE=$$TEMP_DOXYFILE_MODIFIED; \
		( cd "$(DOXYGEN_RUNDIR)" && doxygen $$TEMP_DOXYFILE > >("$(MAKEFILE_DIR)/bin/doxygen-colorize-output.sh") ); \
		DOXYGEN_EXIT=$$?; \
		"$(DOXY_WARNING_COLORIZE)" < "$$WARN_LOGFILE" || true; \
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
		if command -v cygpath >/dev/null 2>&1; then \
			WARN_LOGFILE_DOXY=$$(cygpath -m "$$WARN_LOGFILE"); \
		else \
			WARN_LOGFILE_DOXY=$$WARN_LOGFILE; \
		fi; \
		rm -f "$(DOXY_WARN_OUTPUT)"; \
		if [ -n "$(CATEGORY)" ]; then \
			sed -e 's|^\(OUTPUT_DIRECTORY[[:space:]]*=\).*|\1 $(WORKSPACE_DIR)/pages/doxygen/$(CATEGORY_ID)/|' \
			    -e 's|^\(XML_OUTPUT[[:space:]]*=\).*|\1 $(WORKSPACE_DIR)/xml/$(CATEGORY_ID)|' \
			    -e 's|^\(GENERATE_TAGFILE[[:space:]]*=\).*|\1 $(XML_DIR)/doxyfw.tag|' \
			    -e 's|^\(INPUT_FILTER[[:space:]]*=\).*|\1 "python3 $(INPUT_FILTER_ABS)"|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE_DOXY|" \
			    "$(MAKEFILE_DIR)/Doxyfile" > $$TEMP_DOXYFILE || exit 1; \
			( cd "$(DOXYGEN_WORKDIR)" && doxygen $$TEMP_DOXYFILE > >("$(MAKEFILE_DIR)/bin/doxygen-colorize-output.sh") ); \
			DOXYGEN_EXIT=$$?; \
			"$(DOXY_WARNING_COLORIZE)" < "$$WARN_LOGFILE" || true; \
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
			    -e 's|^\(GENERATE_TAGFILE[[:space:]]*=\).*|\1 $(XML_DIR)/doxyfw.tag|' \
			    -e "s|^\(WARN_LOGFILE[[:space:]]*=\).*|\1 $$WARN_LOGFILE_DOXY|" \
			    "$(MAKEFILE_DIR)/Doxyfile" > $$TEMP_DOXYFILE || exit 1; \
			( cd "$(DOXYGEN_WORKDIR)" && doxygen $$TEMP_DOXYFILE > >("$(MAKEFILE_DIR)/bin/doxygen-colorize-output.sh") ); \
			DOXYGEN_EXIT=$$?; \
			"$(DOXY_WARNING_COLORIZE)" < "$$WARN_LOGFILE" || true; \
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

	@if [ -f "$(XML_DIR)/index.xml" ] && grep -q '<compound ' "$(XML_DIR)/index.xml"; then \
		DEPENDENCY_WARN_LOG=$$(mktemp); \
		DEPENDENCY_WARN_EXTRACT=$$(mktemp); \
		python3 "$(DEPENDENCY_REPORT_GENERATOR)" "$(XML_DIR)" "$(DOCS_DOXYGEN_DIR)/dependency" "$(CATEGORY_ID)" 2> "$$DEPENDENCY_WARN_LOG"; \
		DEPENDENCY_REPORT_EXIT=$$?; \
		if [ -s "$$DEPENDENCY_WARN_LOG" ]; then \
			"$(DOXY_WARNING_COLORIZE)" < "$$DEPENDENCY_WARN_LOG" || true; \
		fi; \
		if [ -x "$(EXTRACT_DOXY_WARNINGS)" ]; then \
			"$(EXTRACT_DOXY_WARNINGS)" "$$DEPENDENCY_WARN_LOG" "$$DEPENDENCY_WARN_EXTRACT"; \
			if [ -s "$$DEPENDENCY_WARN_EXTRACT" ]; then \
				cat "$$DEPENDENCY_WARN_EXTRACT" >> "$(DOXY_WARN_OUTPUT)"; \
			fi; \
		fi; \
		rm -f "$$DEPENDENCY_WARN_LOG" "$$DEPENDENCY_WARN_EXTRACT"; \
		if [ $$DEPENDENCY_REPORT_EXIT -ne 0 ]; then exit $$DEPENDENCY_REPORT_EXIT; fi; \
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
    # 宣言側 (統合済み) memberdef の説明をソース定義側 memberdef へ同期 (非グループ関数)
	python3 templates/merge-member-docs.py $(XML_DIR) || exit 1
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
		--templates templates 2>&1 | tee "$$DOXYBOOK2_LOG" | $(MAKEFILE_DIR)/bin/doxybook2-decolorize-output.sh; \
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
    # Doxybook2 が Windows で非 ASCII ファイル名の画像コピーに失敗する場合があるため補完
	python3 templates/copy-doxygen-images.py $(XML_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # C# enum を Files ドキュメントに挿入
	python3 templates/inject-cs-enums.py $(XML_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # グループ (@defgroup) を Files ドキュメントに挿入
	python3 templates/inject-groups.py $(XML_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # ポストプロセッシング
	templates/postprocess.sh $(DOCS_DOXYBOOK2_DIR) || exit 1
    # 正常に変換できたら xml は不要なため削除
	rm -rf $(XML_DIR)
#	rm -rf $(XML_ORG_DIR)
    # rmdir コマンドは空のディレクトリのみを削除する
	@rmdir "$(WORKSPACE_DIR)/xml" 2>/dev/null || true
	@rmdir "$(WORKSPACE_DIR)/xml_org" 2>/dev/null || true

.PHONY: clean
clean:
	-rm -rf $(DOCS_DOXYGEN_DIR) $(DOCS_DOXYBOOK2_DIR) $(XML_DIR) $(XML_ORG_DIR)
    # rmdir コマンドは空のディレクトリのみを削除する
	@if [ -n "$(APP_DOCS_DIR)" ]; then rmdir "$(APP_DOCS_DIR)" 2>/dev/null || true; fi
	@rmdir "$(WORKSPACE_DIR)/pages/doxygen" 2>/dev/null || true
	@rmdir "$(WORKSPACE_DIR)/docs/doxybook2" 2>/dev/null || true
	@rmdir "$(WORKSPACE_DIR)/xml" 2>/dev/null || true
	@rmdir "$(WORKSPACE_DIR)/xml_org" 2>/dev/null || true
