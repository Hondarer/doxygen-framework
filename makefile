.PHONY: docs clean all

docs:
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
	mkdir -p ../docs-src/doxybook
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
# ポストプロセッシング
	templates/postprocess.sh ../docs-src/doxybook

clean:
	rm -rf ../docs/doxygen ../docs-src/doxybook ../xml

all: clean docs
