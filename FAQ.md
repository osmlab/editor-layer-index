## What imagery licenses are compatible with this index?

- :white_check_mark: "Public domain" or [Creative Commons (CC0)](https://creativecommons.org/share-your-work/public-domain/cc0/)
imagery sources are directly compatible with tracing on OpenStreetMap and do not
require any additional permission!

- :question: [Creative Commons with condition (CC BY, CC BY-NC, CC BY-SA)](https://creativecommons.org/share-your-work/licensing-types-examples/) imagery sources are generally compatible with tracing on
OpenStreetMap, however you should request the owning organization to grant
permission using the [creative commons waiver](#where-can-i-find-an-imagery-license-waiver).

- :question: For any other imagery sources - open an issue and we will look into it!
There may be language in the imagery metadata or elsewhere on the owning organizations's
website that makes things clear.  In situations where the license is unclear, you
can also request the owning organization to grant permission using the
[general waiver](#where-can-i-find-an-imagery-license-waiver).


## Where can I find an imagery license waiver?

Visit the link below and choose the link for "Template text for aerial imagery waivers".<br/>
Within that document are variations for general and creative commons waivers.

https://wiki.osmfoundation.org/wiki/Licence/Waiver_and_Permission_Templates


## How can I draw a bounding polygon?

You can use http://geojson.io to draw a polygon.

Geojson.io will even let you add a tile-based imagery layer to the map.  This lets
you see where the imagery is valid.

1. Choose Meta -> Add map layer from the menu
2. Enter the url, as you would if you were adding the source as a custom layer in iD.
Note: you do need to use `{z}` instead of `{zoom}` on geojson.io

Tips for drawing the polygon:

1. Click "Draw A Polygon" button to get started - it looks like a pentagon shape.
2. You don't need to be super detailed, just roughly trace around where the imagery is valid.
3. Double click to stop drawing.
4. If you want to change the shape, click the "Edit Layers" button - it looks like a square with pencil in it.
5. In edit mode you can move or click once to delete exising points, or drag midpoints to create new points.


