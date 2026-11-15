## What imagery licenses are compatible with this index?

- :white_check_mark: "Public Domain" or [Creative Commons (CC0)](https://creativecommons.org/share-your-work/public-domain/cc0/)
imagery sources are directly compatible with tracing on OpenStreetMap and do not
require any additional permission.  Attribution of a Public Domain source is
not required, but is encouraged, to appear in the .geojson source file.

- :white_check_mark: [Open Government Licence (OGL)](http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
imagery sources are also compatible with tracing and do not require any additional
permission.  Attribution of an OGL source is required to appear in the .geojson source file.

- :white_check_mark: [Data licence Germany - Zero - Version 2.0 (dl-zero-de/2.0)](https://www.govdata.de/dl-de/zero-2-0)
imagery sources are directly compatible with tracing on OpenStreetMap and do not
require any additional permission.  Attribution of such a source is
not required, but is encouraged, to appear in the .geojson source file.

- :question: [Creative Commons with condition (CC BY, CC BY-NC, CC BY-SA)](https://creativecommons.org/share-your-work/licensing-types-examples/) imagery sources are compatible with tracing on
OpenStreetMap on the condition of obtaining a waiver or permission from the publishing organization
by using either the [CC BY waiver or aerial imagery tracing waiver for Creative Commons](#where-can-i-find-an-imagery-license-waiver).

- :question: For any other imagery sources - open an issue and we will look into it!
There may be language in the imagery metadata or elsewhere on the owning organizations's
website that makes things clear.  In situations where the license is unclear, you
can also request the owning organization to grant permission using the
[general waiver](#where-can-i-find-an-imagery-license-waiver).


## Where can I find an imagery license waiver?

Visit the [OpenStreetMap Foundation's Waiver and Permission Templates](https://wiki.osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates) choose one of the waiver templates.<br/>

- CC BY 4.0 licensed imagery may use either
  - [waiver template for CC BY 4.0](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Cover_letter_and_waiver_template_for_CC_BY_4.0), or
  - [aerial imagery waiver - general waiver](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Template_text_for_aerial_imagery_waivers#For_an_OSM_waiver_generally:)
  - [aerial imagery waiver - CC BY/CC BY-NC/CC BY-SA](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Template_text_for_aerial_imagery_waivers#For_a_tracing_waiver_as_to_imagery_already.2Fto_be_released_under_CC_BY.2FCC_BY-NC.2FCC_BY-SA:)
- CC BY 3.0/2.0 licensed imagery may use either
  - [waiver template for CC BY 3.0/2.0](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Cover_letter_and_waiver_template_for_CC_BY_2.0-3.0)
  - [aerial imagery waiver - general waiver](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Template_text_for_aerial_imagery_waivers#For_an_OSM_waiver_generally:)
  - [aerial imagery waiver - CC BY/CC BY-NC/CC BY-SA](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Template_text_for_aerial_imagery_waivers#For_a_tracing_waiver_as_to_imagery_already.2Fto_be_released_under_CC_BY.2FCC_BY-NC.2FCC_BY-SA:)
- [CC BY](https://creativecommons.org/licenses/by/4.0/)/[CC BY-NC](https://creativecommons.org/licenses/by-nc/4.0/)/[CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/) licensed imagery may use either
  - [waiver template for CC BY 4.0](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Cover_letter_and_waiver_template_for_CC_BY_4.0), or
  - [aerial imagery waiver - general waiver](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Template_text_for_aerial_imagery_waivers#For_an_OSM_waiver_generally:)
  - [aerial imagery waiver - CC BY/CC BY-NC/CC BY-SA](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Template_text_for_aerial_imagery_waivers#For_a_tracing_waiver_as_to_imagery_already.2Fto_be_released_under_CC_BY.2FCC_BY-NC.2FCC_BY-SA:)
- Copyrighted imagery or imagery under any other license map use
  - [aerial imagery waiver - general waiver](https://osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates/Template_text_for_aerial_imagery_waivers#For_an_OSM_waiver_generally:)

Completed imagery waivers should be stored in this repository in the same location
as the corresponding .geojson source files.  Please save the completed waiver as
a .pdf, using the a similar name as the .geojson source file.<br/>
(For example `NYS2017-orthos.geojson`, `NYS2017-orthos-waiver.pdf`)


## How can I draw a bounding polygon?

You can use http://geojson.io to draw a polygon.

[Download.geofabrik.de](https://download.geofabrik.de/) has free .poly files that geojson.io can import.

Geojson.io will even let you add a tile-based imagery layer to the map.  This lets
you see where the imagery is valid.

1. Choose Meta -> Add raster tile layer from the menu
2. Enter the url, as you would if you were adding the source as a custom layer in iD.
Note: you do need to use `{z}` instead of `{zoom}` on geojson.io

Tips for drawing the polygon:

1. Click "Draw Polygon" button to get started - it looks like a pentagon shape.
2. You don't need to be super detailed, just roughly trace around where the imagery is valid.
3. Double click to stop drawing.
4. If you want to change the shape, click the "Edit Layers" button - it looks like a square with pencil in it.
5. In edit mode you can move or click once to delete existing points, or drag midpoints to create new points.

