ALL = imagery.geojson imagery.json imagery.xml imagery.id.json i18n/en.yaml
.DELETE_ON_ERROR:
SOURCES := $(shell find sources -type f -name '*.geojson')
SOURCES_QUOTED := $(shell find sources -type f -name '*.geojson' -exec echo "\"{}"\" \; | LC_ALL="C" sort)
PYTHON = python
NODE = node
TX := $(shell which tx)
TXVERSION := $(shell tx --version | cut -c1-1)

all: $(ALL)

check: scripts/check.py $(SOURCES)
	@$(PYTHON) $< $(SOURCES_QUOTED)

clean:
	rm -f $(ALL)

imagery.xml: scripts/convert_xml.py $(SOURCES)
	@$(PYTHON) $< $(SOURCES_QUOTED)

imagery.json: scripts/convert_geojson_to_legacyjson.py $(SOURCES)
	@$(PYTHON) $< $(SOURCES_QUOTED) > $@

imagery.geojson: scripts/concat_geojson.py $(SOURCES)
	@$(PYTHON) $< $(SOURCES_QUOTED) > $@

imagery.id.json: scripts/convert_id.mjs scripts/id/convert.mjs scripts/id/update_imagery.js scripts/id/manual_imagery.json imagery.geojson
	@$(NODE) $< --format-version 1 imagery.geojson > $@

.PHONY: test-id
test-id: imagery.id.json
	@$(NODE) --test scripts/tests/test_id_imagery.mjs

i18n/en.yaml: scripts/extract_i18n.py $(SOURCES)
	@$(PYTHON) $< $(SOURCES_QUOTED) > $@

txpush: i18n/en.yaml
ifeq (, $(TX))
	@echo "Transifex not installed"
else ifeq (0, $(TXVERSION))
	@echo "Installed Transifex CLI client too old: Upgrade to https://github.com/transifex/cli"
else
	$(TX) push -s
endif

txpull:
ifeq (, $(TX))
	@echo "Transifex not installed"
else ifeq (0, $(TXVERSION))
	@echo "Installed Transifex CLI client too old: Upgrade to https://github.com/transifex/cli"
else
	$(TX) pull -a --use-git-timestamps
endif

# $@ The file name of the target of the rule.
# $< The name of the first prerequisite.
# $? The names of all the prerequisites that are newer than the target, with spaces between them.
# $^ The names of all the prerequisites, with spaces between them.
