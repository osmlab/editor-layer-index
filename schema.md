
#  Schema

```
```


| Abstract | Extensible | Status | Identifiable | Custom Properties | Additional Properties | Defined In |
|----------|------------|--------|--------------|-------------------|-----------------------|------------|
| Can be instantiated | No | Experimental | No | Forbidden | Permitted |  |

#  Properties

| Property | Type | Required | Defined by |
|----------|------|----------|------------|
| [bbox](#bbox) | reference | Optional |  (this schema) |
| [geometry](#geometry) | reference | Optional |  (this schema) |
| [properties](#properties) | `object` | Optional |  (this schema) |
| [type](#type) | `enum` | Optional |  (this schema) |
| `*` | any | Additional | this schema *allows* additional properties |

## bbox


`bbox`
* is optional
* type: reference
* defined in this schema

### bbox Type


* []() – `http://json.schemastore.org/geojson#/properties/bbox`





## geometry


`geometry`
* is optional
* type: reference
* defined in this schema

### geometry Type


* []() – `http://json.schemastore.org/geojson#/definitions/geometry`





## properties


`properties`
* is optional
* type: `object`
* defined in this schema

### properties Type


`object` with following properties:


| Property | Type | Required | Default |
|----------|------|----------|---------|
| `attribution`| object | Optional |  |
| `available_projections`| array | Optional |  |
| `best`| boolean | Optional |  |
| `country_code`| string | Optional |  |
| `default`| boolean | Optional |  |
| `description`| string | Optional |  |
| `end_date`| string | Optional |  |
| `i18n`| boolean | Optional |  |
| `icon`| string | Optional |  |
| `id`| string | **Required** |  |
| `license`| string | Optional |  |
| `license_url`| string | Optional |  |
| `max_zoom`| integer | Optional |  |
| `min_zoom`| integer | Optional | `0` |
| `name`| string | **Required** |  |
| `overlay`| boolean | Optional | `"false"` |
| `permission_osm`| string | Optional |  |
| `start_date`| string | Optional |  |
| `type`| string | **Required** |  |
| `url`| string | **Required** |  |



#### attribution

undefined

`attribution`
* is optional
* type: `object`

##### attribution Type

Unknown type `object`.

```json
{
  "type": "object",
  "properties": {
    "url": {
      "type": "string"
    },
    "text": {
      "type": "string"
    },
    "html": {
      "type": "string"
    },
    "required": {
      "type": "boolean"
    }
  },
  "additionalProperties": false,
  "simpletype": "`object`"
}
```







#### available_projections

undefined

`available_projections`
* is optional
* type: `string[]`


##### available_projections Type


Array type: `string[]`

All items must be of the type:
`string`











#### best

Whether this imagery is the best source for the region

`best`
* is optional
* type: `boolean`

##### best Type


`boolean`







#### country_code

The ISO 3166-1 alpha-2 two letter country code in upper case. Use ZZ for unknown or multiple.

`country_code`
* is optional
* type: `string`

##### country_code Type


`string`


All instances must conform to this regular expression 
(test examples [here](https://regexr.com/?expression=%5E%5BA-Z%5D%7B2%7D%24)):
```regex
^[A-Z]{2}$
```








#### default

Whether this imagery should be shown in the default world-wide menu

`default`
* is optional
* type: `boolean`

##### default Type


`boolean`







#### description

A short English-language description of the source

`description`
* is optional
* type: `string`

##### description Type


`string`








#### end_date

The age of the newest imagery or data in the source, as an RFC3339 date or leading portion of one

`end_date`
* is optional
* type: `string`

##### end_date Type


`string`


All instances must conform to this regular expression 
(test examples [here](https://regexr.com/?expression=%5E%5Cd%5Cd%5Cd%5Cd(-%5Cd%5Cd(-%5Cd%5Cd)%3F)%3F%24)):
```regex
^\d\d\d\d(-\d\d(-\d\d)?)?$
```








#### i18n

Whether the imagery name should be translated

`i18n`
* is optional
* type: `boolean`

##### i18n Type


`boolean`







#### icon

undefined

`icon`
* is optional
* type: `string`

##### icon Type


`string`








#### id

A unique identifier for the source; used in imagery_used changeset tag

`id`
* is **required**
* type: `string`

##### id Type


`string`


All instances must conform to this regular expression 
(test examples [here](https://regexr.com/?expression=%5E%5B-_.A-Za-z0-9%5D%2B%24)):
```regex
^[-_.A-Za-z0-9]+$
```








#### license

The license for the imagery specified using a SPDX identifier, or 'COMMERCIAL'

`license`
* is optional
* type: `string`

##### license Type


`string`








#### license_url

A URL for the license or permissions for the imagery

`license_url`
* is optional
* type: `string`

##### license_url Type


`string`








#### max_zoom

undefined

`max_zoom`
* is optional
* type: `integer`

##### max_zoom Type


`integer`
* minimum value: `1`








#### min_zoom

undefined

`min_zoom`
* is optional
* type: `integer`
* default: `0`


##### min_zoom Type


`integer`
* minimum value: `0`








#### name

The name of the imagery source

`name`
* is **required**
* type: `string`

##### name Type


`string`








#### overlay

'true' if tiles are transparent and can be overlaid on another source

`overlay`
* is optional
* type: `boolean`
* default: `"false"`


##### overlay Type


`boolean`







#### permission_osm

explicit/implicit permission by the owner for use in OSM

`permission_osm`
* is optional
* type: `enum`

The value of this property **must** be equal to one of the [known values below](#properties-known-values).

##### permission_osm Known Values
| Value | Description |
|-------|-------------|
| `explicit` |  |
| `implicit` |  |
| `no` |  |






#### start_date

The age of the oldest imagery or data in the source, as an RFC3339 date or leading portion of one

`start_date`
* is optional
* type: `string`

##### start_date Type


`string`


All instances must conform to this regular expression 
(test examples [here](https://regexr.com/?expression=%5E%5Cd%5Cd%5Cd%5Cd(-%5Cd%5Cd(-%5Cd%5Cd)%3F)%3F%24)):
```regex
^\d\d\d\d(-\d\d(-\d\d)?)?$
```








#### type

undefined

`type`
* is **required**
* type: `enum`

The value of this property **must** be equal to one of the [known values below](#properties-known-values).

##### type Known Values
| Value | Description |
|-------|-------------|
| `tms` |  |
| `wms` |  |
| `bing` |  |
| `scanex` |  |
| `wms_endpoint` |  |






#### url

A URL template for imagery tiles

`url`
* is **required**
* type: `string`

##### url Type


`string`











## type


`type`
* is optional
* type: `enum`
* defined in this schema

The value of this property **must** be equal to one of the [known values below](#type-known-values).

### type Known Values
| Value | Description |
|-------|-------------|
| `Feature` |  |



