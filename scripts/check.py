import json, sys
from jsonschema import validate, ValidationError

schema = json.load(open('schema.json'))

for file in sys.argv[1:]:
    source = json.load(open(file))
    try:
        validate(source, schema)
    except ValidationError as e:
        print file
        raise
