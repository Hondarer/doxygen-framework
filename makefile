# この makefile のディレクトリ (絶対パス) を取得
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# ドキュメント大分類オプション (デフォルトは空)
CATEGORY ?=

# CATEGORY を環境変数としてエクスポート (postprocess.sh で使用)
export CATEGORY

# ガードファイル用の変数 (PID を含む一意なファイル名)
SKIP_MARKER_PID := $(shell echo $$$$)
SKIP_MARKER := /tmp/.skip_markdown_generation.$(SKIP_MARKER_PID)
export SKIP_MARKER

# CATEGORY に応じたパスの設定
ifdef CATEGORY
    CATEGORY_SUFFIX := /$(CATEGORY)
    DOXYFILE_PART := ../Doxyfile.part.$(CATEGORY)
else
    CATEGORY_SUFFIX :=
    DOXYFILE_PART := ../Doxyfile.part
endif

DOCS_DOXYGEN_DIR := ../docs/doxygen$(CATEGORY_SUFFIX)
DOCS_DOXYBOOK_DIR := ../docs-src/doxybook$(CATEGORY_SUFFIX)
XML_DIR := ../xml$(CATEGORY_SUFFIX)
XML_ORG_DIR := ../xml_org$(CATEGORY_SUFFIX)

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
		cat Doxyfile $(DOXYFILE_PART) > $$TEMP_DOXYFILE || exit 1; \
		if [ -n "$(CATEGORY)" ]; then \
			TEMP_DOXYFILE_MODIFIED=$$(mktemp); \
			sed -e 's|^\(OUTPUT_DIRECTORY[[:space:]]*=\).*|\1 ../docs/doxygen/$(CATEGORY)/|' \
			    -e 's|^\(XML_OUTPUT[[:space:]]*=\).*|\1 ../../../xml/$(CATEGORY)|' \
			    $$TEMP_DOXYFILE > $$TEMP_DOXYFILE_MODIFIED || exit 1; \
			rm -f $$TEMP_DOXYFILE; \
			TEMP_DOXYFILE=$$TEMP_DOXYFILE_MODIFIED; \
		fi; \
		cd ../prod && doxygen $$TEMP_DOXYFILE 2>&1 | $(MAKEFILE_DIR)/doxygen-colorize-output.sh; \
		PIPE_STATUS=($${PIPESTATUS[@]}); DOXYGEN_EXIT=$${PIPE_STATUS[0]}; COLORIZE_EXIT=$${PIPE_STATUS[1]}; \
		rm -f $$TEMP_DOXYFILE; \
		if [ $$DOXYGEN_EXIT -ne 0 ]; then exit $$DOXYGEN_EXIT; fi; \
		exit $$COLORIZE_EXIT; \
	else \
		TEMP_DOXYFILE=$$(mktemp); \
		if [ -n "$(CATEGORY)" ]; then \
			sed -e 's|^\(OUTPUT_DIRECTORY[[:space:]]*=\).*|\1 ../docs/doxygen/$(CATEGORY)/|' \
			    -e 's|^\(XML_OUTPUT[[:space:]]*=\).*|\1 ../../../xml/$(CATEGORY)|' \
			    Doxyfile > $$TEMP_DOXYFILE || exit 1; \
			cd ../prod && doxygen $$TEMP_DOXYFILE 2>&1 | $(MAKEFILE_DIR)/doxygen-colorize-output.sh; \
			PIPE_STATUS=($${PIPESTATUS[@]}); DOXYGEN_EXIT=$${PIPE_STATUS[0]}; COLORIZE_EXIT=$${PIPE_STATUS[1]}; \
			rm -f $$TEMP_DOXYFILE; \
			if [ $$DOXYGEN_EXIT -ne 0 ]; then exit $$DOXYGEN_EXIT; fi; \
			exit $$COLORIZE_EXIT; \
		else \
			cd ../prod && doxygen $(MAKEFILE_DIR)/Doxyfile 2>&1 | $(MAKEFILE_DIR)/doxygen-colorize-output.sh; \
			PIPE_STATUS=($${PIPESTATUS[@]}); DOXYGEN_EXIT=$${PIPE_STATUS[0]}; COLORIZE_EXIT=$${PIPE_STATUS[1]}; \
			if [ $$DOXYGEN_EXIT -ne 0 ]; then exit $$DOXYGEN_EXIT; fi; \
			exit $$COLORIZE_EXIT; \
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
	mkdir -p $(DOCS_DOXYBOOK_DIR)
    # デバッグ用にオリジナルの xml をバックアップ
#	rm -rf $(XML_ORG_DIR)
#	mkdir -p $(XML_ORG_DIR)
#	cp -rp $(XML_DIR)/* $(XML_ORG_DIR)/
    # グラフ抽出 (XML のグラフ情報から PlantUML を生成し XML に挿入)
	python3 templates/extract-graphs.py $(XML_DIR) || exit 1
    # プリプロセッシング
	templates/preprocess.sh $(XML_DIR) || exit 1
    # xml -> md 変換
	doxybook2 \
		-i $(XML_DIR) \
		-o $(DOCS_DOXYBOOK_DIR) \
		--config doxybook-config.json \
		--templates templates 2>&1 | $(MAKEFILE_DIR)/doxybook2-decolorize-output.sh; \
	DOXYBOOK_EXIT=$${PIPESTATUS[0]}; \
	if [ $$DOXYBOOK_EXIT -ne 0 ]; then exit $$DOXYBOOK_EXIT; fi
    # 正常に変換できたら xml は不要なため削除
	rm -rf $(XML_DIR)
#	rm -rf $(XML_ORG_DIR)
    # rmdir コマンドは空のディレクトリのみを削除する
	@rmdir ../xml 2>/dev/null || true
	@rmdir ../xml_org 2>/dev/null || true
    # ポストプロセッシング
	templates/postprocess.sh $(DOCS_DOXYBOOK_DIR) || exit 1

.PHONY: clean
clean:
	-rm -rf $(DOCS_DOXYGEN_DIR) $(DOCS_DOXYBOOK_DIR) $(XML_DIR) $(XML_ORG_DIR)
    # rmdir コマンドは空のディレクトリのみを削除する
	@rmdir ../docs/doxygen 2>/dev/null || true
	@rmdir ../docs-src/doxybook 2>/dev/null || true
	@rmdir ../xml 2>/dev/null || true
	@rmdir ../xml_org 2>/dev/null || true
