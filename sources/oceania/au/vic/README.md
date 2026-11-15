## City of Melbourne

City of Melbourne imagery processed with https://gitlab.com/andrewharvey/city-of-melbourne-cogeo and hosted on openstreetmap.org imagery service.

## Vicmap

### Filtering a WMS layer

The `cql_filter` parameter can be set to filter the data shown using the [CQL query langauge for GeoServer](https://docs.geoserver.org/main/en/user/tutorials/cql/cql_tutorial.html#cql-tutorial).

For example using `cql_filter=status=%27A%27` on the "Vicmap-property_view" layer would filter where the `status` attribute is `A` (Assigned, as opposed to P for Proposed).

### User supplied styles

A WMS layer can have a custom style following the SLD schema.

We have some custom SLDs in the `sld` directory. To convert these into the URL parameter use

    xmlstarlet format --noindent Address.xml | tr -d '\n\t\r' | jq -sRr @uri

This will compact the XML by removing indents and new lines, then URL encode it.

Then use that value for the `sld_body=` URL parameter.

    https://opendata.maps.vic.gov.au/geoserver/wms?service=wms&version=1.3.0&request=getmap&format=image%2Fpng&transparent=true&width={width}&height={height}&crs={proj}&bbox={bbox}&layers=open-data-platform:property_view&sld_body=
