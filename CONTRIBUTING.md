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

See [FAQ.md](FAQ.md#what-imagery-licenses-are-compatible-with-this-index) for information
about which licenses are compatible with this index.

The 'source' documents for this project are the .geojson files in `sources`. To add
a new imagery source, add a new file to this directory.

Each source must be a GeoJSON `Feature` and must minimally have `name`, `type`, and `url` properties. To improve readability, the keys of the GeoJSON document should be ordered consistently: `type`, `properties`, then `geometry`.

See [schema.json](schema.json) for the full list of available properties.


##### Imagery Extent

Local (i.e. not worldwide) sources should define an appropriate extent as the geometry for the GeoJSON feature. Polygons and bounding boxes can be created by using a tool like http://geojson.io/

See [FAQ.md](FAQ.md#how-can-i-draw-a-bounding-polygon) for information about how to draw a bounding polygon.


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


### Translations

Imagery sources optionally support localization of the name, description, and
attribution text. To set an imagery source as being translatable, include the
property `i18n: true`.

Translations are managed using the
[Transifex](https://www.transifex.com/projects/p/id-editor/) platform.
After signing up, you can go to [iD's project page](https://www.transifex.com/projects/p/id-editor/),
select a language and click **Translate** to start translating.

The translation strings for this project are located in a resource called
[**imagery**](https://www.transifex.com/openstreetmap/id-editor/imagery/).


#### Working with translation files

To work with translation files,
[install the Transifex Client](https://docs.transifex.com/client/introduction) software.

The Transifex Client uses a file
[`~/.transifex.rc`](https://docs.transifex.com/client/client-configuration#-transifexrc)
to store your username and password.

Note that you can also use a
[Transifex API Token](https://docs.transifex.com/api/introduction#authentication)
in place of your username and password.  In this usage, the username is `api`
and the password is the generated API token.

Once you have installed the client and setup the `~/.transifex.rc` file, you can
use the following commands:

* `tx push -s`  - upload latest source `/i18n/en.yaml` file to Transifex
* `tx pull -a`  - download latest translation files to `/i18n/<lang>.yaml`

For convenience you can also run these commands as `make txpush` or `make txpull`.

