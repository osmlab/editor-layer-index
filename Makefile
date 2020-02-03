ALL = imagery.geojson imagery.json imagery.xml i18n/en.yaml
SOURCES := $(shell find sources -type f -name '*.geojson')
SOURCES_QUOTED := $(shell find sources -type f -name '*.geojson' -exec echo "\"{}"\" \; | LC_ALL="C" sort)
PYTHON = python
TX := $(shell which tx)

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

i18n/en.yaml: scripts/extract_i18n.py $(SOURCES)
	@$(PYTHON) $< $(SOURCES_QUOTED) > $@

txpush: i18n/en.yaml
ifeq (, $(TX))
	@echo "Transifex not installed"
else
	$(TX) push -s
endif

txpull:
ifeq (, $(TX))
	@echo "Transifex not installed"
else
	$(TX) pull -a
endif

# $@ The file name of the target of the rule.
# $< The name of the first prerequisite.
# $? The names of all the prerequisites that are newer than the target, with spaces between them.
# $^ The names of all the prerequisites, with spaces between them.
