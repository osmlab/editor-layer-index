import json, sys, io
from jsonschema import validate, ValidationError

schema = json.load(io.open('schema.json', encoding='utf-8'))
seen_ids = set()

for file in sys.argv[1:]:
    source = json.load(io.open(file, encoding='utf-8'))
    try:
        validate(source, schema)
        id = source['properties']['id']
        if id in seen_ids:
            raise ValidationError('Id %s used multiple times' % id)
        seen_ids.add(id)
        if '{z}' in source['properties']['url']:
            raise ValidationError('{z} found instead of {zoom} in tile url')
        sys.stdout.write('.')
        sys.stdout.flush()
    except ValidationError as e:
        print(file)
        raise

print('')
