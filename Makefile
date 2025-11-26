# このMakefileのディレクトリ (絶対パス) を取得
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.DEFAULT_GOAL := default

.PHONY: default
default: clean
# doxygen コマンドが存在しない場合は全体をスキップ
	@if ! command -v doxygen >/dev/null 2>&1; then \
		echo "Warning: doxygen command not found. Skipping documentation generation."; \
		exit 0; \
	fi
	mkdir -p ../docs/doxygen
# Doxyfile.part がある場合は結合した一時 Doxyfile を作成
	@if [ -f "../Doxyfile.part" ]; then \
		echo "Merging Doxyfile.part..."; \
		TEMP_DOXYFILE=$$(mktemp); \
		cat Doxyfile ../Doxyfile.part > $$TEMP_DOXYFILE || exit 1; \
		cd ../prod && doxygen $$TEMP_DOXYFILE 2>&1 | $(MAKEFILE_DIR)/doxygen-colorize-output.sh; \
		DOXYGEN_EXIT=$${PIPESTATUS[0]}; \
		rm -f $$TEMP_DOXYFILE; \
		exit $$DOXYGEN_EXIT; \
	else \
		cd ../prod && doxygen $(MAKEFILE_DIR)/Doxyfile 2>&1 | $(MAKEFILE_DIR)/doxygen-colorize-output.sh; \
		exit $${PIPESTATUS[0]}; \
	fi
# doxybook2 コマンドが存在しない場合は前処理～doxybook2～後処理をスキップ
	@if ! command -v doxybook2 >/dev/null 2>&1; then \
		echo "Warning: doxybook2 command not found. Skipping Markdown generation."; \
		exit 0; \
	fi
	mkdir -p ../docs-src/doxybook
# デバッグ用にオリジナルの xml をバックアップ
#	rm -rf ../xml_org
#	cp -rp ../xml ../xml_org
# プリプロセッシング
	templates/preprocess.sh ../xml || exit 1
# xml -> md 変換
	doxybook2 \
		-i ../xml \
		-o ../docs-src/doxybook \
		--config doxybook-config.json \
		--templates templates 2>&1 | $(MAKEFILE_DIR)/doxybook2-decolorize-output.sh; \
	DOXYBOOK_EXIT=$${PIPESTATUS[0]}; \
	if [ $$DOXYBOOK_EXIT -ne 0 ]; then exit $$DOXYBOOK_EXIT; fi
# 正常に変換できたら xml は不要なため削除
	rm -rf ../xml
#	rm -rf ../xml_org
# ポストプロセッシング
	templates/postprocess.sh ../docs-src/doxybook || exit 1
# Markdown 収集
	./collect-pages.sh ../ prod docs-src/doxybook/Pages || exit 1

.PHONY: clean
clean:
	-rm -rf ../docs/doxygen ../docs-src/doxybook ../xml
