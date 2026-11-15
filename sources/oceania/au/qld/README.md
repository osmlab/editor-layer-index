# ArcGIS Services

[Queensland's Natural Resources and Mines, Manufacturing and Regional and Rural Development spatial open data](https://www.data.qld.gov.au/dataset/?organization=resources) is mostly provided as data downloads and ArcGIS REST Services via https://spatial-gis.information.qld.gov.au/arcgis/rest/services/.

We make use of these ArcGIS REST Services to provide custom overlay layers to OpenStreetMap editors via the [MapServer /export feature](https://spatial-gis.information.qld.gov.au/arcgis/help/en/rest/services-reference/enterprise/export-map/)

_We must provide the `imageSR={wkid}` and `bboxSR={wkid}` since some services aren't defaulted to EPSG:3857._

## Adding raster tile services

Some services are available as WMTS raster tiles, these are added directly either into the JOSM index via the WMTS Capabilities URL such as

    https://spatial-gis.information.qld.gov.au/arcgis/rest/services/Basemaps/QldMap_Lite/MapServer/WMTS/1.0.0/WMTSCapabilities.xml

Or into iD as the XYZ tile URL such as

    https://spatial-gis.information.qld.gov.au/arcgis/rest/services/Basemaps/QldMap_Lite/MapServer/WMTS/tile/1.0.0/Basemaps_QldMap_Lite/default/GoogleMapsCompatible/{zoom}/{x}/{y}.png

## Adding a service as-is

Some services we can add using the provided styling and layer selection, in that case we can use the URL

    https://spatial-gis.information.qld.gov.au/arcgis/rest/services/Transportation/RoadsAndTracks/MapServer/export?imageSR={wkid}&bboxSR={wkid}&bbox={bbox}&format=png32&size={width},{height}&transparent=true&f=image

This returns back EPSG:3857 tiles given a tile bbox including all layers from the service and using the default style.

## Adding selected layers as-is

To show only selected layers from the service you can pass `layers=show:0` based on the syntax

    // Where layerId1 and layerId2 are the layer ids returned by the  map service resource
    [show | hide | include | exclude]:layerId1,layerId2

## Applying your own style

Where you want to restyle selected layers from a service you need to pass your custom "Dynamic Layers" field with your own ["Drawing Info"](https://developers.arcgis.com/web-map-specification/objects/drawingInfo/). We do this for the [NSW Land Parcel Property Theme](https://portal.spatial.nsw.gov.au/server/rest/services/NSW_Land_Parcel_Property_Theme/MapServer), [Lot layer](https://portal.spatial.nsw.gov.au/server/rest/services/NSW_Land_Parcel_Property_Theme/MapServer/8), you can see in the service that the default style is

    Renderer:
        Simple Renderer:
        Symbol:
            Style: esriSFSSolid
            Color: [201, 249, 252, 255]
            Outline:
                Style: esriSLSSolid
                Color: [110, 110, 110, 255]
                Width: 0
        Label: N/A
        Description: N/A
    Transparency: 0
    Labeling Info:

Instead we use the following value for Dynamic Layers, which uses a transparent fill, and a white outline

    [
      {
        "id": 8,
        "source": {
          "type": "mapLayer",
          "mapLayerId": 8
        },
        "drawingInfo": {
          "renderer": {
            "type": "simple",
            "symbol": {
              "type": "esriSFS",
              "style": "esriSFSSolid",
              "color": [0,0,0,0],
              "outline": {
                "type": "esriSLS",
                "style": "esriSLSolid",
                "color": [255, 255, 255, 255],
                "width": 1
              }
            }
          }
        }
      }
    ]

We use the format `png32` as this provides smooth lines given the transparent background.

    https://portal.spatial.nsw.gov.au/server/rest/services/NSW_Land_Parcel_Property_Theme/MapServer/export?layers=show%3A8&imageSR={wkid}&bboxSR={wkid}&bbox={bbox}&format=png32&size={width},{height}&transparent=true&f=image&dynamicLayers=%5B%0D%0A%7B%0D%0A%22id%22%3A8%2C%0D%0A%22source%22%3A%7B%0D%0A%22type%22%3A%22mapLayer%22%2C%0D%0A%22mapLayerId%22%3A8%0D%0A%7D%2C%0D%0A%22drawingInfo%22%3A%7B%0D%0A%22renderer%22%3A%7B%0D%0A%22type%22%3A%22simple%22%2C%0D%0A%22symbol%22%3A%7B%0D%0A%22type%22%3A%22esriSFS%22%2C%0D%0A%22style%22%3A%22esriSFSSolid%22%2C%0D%0A%22color%22%3A%5B0%2C0%2C0%2C0%5D%2C%0D%0A%22outline%22%3A%7B%0D%0A%22type%22%3A%22esriSLS%22%2C%0D%0A%22style%22%3A%22esriSLSolid%22%2C%0D%0A%22color%22%3A%5B255%2C255%2C255%2C255%5D%2C%0D%0A%22width%22%3A1%0D%0A%7D%0D%0A%7D%0D%0A%7D%0D%0A%7D%0D%0A%7D%5D

To create a URL Encoded value to add to the end of the url with `dynamicLayers=` you can use `jq --compact-output . < dynamiclayers/*.json | jq -Rr @uri`
