ALL = imagery.geojson imagery.json imagery.xml i18n/en.json
SOURCES = $(shell find sources -type f -name '*.geojson' | LC_ALL="C" sort)
PYTHON = python
TX := $(shell which tx)

all: $(ALL)

check:
	@$(PYTHON) scripts/check.py $(SOURCES)

clean:
	rm -f $(ALL)

imagery.xml: $(SOURCES)
	@$(PYTHON) scripts/convert_xml.py $(SOURCES)

imagery.json: $(SOURCES)
	@$(PYTHON) scripts/convert_geojson_to_legacyjson.py $(SOURCES) > imagery.json

imagery.geojson: $(SOURCES)
	@$(PYTHON) scripts/concat_geojson.py $(SOURCES) > imagery.geojson

i18n/en.json: $(SOURCES)
	@$(PYTHON) scripts/extract_i18n.py $(SOURCES) > $@

txpush: i18n/en.json
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
