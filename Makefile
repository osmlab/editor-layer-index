all: imagery.geojson imagery.json

clean:
	rm imagery.geojson
	rm imagery.json

imagery.geojson: josm-imagery.xml
	python scripts/convert_geojson.py josm-imagery.xml > imagery.geojson

imagery.json: josm-imagery.xml
	python scripts/convert_josm_index.py josm-imagery.xml > imagery.json
