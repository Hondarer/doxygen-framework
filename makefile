SHELL := /bin/bash

# この makefile のディレクトリ (絶対パス) を取得
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
WORKSPACE_DIR ?= $(abspath $(MAKEFILE_DIR)/../..)
INPUT_FILTER_ABS := $(MAKEFILE_DIR)/bin/input-filter.py
DOXY_WARNING_COLORIZE := $(MAKEFILE_DIR)/bin/doxygen-warning-colorize-output.sh
EXTRACT_DOXY_WARNINGS := $(MAKEFILE_DIR)/bin/extract_doxy_warnings.sh
DEPENDENCY_REPORT_GENERATOR := $(MAKEFILE_DIR)/templates/generate-dependency-report.py
RUN_DOXYFW_SCRIPT := $(MAKEFILE_DIR)/bin/run_doxyfw_make.sh
MARKDOWN_MAKE_CMD := $(MAKE)

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
DOXY_WARN_OUTPUT := $(DOXYGEN_WORKDIR)/$(DOXY_WARN_BASENAME)
DOXYFW_TMP_ROOT ?= /tmp/doxyfw-tmp
DOXYFW_LOCK_ROOT ?= /tmp/doxyfw-locks
DOXYFW_RUNTIME_KEY := $(if $(CATEGORY_ID),$(CATEGORY_ID),root)

.DEFAULT_GOAL := default

.PHONY: default
default:
	@MAKEFILE_DIR="$(MAKEFILE_DIR)" \
	WORKSPACE_DIR="$(WORKSPACE_DIR)" \
	INPUT_FILTER_ABS="$(INPUT_FILTER_ABS)" \
	DOXY_WARNING_COLORIZE="$(DOXY_WARNING_COLORIZE)" \
	EXTRACT_DOXY_WARNINGS="$(EXTRACT_DOXY_WARNINGS)" \
	DEPENDENCY_REPORT_GENERATOR="$(DEPENDENCY_REPORT_GENERATOR)" \
	DOXYGEN_RUNDIR="$(DOXYGEN_RUNDIR)" \
	DOXYFILE_PART="$(DOXYFILE_PART)" \
	CATEGORY="$(CATEGORY)" \
	CATEGORY_ID="$(CATEGORY_ID)" \
	DOCS_DOXYGEN_DIR="$(DOCS_DOXYGEN_DIR)" \
	DOCS_DOXYBOOK2_DIR="$(DOCS_DOXYBOOK2_DIR)" \
	DOXY_WARN_OUTPUT="$(DOXY_WARN_OUTPUT)" \
	APP_DOCS_DIR="$(APP_DOCS_DIR)" \
	DOXY_WARN_BASENAME="$(DOXY_WARN_BASENAME)" \
	DOXYFW_TMP_ROOT="$(DOXYFW_TMP_ROOT)" \
	DOXYFW_LOCK_ROOT="$(DOXYFW_LOCK_ROOT)" \
	DOXYFW_RUNTIME_KEY="$(DOXYFW_RUNTIME_KEY)" \
	SKIP_MARKER="$(SKIP_MARKER)" \
	MARKDOWN_MAKE="$(MARKDOWN_MAKE_CMD)" \
	"$(SHELL)" "$(RUN_DOXYFW_SCRIPT)"

.PHONY: markdown-generation
DOXYFW_XML_WORK_DIR ?=

markdown-generation:
	@if [ -z "$(DOXYFW_XML_WORK_DIR)" ]; then \
		echo "ERROR: DOXYFW_XML_WORK_DIR is required for markdown-generation." >&2; \
		exit 2; \
	fi
	mkdir -p $(DOCS_DOXYBOOK2_DIR)
    # 宣言側 (統合済み) memberdef の説明をソース定義側 memberdef へ同期 (非グループ関数)
	python3 templates/merge-member-docs.py $(DOXYFW_XML_WORK_DIR) || exit 1
    # グラフ抽出 (XML のグラフ情報から PlantUML を生成し XML に挿入)
	python3 templates/extract-graphs.py $(DOXYFW_XML_WORK_DIR) || exit 1
    # プリプロセッシング
	templates/preprocess.sh $(DOXYFW_XML_WORK_DIR) || exit 1
    # xml -> md 変換
	@DOXYBOOK2_LOG=$$(mktemp); \
	doxybook2 \
		-i $(DOXYFW_XML_WORK_DIR) \
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
	python3 templates/copy-doxygen-images.py $(DOXYFW_XML_WORK_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # C# enum を Files ドキュメントに挿入
	python3 templates/inject-cs-enums.py $(DOXYFW_XML_WORK_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # グループ (@defgroup) を Files ドキュメントに挿入
	python3 templates/inject-groups.py $(DOXYFW_XML_WORK_DIR) $(DOCS_DOXYBOOK2_DIR) || exit 1
    # ポストプロセッシング
	DOXYFW_TAGFILE=$(DOXYFW_XML_WORK_DIR)/doxyfw.tag templates/postprocess.sh $(DOCS_DOXYBOOK2_DIR) || exit 1
    # 正常に変換できたら xml は不要なため削除
	rm -rf $(DOXYFW_XML_WORK_DIR)

.PHONY: clean
clean:
	-rm -rf $(DOCS_DOXYGEN_DIR) $(DOCS_DOXYBOOK2_DIR)
    # 実行中プロセスの一時ディレクトリは削除しない。
    # rmdir コマンドは空のディレクトリのみを削除する
	@if [ -n "$(APP_DOCS_DIR)" ]; then rmdir "$(APP_DOCS_DIR)" 2>/dev/null || true; fi
	@rmdir "$(WORKSPACE_DIR)/pages/doxygen" 2>/dev/null || true
	@rmdir "$(WORKSPACE_DIR)/docs/doxybook2" 2>/dev/null || true
