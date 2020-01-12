## Contributing

### Adding new sources

See [FAQ.md](FAQ.md#what-imagery-licenses-are-compatible-with-this-index) for information
about which licenses are compatible with this index.

The 'source' documents for this project are the .geojson files in `sources`. To add
a new imagery source, add a new file to this directory.

Each source must be a GeoJSON `Feature` and must minimally have `name`, `type`,`url` and `category` properties.
To improve readability, the keys of the GeoJSON document should be ordered consistently: `type`, `properties`, then `geometry`.

We further recommend to add the licence related and `privacy_policy_url` properties.

See [schema.json](schema.json) for the full list of available properties.

##### Source URL

The source `url` property should contain a url with replacement tokens. An application will replace the tokens as needed to download image tiles. Whenever possible, use https URLs.

Supported TMS tokens:
- `{zoom}`, `{x}`, `{y}` for Z/X/Y tile coordinates
- `{-y}` for flipped TMS-style Y coordinates
- `{switch:a,b,c}` for DNS server multiplexing

Example: `https://{switch:a,b,c}.tile.openstreetmap.org/{zoom}/{x}/{y}.png`

Supported WMS tokens:
- `{proj}` - requested projection (e.g. EPSG:3857)
- `{width}`, `{height}` - requested image dimensions (e.g. 256, 512)
- `{bbox}` - requested bounding box

Example: `http://geodienste-hamburg.de/HH_WMS_Geobasisdaten?FORMAT=image/jpeg&VERSION=1.1.1&SERVICE=WMS&REQUEST=GetMap&LAYERS=13&STYLES=&SRS={proj}&WIDTH={width}&HEIGHT={height}&BBOX={bbox}`

Make sure you submit the most appropriate image format for the images: usually, jpeg for photography and png for maps. See #435 for a case where bmp was better.

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

To specify imagery taken sometime in 2019, use `"start_date": "2019"`,
`"end_date": "2019"`.

Implementations *must not* round down the end date (e.g. consider `2013` the same as the
start of `2013`. Note that this is the opposite of what we did before, and layers before 2015 could have overly wide date ranges.

### Submitting your modifications

Follow [this workflow](https://gist.github.com/Chaser324/ce0505fbed06b947d962) to create and submit a change to the editor layer index. Whenever branches are mentioned, replace `master` with `gh-pages`.

After you've made a modification, and submit a pull request including those json files. Tests will be run automatically.

We previously required contributors to run local checks with `make check`, and run `make` to rebuild the combined files. This is now handled automatically for every pull request, and should not be done anymore.

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

