# Existing validation findings

Snapshot: upstream `9cc9c95e`, used for tooling PR #3090. These findings are unresolved and remain visible as warnings; the baseline binds each exception to exact source content. No sources have been changed.

## Metadata findings

| Source | Finding | Existing values |
| --- | --- | --- |
| [Bayonne - Petit et Grand Bayonne 2019](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/Bayonne-2019.geojson) | Missing category | `category` absent |
| [City of Langley Aerial Imagery (2025)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/ca/bc/City_Of_Langley_2025.geojson) | ArcGIS image URL must use /export or /exportImage, not service metadata | `https://maps.langleycity.ca/server/rest/services/Maps/Imagery2025/MapServer` |
| [Mecklenburg County Orthoimagery (Latest)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/nc/Mecklenburg_NC_Latest.geojson) | ArcGIS image URL must use /export or /exportImage, not service metadata | `https://meckaerial.mecklenburgcountync.gov/server/rest/services/Aerial_Latest/ImageServer` |
| [NLS - OS 25-inch (Scotland), 1892-1905](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/gb/NLS-OS25InchScotland1892-1905.geojson) | Missing category | `category` absent |
| [MLIT Plateau Official](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/asia/jp/JapanMLIT-PlateauOfficial.geojson) | end_date is not a real calendar date: 2020-11-31 | `2020-11-31` |
| [Basemap geoportail.lu](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/lu/Luxembourg-GeoportailBasemap.geojson) | Missing category | `category` absent |
| [Basemap geoportail.lu](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/lu/Luxembourg-GeoportailBasemap.geojson) | start_date is after end_date | `2013-07-19` → `2010-07-20` |
| [Cadastre geoportail.lu](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/lu/Luxembourg-GeoportailCadastre.geojson) | Missing category | `category` absent |
| [Topographical Map geoportail.lu](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/lu/Luxembourg-GeoportailTopo.geojson) | Missing category | `category` absent |
| [Topographical Map geoportail.lu](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/lu/Luxembourg-GeoportailTopo.geojson) | start_date is after end_date | `2013-07-19` → `2010-07-20` |
| [Powiat lubaczowski: Buildings](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pl/PowiatlubaczowskiBuildings.geojson) | Missing category | `category` absent |

## Significant best-layer overlaps

**106 pairs**, not 106 necessarily incorrect sources. An overlap qualifies when it covers at least 10% of the smaller footprint and at least 1 km². Areas are WGS84 geodesic measurements of declared footprints, not measurements of actual imagery availability.

All regional `best` layers participate, including different categories, overlays, and alternative WMS/TMS representations. National/regional nesting and alternative transports can be intentional; these findings need editorial review before removing flags or cutting geometry.

| Countries | Pairs |
| --- | --- |
| BE | 1 |
| BE / DE | 1 |
| CH | 11 |
| CH / DE | 1 |
| CH / FR | 2 |
| CZ | 1 |
| DE | 15 |
| DE / FR | 1 |
| DE / NL | 2 |
| ES | 16 |
| FI | 7 |
| FR | 6 |
| HR | 2 |
| MD | 20 |
| NZ | 1 |
| PL | 3 |
| PT | 3 |
| SE | 6 |
| US | 6 |
| ZA | 1 |

### BE (1 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Digitaal Vlaanderen most recent aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/be/DV_OrthoPhoto.geojson) | [CIRB/CIBG most recent aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/be/UrbIS_OrthoPhoto.geojson) | 176.15 | 100.0% | photo; tms / photo; wms |

### BE / DE (1 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [SPW(allonie) most recent aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/be/SPW_OrthoPhoto.geojson) | [Aachen Liegenschaftskataster](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/aachen_alkis.geojson) | 169.58 | 14.9% | photo; wms / other; wms |

