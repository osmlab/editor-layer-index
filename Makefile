ALL = imagery.geojson imagery.json imagery.xml
SOURCES = $(shell find sources -type f -name '*.json' | LC_ALL="C" sort)

all: $(ALL)

check:
	@python scripts/check.py $(SOURCES)

clean:
	rm $(ALL)

imagery.xml: $(SOURCES)
	python scripts/convert_xml.py $(SOURCES)

imagery.json: $(SOURCES)
	python scripts/concat.py $(SOURCES) > imagery.json

imagery.geojson: imagery.xml
	python scripts/convert_geojson.py imagery.xml > imagery.geojson
