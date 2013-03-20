all: imagery.geojson imagery.json

clean:
	rm imagery.geojson
	rm imagery.json

imagery.geojson: imagery.xml
	python scripts/convert_geojson.py imagery.xml > imagery.geojson

imagery.json: imagery.xml
	python scripts/convert_josm_index.py imagery.xml > imagery.json
