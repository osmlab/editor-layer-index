ALL = imagery.geojson imagery.json imagery.xml

all: $(ALL)

clean:
	rm $(ALL)

SOURCES = $(shell find sources -type f -name '*.json')

imagery.xml: $(SOURCES)
	python scripts/convert_xml.py $(SOURCES)

imagery.json: $(SOURCES)
	python scripts/concat.py $(SOURCES) > imagery.json

imagery.geojson: imagery.xml
	python scripts/convert_geojson.py imagery.xml > imagery.geojson
