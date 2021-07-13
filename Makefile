ALL = dist/imagery.geojson dist/imagery.json dist/imagery.xml i18n/en.yaml
SOURCES := $(shell find sources -type f -name '*.geojson')
SOURCES_QUOTED := $(shell find sources -type f -name '*.geojson' -exec echo "\"{}"\" \; | LC_ALL="C" sort)
PYTHON = python

all: $(ALL)

check: scripts/check.py $(SOURCES)
	@$(PYTHON) $< $(SOURCES_QUOTED)

clean:
	rm -f $(ALL)

dist/imagery.xml: scripts/convert_xml.py $(SOURCES)
	mkdir -p dist
	@$(PYTHON) $< $(SOURCES_QUOTED)

dist/imagery.json: scripts/convert_geojson_to_legacyjson.py $(SOURCES)
	mkdir -p dist
	@$(PYTHON) $< $(SOURCES_QUOTED) > $@

dist/imagery.geojson: scripts/concat_geojson.py $(SOURCES)
	mkdir -p dist
	@$(PYTHON) $< $(SOURCES_QUOTED) > $@

i18n/en.yaml: scripts/extract_i18n.py $(SOURCES)
	mkdir -p i18n
	@$(PYTHON) $< $(SOURCES_QUOTED) > $@

# $@ The file name of the target of the rule.
# $< The name of the first prerequisite.
# $? The names of all the prerequisites that are newer than the target, with spaces between them.
# $^ The names of all the prerequisites, with spaces between them.
