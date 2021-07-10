# OHM Editor Layer Index

[![Build Status](https://github.com/openhistoricalmap/ohm-editor-layer-index/workflows/Deploy/badge.svg?branch=main)](https://github.com/openhistoricalmap/ohm-editor-layer-index/actions?query=branch%3Amain+workflow%3ADeploy)

The goal of this project is to maintain a canonical representation of the layers available to [OpenHistoricalMap](https://www.openhistoricalmap.org/) editors such as:

* [iD](https://github.com/openstreetmap/iD)
* [Potlatch 2](https://github.com/systemed/potlatch2) and
* [JOSM](https://josm.openstreetmap.de/) (optional)

Both imagery and other raster data that is useful for mapping are within scope of the project.

This list is purely targeted at OpenHistoricalMap and does not include layers only allow for use in OpenStreetMap.

See [CONTRIBUTING.md](CONTRIBUTING.md) for info on how to contribute new sources to this index.


## Using this index

If you are using iD or Potlatch 2 you are already using this index!

For JOSM you can add `https://openhistoricalmap.github.io/ohm-editor-layer-index/imagery.xml` to the preference key `imagery.layers.sites` in advanced preferences. If you're running a separate JOSM profile for OHM, you probably want to remove the `https://josm.openstreetmap.de/maps` entry.

For QGIS, [use the layer index converter script](https://github.com/andrewharvey/osm-editor-layer-index-qgis). You must check yourself whether the license allows you to use the layer(s) you are interested in.

For any other usage, use https://openhistoricalmap.github.io/ohm-editor-layer-index/imagery.geojson.

## Layer Overview

An interactive list of all layers (with a live map preview for most of them) is available at
https://openhistoricalmap.github.io/ohm-editor-layer-index.
