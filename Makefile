all: imagery.geojson imagery.json

imagery.geojson: josm-imagery.xml
	python convert_geojson.py josm-imagery.xml > imagery.geojson

imagery.json: josm-imagery.xml
	python convert_josm_index.py josm-imagery.xml > imagery.json
