ALL = imagery.geojson imagery.json imagery.xml i18n/en.yaml
SOURCES := $(shell find sources -type f -name '*.geojson' -exec echo "\"{}"\" \; | LC_ALL="C" sort)
PYTHON = python
TX := $(shell which tx)

all: $(ALL)

check:
	@$(PYTHON) scripts/check.py $(SOURCES)

clean:
	rm -f $(ALL)

imagery.xml:
	@$(PYTHON) scripts/convert_xml.py $(SOURCES)

imagery.json:
	@$(PYTHON) scripts/convert_geojson_to_legacyjson.py $(SOURCES) > imagery.json

imagery.geojson:
	@$(PYTHON) scripts/concat_geojson.py $(SOURCES) > imagery.geojson

i18n/en.yaml:
	@$(PYTHON) scripts/extract_i18n.py $(SOURCES) > $@

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
