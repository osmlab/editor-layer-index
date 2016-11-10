## Contributing

### Prerequisites
* Command line development tools (`make`, `git`) for your platform
  * Ubuntu: `sudo apt-get install build-essential git`
  * Mac OS X: Install Xcode and run `xcode-select --install` from a command line
  * Arch Linux: `sudo pacman -S make git`
* Python and Pip
  * Ubuntu: `sudo apt-get install python-pip python-dev`
  * Mac OS X (via [Homebrew](http://brew.sh/)): `brew install python`, then `brew linkapps python`
  * Arch Linux: `sudo pacman -S python2 python2-jsonschema`
* `jsonschema` package (for running `make check`)
  * `pip install jsonschema`

### Adding new sources
The 'source' documents for this project are the .geojson files in `sources`. To add
a new imagery source, add a new file to this directory.

Each source must be a GeoJSON `Feature` and must minimally have `name`, `type`, and `url` properties. To improve readability, the keys of the GeoJSON document should be ordered consistently: `type`, `properties`, then `geometry`.

See [schema.json](schema.json) for the full list of available properties.


##### Imagery Extent

Local (i.e. not worldwide) sources should define an appropriate extent as the geometry for the GeoJSON feature. Polygons and bounding boxes can be created by using a tool like http://geojson.io/


##### Imagery Dates

Valid imagery dates may be defined with `start_date` and `end_date` properties:
```js
    "start_date": "2012",
    "end_date": "2014",
```

Specifying reduced accuracy dates is complex. For simplicity, the schema allows
a subset of ISO 8601 defined in [RFC 3339](http://tools.ietf.org/html/rfc3339#section-5.6)
except that a reduced precision date is allowed. For example, `2013-04-15T14:02:54.05+00:00`
is a fully specified ISO 8601 date-time, `2013-04-15` could be used for just the date,
or `2013-04` for just the month, `2013` for just the year.

Implementations may round down the end date (e.g. consider `2013` the same as the
start of `2013` so to specify imagery taken sometime in 2013, use `"start_date": "2013"`,
`"end_date": "2014"`.


### Building the combined files

After you've made a modification:

1. run `make check` to validate the source files against `schema.json`
2. run `make` to generate `imagery.xml`, `imagery.json`, and `imagery.geojson`
