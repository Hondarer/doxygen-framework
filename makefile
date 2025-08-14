.PHONY: docs

docs:
	mkdir -p ../docs/doxygen
# Doxyfile.part がある場合は結合した一時 Doxyfile を作成
	@if [ -f "../Doxyfile.part" ]; then \
		echo "Merging Doxyfile.part..."; \
		TEMP_DOXYFILE=$$(mktemp); \
		cat config/Doxyfile ../Doxyfile.part > $$TEMP_DOXYFILE; \
		cd ../prod && doxygen $$TEMP_DOXYFILE; \
		rm -f $$TEMP_DOXYFILE; \
	else \
		cd ../prod && doxygen ../doxyfw/config/Doxyfile; \
	fi
	mkdir -p ../docs-src/doxybook
# プリプロセッシング
	config/templates/preprocess.sh ../xml
# xml -> md 変換
	doxybook2 \
		-i ../xml \
		-o ../docs-src/doxybook \
		--config config/doxybook-config.json \
		--templates config/templates
# 正常に変換できたら xml は不要なため削除
	rm -rf ../xml
# ポストプロセッシング
	config/templates/postprocess.sh ../docs-src/doxybook

clean:
	rm -rf ../docs/doxygen ../docs-src/doxybook ../xml
