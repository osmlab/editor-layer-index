ALL = imagery.geojson imagery.json imagery.xml
SOURCES := $(shell find sources -type f -name '*.geojson')
SOURCES_QUOTED := $(shell find sources -type f -name '*.geojson' -exec echo "\"{}"\" \; | LC_ALL="C" sort)
PYTHON = python

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

# $@ The file name of the target of the rule.
# $< The name of the first prerequisite.
# $? The names of all the prerequisites that are newer than the target, with spaces between them.
# $^ The names of all the prerequisites, with spaces between them.
