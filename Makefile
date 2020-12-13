ALL = imagery.geojson imagery.json imagery.xml i18n/en.yaml
PYTHON = python
TX := $(shell which tx)

all: $(ALL)

check:
	@$(PYTHON) scripts/check.py sources

clean:
	rm -f $(ALL)

imagery.xml:
	@$(PYTHON) scripts/convert_xml.py sources

imagery.json:
	@$(PYTHON) scripts/convert_geojson_to_legacyjson.py sources

imagery.geojson:
	@$(PYTHON) scripts/concat_geojson.py sources

i18n/en.yaml:
	@$(PYTHON) scripts/extract_i18n.py i18n/en.yaml sources

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

# $@ The file name of the target of the rule.
# $< The name of the first prerequisite.
# $? The names of all the prerequisites that are newer than the target, with spaces between them.
# $^ The names of all the prerequisites, with spaces between them.
