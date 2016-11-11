ALL = imagery.geojson imagery.json imagery.xml
SOURCES = $(shell find sources -type f -name '*.geojson' | LC_ALL="C" sort)
PYTHON = python

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
