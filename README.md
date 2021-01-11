# OSM Editor Layer Index

[![Build Status](https://github.com/osmlab/editor-layer-index/workflows/Deploy/badge.svg?branch=gh-pages)](https://github.com/osmlab/editor-layer-index/actions?query=branch%3Agh-pages+workflow%3ADeploy)

The goal of this project is to maintain a canonical representation of the layers available to [OpenStreetMap](https://www.openstreetmap.org/) editors such as:

* [iD](https://github.com/openstreetmap/iD)
* [Vespucci](http://vespucci.io/) (historically)
* [Go Map!!](https://wiki.openstreetmap.org/wiki/Go_Map!!) (historically)
* [Potlatch 2](https://github.com/systemed/potlatch2) and
* [JOSM](https://josm.openstreetmap.de/) (optional)

Both imagery and other raster data that is useful for mapping are within scope of the project.

This list is purely targeted at OpenStreetMap and does not include layers only useful for other projects such as [Open Historical Map](http://www.openhistoricalmap.org/) if the layers are not also useful for OpenStreetMap. With the way this list is structured it is easy to combine it with additional layer sources simply by copying the additional sources into their own directory and running `make`.

Some sources in this list are usable in OpenStreetMap because permission was specifically given to use them with OpenStreetMap and this permission does not extend to other projects.  See [FAQ.md](FAQ.md#what-imagery-licenses-are-compatible-with-this-index) for information about which imagery licenses are compatible with this index.

See [CONTRIBUTING.md](CONTRIBUTING.md) for info on how to contribute new sources to this index.


## Using this index

If you are using iD or Potlatch 2 you are already using this index!

For JOSM you can add `https://osmlab.github.io/editor-layer-index/imagery.xml` to the preference key `imagery.layers.sites` in advanced preferences. You probably want to remove the `https://josm.openstreetmap.de/maps` entry or you'll get the same layers listed twice.

For QGIS, [use the layer index converter script](https://github.com/andrewharvey/osm-editor-layer-index-qgis). You must check yourself whether the license allows you to use the layer(s) you are interested in.

For any other usage, use https://osmlab.github.io/editor-layer-index/imagery.geojson.

## Layer Overview

An interactive list of all layers (with a live map preview for most of them) is available at
https://osmlab.github.com/editor-layer-index.