### CH (11 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Kanton Aargau 20cm (AGIS 2025)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonAargau20cm-AGIS2025.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 1,790.18 | 95.5% | photo; tms / photo; wms |
| [Stadt Bern 10cm (2023)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/Stadt_Bern-Orthofotos-2023-WMTS.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 87.11 | 100.0% | photo; wms / photo; wms |
| [Canton de Génève, Orthophoto 2024 (4cm) (SITG)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/Canton_de_Geneve_orthophoto2024_4cm.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 367.27 | 88.3% | photo; tms / photo; wms |
| [Kanton Basel-Stadt 2023](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonBasel-Stadt2023.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 58.53 | 88.8% | photo; wms / photo; wms |
| [Kanton Zurich, Orthofoto ZH Sommer 2024/25 RGB 5cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/Kanton_Zurich_ortho_2024_wms.geojson) | [Kanton Zug Neuheim 2020 3.5 cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonZug2020wms.geojson) | 6.07 | 38.8% | photo; wms / photo; wms |
| [Kanton Zurich, Orthofoto ZH Sommer 2024/25 RGB 5cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/Kanton_Zurich_ortho_2024_wms.geojson) | [Kanton Zug Menzingen 2021 6.5 cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonZug2021wms.geojson) | 19.58 | 35.0% | photo; wms / photo; wms |
| [Kanton Zurich, Orthofoto ZH Sommer 2024/25 RGB 5cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/Kanton_Zurich_ortho_2024_wms.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 1,852.20 | 99.9% | photo; wms / photo; wms |
| [Kanton Zug (Walchwil und Zug (Alpli)) 2019](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonZug2019wms.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 27.77 | 100.0% | photo; wms / photo; wms |
| [Kanton Zug Neuheim 2020 3.5 cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonZug2020wms.geojson) | [Kanton Zug Menzingen 2021 6.5 cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonZug2021wms.geojson) | 9.59 | 61.4% | photo; wms / photo; wms |
| [Kanton Zug Neuheim 2020 3.5 cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonZug2020wms.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 15.62 | 100.0% | photo; wms / photo; wms |
| [Kanton Zug Menzingen 2021 6.5 cm](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonZug2021wms.geojson) | [swisstopo SWISSIMAGE](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/swisstopo_swissimage.geojson) | 55.97 | 100.0% | photo; wms / photo; wms |

### CH / DE (1 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Baden-Württemberg DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Baden-Württemberg-DOP20.geojson) | [Kanton Basel-Stadt 2023](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonBasel-Stadt2023.geojson) | 13.27 | 20.1% | photo; wms / photo; wms |

### CH / FR (2 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Canton de Génève, Orthophoto 2024 (4cm) (SITG)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/Canton_de_Geneve_orthophoto2024_4cm.geojson) | [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | 206.07 | 49.5% | photo; tms / photo; tms |
| [Kanton Basel-Stadt 2023](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/ch/KantonBasel-Stadt2023.geojson) | [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | 11.36 | 17.2% | photo; wms / photo; tms |

### CZ (1 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Czechia CUZK orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/cz/CzechCUZK_ortophoto.geojson) | [Praha IPR low-vegetation orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/cz/PrahaIPRlow-vegetationorthophoto.geojson) | 661.41 | 100.0% | photo; wms / photo; wms |

### DE (15 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Baden-Württemberg DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Baden-Württemberg-DOP20.geojson) | [Ludwigshafen 2022](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Ludwigshafen-2022.geojson) | 17.03 | 11.1% | photo; wms / photo; wms |
| [Baden-Württemberg DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Baden-Württemberg-DOP20.geojson) | [Stuttgart Luftbild Stadtmessungsamt](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Stuttgart-latest.geojson) | 867.02 | 100.0% | photo; wms / photo; wms |
| [Berlin/Geoportal DOP20RGB (2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Berlinaerialphotograph2026.geojson) | [Brandenburg GeoBasis-DE/LGB (latest) / DOP20c](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Brandenburg-DOP20c.geojson) | 1,121.17 | 100.0% | photo; tms / photo; wms |
| [Saxony latest aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Saxony-DOP20-latest.geojson) | [Saxony raw aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Saxony-DOP20-raw.geojson) | 19,758.30 | 100.0% | photo; wms / photo; wms |
| [Köln TrueDOP 2024](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Köln-TrueDOP-2024.geojson) | [NRW Orthophoto (RGB)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/NRW_ortho_wms.geojson) | 443.02 | 100.0% | photo; wms / photo; wms |
| [© GeoBasis-DE/LVermGeo LSA, ALKIS Cadastre parcels](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_ALKIS_CP.geojson) | [© GeoBasis-DE/LVermGeo LSA, ALKIS Building Outlines](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_ALKIS_BU.geojson) | 21,283.50 | 100.0% | map overlay; wms / other overlay; wms |
| [© GeoBasis-DE/LVermGeo LSA, ALKIS Cadastre parcels](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_ALKIS_CP.geojson) | [© GeoBasis-DE/LVermGeo LSA, DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_DOP20.geojson) | 21,283.50 | 100.0% | map overlay; wms / photo; wms |
| [© GeoBasis-DE/LVermGeo LSA, ALKIS Cadastre parcels](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_ALKIS_CP.geojson) | [© GeoBasis-DE/LVermGeo LSA, Digital administrative boundaries](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_DVG.geojson) | 21,283.50 | 100.0% | map overlay; wms / map overlay; wms |
| [© GeoBasis-DE/LVermGeo LSA, ALKIS Building Outlines](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_ALKIS_BU.geojson) | [© GeoBasis-DE/LVermGeo LSA, DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_DOP20.geojson) | 21,283.50 | 100.0% | other overlay; wms / photo; wms |
| [© GeoBasis-DE/LVermGeo LSA, ALKIS Building Outlines](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_ALKIS_BU.geojson) | [© GeoBasis-DE/LVermGeo LSA, Digital administrative boundaries](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_DVG.geojson) | 21,283.50 | 100.0% | other overlay; wms / map overlay; wms |
| [© GeoBasis-DE/LVermGeo LSA, DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_DOP20.geojson) | [© GeoBasis-DE/LVermGeo LSA, Digital administrative boundaries](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/SaxonyAnhalt_DVG.geojson) | 21,283.50 | 100.0% | photo; wms / map overlay; wms |
| [Ludwigshafen 2022](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Ludwigshafen-2022.geojson) | [Rheinland-Pfalz DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Rheinland-Pfalz-DOP20.geojson) | 139.66 | 91.0% | photo; wms / photo; wms |
| [Rheinland-Pfalz DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Rheinland-Pfalz-DOP20.geojson) | [Worms 2025](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Worms-2025.geojson) | 113.60 | 100.0% | photo; wms / photo; wms |
| [Aachen Liegenschaftskataster](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/aachen_alkis.geojson) | [NRW Orthophoto (RGB)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/NRW_ortho_wms.geojson) | 942.11 | 82.5% | other; wms / photo; wms |
| [NRW Orthophoto (RGB)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/NRW_ortho_wms.geojson) | [ALKIS Kreis Viersen](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/viersen_alkis.geojson) | 642.80 | 98.1% | photo; wms / other; wms |

### DE / FR (1 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Saarland DOP20](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/Saarland-DOP20.geojson) | [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | 351.56 | 11.8% | photo; wms / photo; tms |

### DE / NL (2 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [PDOK aerial imagery Beeldmateriaal.nl 8cm (WMTS) latest](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/nl/PDOK-Luchtfoto-Beeldmateriaal-OrthoHR-latest.geojson) | [Aachen Liegenschaftskataster](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/aachen_alkis.geojson) | 118.36 | 10.4% | photo; tms / other; wms |
| [PDOK aerial imagery Beeldmateriaal.nl 8cm (WMTS) latest](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/nl/PDOK-Luchtfoto-Beeldmateriaal-OrthoHR-latest.geojson) | [ALKIS Kreis Viersen](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/de/viersen_alkis.geojson) | 125.67 | 19.2% | photo; tms / other; wms |

### ES (16 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [GRAFCAN Ortofoto Urbana de alta resolución](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/GRAFCAN-Urbana.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | 11,170.83 | 100.0% | photo; wms / photo; wms |
| [GRAFCAN Ortofoto Urbana de alta resolución](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/GRAFCAN-Urbana.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | 11,170.83 | 100.0% | photo; wms / photo; tms |
| [ICGC - Ortofoto de Catalunya](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/ICGC.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | 35,263.81 | 100.0% | photo; wms / photo; wms |
| [ICGC - Ortofoto de Catalunya](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/ICGC.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | 35,263.81 | 100.0% | photo; wms / photo; tms |
| [IDEIB - Ortofoto més recent de les Illes Balears](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/ideib_balears.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | 53,694.72 | 100.0% | photo; wms / photo; wms |
| [IDEIB - Ortofoto més recent de les Illes Balears](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/ideib_balears.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | 53,694.72 | 100.0% | photo; wms / photo; tms |
| [ITACyL - Castilla y León](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/ITACyL-CastileandLen.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | 99,285.85 | 99.1% | photo; wms / photo; wms |
| [ITACyL - Castilla y León](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/ITACyL-CastileandLen.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | 99,285.85 | 99.1% | photo; wms / photo; tms |
| [ITACyL - Castilla y León](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/ITACyL-CastileandLen.geojson) | [geoEuskadiren Ortoargazkiak](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/geoEuskadi.geojson) | 974.44 | 11.1% | photo; wms / photo; wms |
| [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | 895,348.17 | 100.0% | photo; wms / photo; tms |
| [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | [SITNA Ortofoto de máxima actualidad](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/SITNA.geojson) | 10,715.56 | 100.0% | photo; wms / photo; wms |
| [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | [geoEuskadiren Ortoargazkiak](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/geoEuskadi.geojson) | 8,749.69 | 100.0% | photo; wms / photo; wms |
| [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain.geojson) | [Ayuntamiento de Madrid - Ortofoto actualizada](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/madrid-ayto-geoportal.geojson) | 604.16 | 100.0% | photo; wms / photo; wms |
| [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | [SITNA Ortofoto de máxima actualidad](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/SITNA.geojson) | 10,715.56 | 100.0% | photo; tms / photo; wms |
| [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | [geoEuskadiren Ortoargazkiak](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/geoEuskadi.geojson) | 8,749.69 | 100.0% | photo; tms / photo; wms |
| [PNOA Spain](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/PNOASpain-TMS.geojson) | [Ayuntamiento de Madrid - Ortofoto actualizada](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/es/madrid-ayto-geoportal.geojson) | 604.16 | 100.0% | photo; tms / photo; wms |

### FI (7 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Helsinki region orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/hri-orto.geojson) | [MML Orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/mml-orto.geojson) | 2,765.73 | 100.0% | photo; wms / photo; wms |
| [MML Orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/mml-orto.geojson) | [Tampere aerial imagery 2022](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/tampere-aerial-2022.geojson) | 241.84 | 100.0% | photo; wms / historicphoto; wms |
| [MML Orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/mml-orto.geojson) | [Tampere aerial imagery 2025](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/tampere-aerial-2025.geojson) | 285.67 | 100.0% | photo; wms / photo; wms |
| [MML Orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/mml-orto.geojson) | [City of Turku ortophoto - 2021](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/turku-orto-2021.geojson) | 299.73 | 100.0% | photo; wms / photo; wms |
| [MML Orthophoto](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/mml-orto.geojson) | [City of Turku topographic map](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/turku-topo.geojson) | 497.09 | 100.0% | photo; wms / map overlay; wms |
| [Tampere aerial imagery 2022](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/tampere-aerial-2022.geojson) | [Tampere aerial imagery 2025](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/tampere-aerial-2025.geojson) | 228.20 | 94.4% | historicphoto; wms / photo; wms |
| [City of Turku ortophoto - 2021](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/turku-orto-2021.geojson) | [City of Turku topographic map](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fi/turku-topo.geojson) | 290.15 | 96.8% | photo; wms / map overlay; wms |

### FR (6 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Eurométropole de Strasbourg - Orthophotographie 2022](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/Eurometropole-de-Strasbourg-Orthophoto-2022.geojson) | [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | 351.91 | 100.0% | photo; wms / photo; tms |
| [Nancy - Orthophoto - 2025](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/Nancy-Orthophoto-2025.geojson) | [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | 284.51 | 100.0% | photo; wms / photo; tms |
| [Toulouse - Orthophotoplan 2019](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/Toulouse-Orthophotoplan2019.geojson) | [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | 581.73 | 100.0% | historicphoto; tms / photo; tms |
| [Toulouse - Orthophotoplan 2019](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/Toulouse-Orthophotoplan2019.geojson) | [PCRS raster](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/PCRS.geojson) | 581.73 | 100.0% | historicphoto; tms / photo; wms |
| [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | [PCRS raster](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/PCRS.geojson) | 41,486.90 | 100.0% | photo; tms / photo; wms |
| [BD Ortho IGN](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/BDOrthoIGN.geojson) | [Lyon Orthophoto plus récente](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/fr/Lyon-Orthophoto-plus-recente.geojson) | 1,220.40 | 100.0% | photo; tms / photo; wms |

### HR (2 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [dgu.hr: Croatia 2023-2024 aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/hr/dgu-dof-2023-2024.geojson) | [gis-rijeka: Rijeka 2020 aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/hr/gis-rijeka-2020.geojson) | 60.91 | 100.0% | photo; wms / photo; tms |
| [dgu.hr: Croatia 2023-2024 aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/hr/dgu-dof-2023-2024.geojson) | [osm-hr: Zagreb 2018 Aerial imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/hr/osm-hr-zagreb-2018.geojson) | 882.67 | 100.0% | photo; wms / photo; tms |

### MD (20 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Chișinău Municipality Orthophoto (2014)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2014_Chisinau.geojson) | [Moldova Composite Orthophoto (2016+2020+2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova_Extended.geojson) | 743.80 | 100.0% | historicphoto; wms / photo; wms |
| [Chișinău Municipality Orthophoto (2014)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2014_Chisinau.geojson) | [Moldova Orthophoto (2016)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova.geojson) | 738.06 | 99.2% | historicphoto; wms / photo; wms |
| [Chișinău Municipality Orthophoto (2014)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2014_Chisinau.geojson) | [Moldova Orthophoto, Center part (2020)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2020_Centru.geojson) | 743.80 | 100.0% | historicphoto; wms / photo; wms |
| [Chișinău Municipality Orthophoto (2014)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2014_Chisinau.geojson) | [Moldova Satellite Orthophoto (2025-2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Satellite_Orthophoto_2026_Moldova.geojson) | 743.80 | 100.0% | historicphoto; wms / photo; wms |
| [Chișinău Municipality Orthophoto (2014)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2014_Chisinau.geojson) | [Topographical Linemap of Moldova, 2017](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Topographical_Linemap_2017.geojson) | 743.80 | 100.0% | historicphoto; wms / map; wms |
| [Moldova Composite Orthophoto (2016+2020+2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova_Extended.geojson) | [Moldova Orthophoto (2016)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova.geojson) | 30,123.35 | 100.0% | photo; wms / photo; wms |
| [Moldova Composite Orthophoto (2016+2020+2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova_Extended.geojson) | [Moldova Orthophoto, Center part (2020)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2020_Centru.geojson) | 10,736.82 | 99.9% | photo; wms / photo; wms |
| [Moldova Composite Orthophoto (2016+2020+2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova_Extended.geojson) | [Moldova Orthophoto, South part (2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2021_South.geojson) | 9,868.94 | 100.0% | photo; wms / photo; wms |
| [Moldova Composite Orthophoto (2016+2020+2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova_Extended.geojson) | [Moldova Satellite Orthophoto (2025-2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Satellite_Orthophoto_2026_Moldova.geojson) | 30,942.68 | 96.7% | photo; wms / photo; wms |
| [Moldova Composite Orthophoto (2016+2020+2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova_Extended.geojson) | [Topographical Linemap of Moldova, 2017](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Topographical_Linemap_2017.geojson) | 30,148.77 | 99.7% | photo; wms / map; wms |
| [Moldova Orthophoto (2016)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova.geojson) | [Moldova Orthophoto, Center part (2020)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2020_Centru.geojson) | 10,009.00 | 93.1% | photo; wms / photo; wms |
| [Moldova Orthophoto (2016)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova.geojson) | [Moldova Orthophoto, South part (2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2021_South.geojson) | 9,404.84 | 95.3% | photo; wms / photo; wms |
| [Moldova Orthophoto (2016)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova.geojson) | [Moldova Satellite Orthophoto (2025-2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Satellite_Orthophoto_2026_Moldova.geojson) | 29,803.75 | 98.9% | photo; wms / photo; wms |
| [Moldova Orthophoto (2016)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2016_Moldova.geojson) | [Topographical Linemap of Moldova, 2017](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Topographical_Linemap_2017.geojson) | 29,470.88 | 97.8% | photo; wms / map; wms |
| [Moldova Orthophoto, Center part (2020)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2020_Centru.geojson) | [Moldova Orthophoto, South part (2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2021_South.geojson) | 990.20 | 10.0% | photo; wms / photo; wms |
| [Moldova Orthophoto, Center part (2020)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2020_Centru.geojson) | [Moldova Satellite Orthophoto (2025-2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Satellite_Orthophoto_2026_Moldova.geojson) | 10,661.62 | 99.2% | photo; wms / photo; wms |
| [Moldova Orthophoto, Center part (2020)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2020_Centru.geojson) | [Topographical Linemap of Moldova, 2017](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Topographical_Linemap_2017.geojson) | 10,528.66 | 97.9% | photo; wms / map; wms |
| [Moldova Orthophoto, South part (2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2021_South.geojson) | [Moldova Satellite Orthophoto (2025-2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Satellite_Orthophoto_2026_Moldova.geojson) | 9,344.18 | 94.6% | photo; wms / photo; wms |
| [Moldova Orthophoto, South part (2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Orthophoto_2021_South.geojson) | [Topographical Linemap of Moldova, 2017](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Topographical_Linemap_2017.geojson) | 9,119.96 | 92.4% | photo; wms / map; wms |
| [Moldova Satellite Orthophoto (2025-2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Satellite_Orthophoto_2026_Moldova.geojson) | [Topographical Linemap of Moldova, 2017](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/md/Topographical_Linemap_2017.geojson) | 30,062.01 | 99.4% | photo; wms / map; wms |

### NZ (1 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [LINZ Auckland 2023](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/oceania/nz/LINZ-NZ-Auckland-2023.geojson) | [LINZ NZ Aerial Imagery](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/oceania/nz/LINZ-NZ-Aerial-Imagery.geojson) | 135.83 | 100.0% | photo; tms / photo; tms |

### PL (3 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Bytom: Orthophotomap 2021 (aerial image)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pl/BytomOrthophotomap2021(aerialimage).geojson) | [Geoportal 2: Orthophotomap (latest aerial imagery) (WMTS)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pl/Geoportal2Orthophotomap(aerialimage)_WMTS.geojson) | 99.20 | 100.0% | photo; wms / photo; tms |
| [Geoportal 2: Orthophotomap (latest aerial imagery) (WMTS)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pl/Geoportal2Orthophotomap(aerialimage)_WMTS.geojson) | [Poznań: Orthophotomap Bieżąca (aerial image)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pl/PoznaOrthophotomapBiezaca(aerialimage).geojson) | 380.79 | 100.0% | photo; tms / photo; wms |
| [Geoportal 2: Orthophotomap (latest aerial imagery) (WMTS)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pl/Geoportal2Orthophotomap(aerialimage)_WMTS.geojson) | [Wrocław: Orthophotomap 2018 (aerial image)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pl/WrocawOrthophotomap2018(aerialimage).geojson) | 318.35 | 100.0% | photo; tms / photo; wms |

### PT (3 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Orthophotos of mainland Portugal - 25 cm - 2018 (DGT)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pt/Orthophotos_mainland-25cm-2018.geojson) | [Orthophotos of the northern portion of mainland Portugal - 25 cm - 2021 (DGT)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pt/Orthophotos_north-25cm-2021.geojson) | 48,031.60 | 99.7% | photo; wms / photo; wms |
| [Orthophotos of mainland Portugal - 25 cm - 2018 (DGT)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pt/Orthophotos_mainland-25cm-2018.geojson) | [Orthophotos of mainland Portugal - 25 cm - 2025 (DGT)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pt/Orthophotos_mainland-25cm-2025.geojson) | 107,379.37 | 96.7% | photo; wms / photo; wms |
| [Orthophotos of the northern portion of mainland Portugal - 25 cm - 2021 (DGT)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pt/Orthophotos_north-25cm-2021.geojson) | [Orthophotos of mainland Portugal - 25 cm - 2025 (DGT)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/pt/Orthophotos_mainland-25cm-2025.geojson) | 48,163.26 | 100.0% | photo; wms / photo; wms |

### SE (6 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [Kalmar North Orthophoto 2014](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2014.geojson) | [Kalmar South Orthophoto 2016](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2016.geojson) | 20.04 | 12.0% | photo; wms / photo; wms |
| [Kalmar North Orthophoto 2014](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2014.geojson) | [Kalmar Urban Orthophoto 2018](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2018.geojson) | 30.23 | 21.1% | photo; wms / photo; wms |
| [Kalmar North Orthophoto 2014](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2014.geojson) | [Kalmar Urban Orthophoto 2020](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2020.geojson) | 55.13 | 32.9% | photo; wms / photo; wms |
| [Kalmar South Orthophoto 2016](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2016.geojson) | [Kalmar Urban Orthophoto 2018](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2018.geojson) | 71.16 | 49.6% | photo; wms / photo; wms |
| [Kalmar South Orthophoto 2016](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2016.geojson) | [Kalmar Urban Orthophoto 2020](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2020.geojson) | 271.01 | 91.5% | photo; wms / photo; wms |
| [Kalmar Urban Orthophoto 2018](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2018.geojson) | [Kalmar Urban Orthophoto 2020](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/europe/se/kalmar_orto_2020.geojson) | 92.47 | 64.4% | photo; wms / photo; wms |

### US (6 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [ETCOG Imagery (2024)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/tx/ETCOG24_NC_6in.geojson) | [TX: Smith County Imagery 2019](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/tx/Smith_County_Orthophoto_2019_WMS.geojson) | 462.54 | 16.8% | photo; wms / photo; wms |
| [Maui County Orthoimagery (2023)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/hi/Maui_2023.geojson) | [Maui County Orthoimagery (2025)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/hi/Maui_2025.geojson) | 56.99 | 100.0% | photo; tms / photo; tms |
| [Maui County Orthoimagery (2023)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/hi/Maui_2023.geojson) | [Maui County Orthoimagery (2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/hi/Maui_2026.geojson) | 66.69 | 100.0% | photo; tms / photo; tms |
| [Maui County Orthoimagery (2025)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/hi/Maui_2025.geojson) | [Maui County Orthoimagery (2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/hi/Maui_2026.geojson) | 18.29 | 32.1% | photo; tms / photo; tms |
| [Rhode Island Aerial Photo (Spring 2025)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/ri/RIGIS_Aerial_Photo_25s.geojson) | [Rhode Island Aerial Photo (Spring 2026)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/ri/RIGIS_Aerial_Photo_26s.geojson) | 3,284.82 | 100.0% | historicphoto; wms / photo; wms |
| [StratMap CapArea, Brazos & Kerr Imagery (Natural Color 2021)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/tx/StratMap21_NCCIR_CapArea_Brazos_Kerr.geojson) | [StratMap Brazos County Imagery (2019)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/north-america/us/tx/Brazos_County_Orthophoto_2019_WMS.geojson) | 1,877.30 | 94.4% | photo; wms / historicphoto; wms |

### ZA (1 pairs)

| First best source | Second best source | Overlap (km²) | Smaller footprint | Categories; types |
| --- | --- | ---: | ---: | --- |
| [South Africa CD:NGI Aerial](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/africa/za/SouthAfricaCDNGIAerial.geojson) | [City of Cape Town Aerial Imagery (2025)](https://github.com/osmlab/editor-layer-index/blob/gh-pages/sources/africa/za/SouthAfricaCoCT2025Aerial.geojson) | 3,471.12 | 71.9% | photo; tms / photo; wms |
