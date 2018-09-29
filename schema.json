{
    "$schema": "http://json-schema.org/draft-04/schema#",
    "id": "https://github.com/osmlab/editor-layer-index",
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "Feature"
            ]
        },
        "bbox": {
            "$ref": "http://json.schemastore.org/geojson#/properties/bbox"
        },
        "geometry": {
            "$ref": "http://json.schemastore.org/geojson#/definitions/geometry"
        },
        "properties": {
            "type": "object",
            "additionalProperties": false,
            "required": [
                "id",
                "type",
                "url",
                "name"
            ],
            "properties": {
                "name": {
                    "description": "The name of the imagery source",
                    "type": "string"
                },
                "i18n": {
                    "description": "Whether the imagery name should be translated",
                    "type": "boolean"
                },
                "type": {
                    "type": "string",
                    "enum": [
                        "tms",
                        "wms",
                        "bing",
                        "scanex",
                        "wms_endpoint"
                    ]
                },
                "url": {
                    "description": "A URL template for imagery tiles",
                    "type": "string"
                },
                "min_zoom": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 0
                },
                "max_zoom": {
                    "type": "integer",
                    "minimum": 1
                },
                "permission_osm": {
                    "description": "explicit/implicit permission by the owner for use in OSM",
                    "type": "string",
                    "enum": [
                        "explicit",
                        "implicit",
                        "no"
                    ]
                },
                "license": {
                    "description": "The license for the imagery specified using a SPDX identifier, or 'COMMERCIAL'",
                    "type": "string"
                },
                "license_url": {
                    "description": "A URL for the license or permissions for the imagery",
                    "type": "string"
                },
                "id": {
                    "description": "A unique identifier for the source; used in imagery_used changeset tag",
                    "pattern": "^[-_.A-Za-z0-9]+$",
                    "type": "string"
                },
                "description": {
                    "description": "A short English-language description of the source",
                    "type": "string"
                },
                "country_code": {
                    "description": "The ISO 3166-1 alpha-2 two letter country code in upper case. Use ZZ for unknown or multiple.",
                    "type": "string",
                    "pattern": "^[A-Z]{2}$"
                },
                "default": {
                    "description": "Whether this imagery should be shown in the default world-wide menu",
                    "type": "boolean"
                },
                "best": {
                    "description": "Whether this imagery is the best source for the region",
                    "type": "boolean"
                },
                "start_date": {
                    "description": "The age of the oldest imagery or data in the source, as an RFC3339 date or leading portion of one",
                    "type": "string",
                    "pattern": "^\\d\\d\\d\\d(-\\d\\d(-\\d\\d)?)?$"
                },
                "end_date": {
                    "description": "The age of the newest imagery or data in the source, as an RFC3339 date or leading portion of one",
                    "type": "string",
                    "pattern": "^\\d\\d\\d\\d(-\\d\\d(-\\d\\d)?)?$"
                },
                "overlay": {
                    "description": "'true' if tiles are transparent and can be overlaid on another source",
                    "type": "boolean",
                    "default": "false"
                },
                "available_projections": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "attribution": {
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
                    "additionalProperties": false
                },
                "icon": {
                    "type": "string"
                }
            }
        }
    }
}
