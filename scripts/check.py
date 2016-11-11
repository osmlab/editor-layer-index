import json, sys, io
from jsonschema import validate, ValidationError

schema = json.load(io.open('schema.json', encoding='utf-8'))

for file in sys.argv[1:]:
    source = json.load(io.open(file, encoding='utf-8'))
    try:
        validate(source, schema)
        sys.stdout.write('.')
        sys.stdout.flush()
    except ValidationError as e:
        print(file)
        raise

print('')
