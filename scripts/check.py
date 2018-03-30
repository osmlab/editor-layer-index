import json, sys, io
from jsonschema import validate, ValidationError

schema = json.load(io.open('schema.json', encoding='utf-8'))
seen_ids = set()

def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
           raise ValidationError("duplicate key: %r" % (k,))
        else:
           d[k] = v
    return d

for file in sys.argv[1:]:
    try:
        source = json.load(io.open(file, encoding='utf-8'), object_pairs_hook=dict_raise_on_duplicates)
        validate(source, schema)
        id = source['properties']['id']
        if id in seen_ids:
            raise ValidationError('Id %s used multiple times' % id)
        seen_ids.add(id)
        if '{z}' in source['properties']['url']:
            raise ValidationError('{z} found instead of {zoom} in tile url')
        sys.stdout.write('.')
        sys.stdout.flush()
    except Exception as e:
        print("Error in "+file+" :")
        print(e.message)
        raise SystemExit(1)

print('')
