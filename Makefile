.PHONY: docs clean all

docs:
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
		cat Doxyfile ../Doxyfile.part > $$TEMP_DOXYFILE; \
		cd ../prod && doxygen $$TEMP_DOXYFILE; \
		rm -f $$TEMP_DOXYFILE; \
	else \
		cd ../prod && doxygen ../doxyfw/Doxyfile; \
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
	templates/preprocess.sh ../xml
# xml -> md 変換
	doxybook2 \
		-i ../xml \
		-o ../docs-src/doxybook \
		--config doxybook-config.json \
		--templates templates
# 正常に変換できたら xml は不要なため削除
	rm -rf ../xml
#	rm -rf ../xml_org
# ポストプロセッシング
	templates/postprocess.sh ../docs-src/doxybook

clean:
	rm -rf ../docs/doxygen ../docs-src/doxybook ../xml

all: clean docs
