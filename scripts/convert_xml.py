import argparse
import glob
import json
import logging
import os
import lxml.etree as ET
from lxml.etree import CDATA
from shapely.geometry import shape, Polygon
from shapely.ops import transform
from pyproj import Transformer
import colorlog

logger = colorlog.getLogger()

# Start off at Error, reduce by one level for each -v argument
logger.setLevel(logging.INFO)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

parser = argparse.ArgumentParser(description="Convert sources to xml.")
parser.add_argument(
    "sources",
    metavar="sources",
    type=str,
    nargs="?",
    help="relative path to sources directory",
    default="sources",
)

arguments = parser.parse_args()
sources_directory = arguments.sources

country_code_list = {
    # EUROPE (JOSM ONLY)
    "EU",
    # KOSOVO (TEMPORARY USER-ASSIGNED CODE)
    "XK",
    # AFGHANISTAN
    "AF",
    # ÅLAND ISLANDS
    "AX",
    # ALBANIA
    "AL",
    # ALGERIA
    "DZ",
    # AMERICAN SAMOA
    "AS",
    # ANDORRA
    "AD",
    # ANGOLA
    "AO",
    # ANGUILLA
    "AI",
    # ANTARCTICA
    "AQ",
    # ANTIGUA AND BARBUDA
    "AG",
    # ARGENTINA
    "AR",
    # ARMENIA
    "AM",
    # ARUBA
    "AW",
    # AUSTRALIA
    "AU",
    # AUSTRIA
    "AT",
    # AZERBAIJAN
    "AZ",
    # BAHAMAS
    "BS",
    # BAHRAIN
    "BH",
    # BANGLADESH
    "BD",
    # BARBADOS
    "BB",
    # BELARUS
    "BY",
    # BELGIUM
    "BE",
    # BELIZE
    "BZ",
    # BENIN
    "BJ",
    # BERMUDA
    "BM",
    # BHUTAN
    "BT",
    # BOLIVIA, PLURINATIONAL STATE OF
    "BO",
    # BONAIRE, SINT EUSTATIUS AND SABA
    "BQ",
    # BOSNIA AND HERZEGOVINA
    "BA",
    # BOTSWANA
    "BW",
    # BOUVET ISLAND
    "BV",
    # BRAZIL
    "BR",
    # BRITISH INDIAN OCEAN TERRITORY
    "IO",
    # BRUNEI DARUSSALAM
    "BN",
    # BULGARIA
    "BG",
    # BURKINA FASO
    "BF",
    # BURUNDI
    "BI",
    # CAMBODIA
    "KH",
    # CAMEROON
    "CM",
    # CANADA
    "CA",
    # CAPE VERDE
    "CV",
    # CAYMAN ISLANDS
    "KY",
    # CENTRAL AFRICAN REPUBLIC
    "CF",
    # CHAD
    "TD",
    # CHILE
    "CL",
    # CHINA
    "CN",
    # CHRISTMAS ISLAND
    "CX",
    # COCOS (KEELING) ISLANDS
    "CC",
    # COLOMBIA
    "CO",
    # COMOROS
    "KM",
    # CONGO
    "CG",
    # CONGO, THE DEMOCRATIC REPUBLIC OF THE
    "CD",
    # COOK ISLANDS
    "CK",
    # COSTA RICA
    "CR",
    # CÔTE D'IVOIRE
    "CI",
    # CROATIA
    "HR",
    # CUBA
    "CU",
    # CURAÇAO
    "CW",
    # CYPRUS
    "CY",
    # CZECH REPUBLIC
    "CZ",
    # DENMARK
    "DK",
    # DJIBOUTI
    "DJ",
    # DOMINICA
    "DM",
    # DOMINICAN REPUBLIC
    "DO",
    # ECUADOR
    "EC",
    # EGYPT
    "EG",
    # EL SALVADOR
    "SV",
    # EQUATORIAL GUINEA
    "GQ",
    # ERITREA
    "ER",
    # ESTONIA
    "EE",
    # ETHIOPIA
    "ET",
    # FALKLAND ISLANDS (MALVINAS)
    "FK",
    # FAROE ISLANDS
    "FO",
    # FIJI
    "FJ",
    # FINLAND
    "FI",
    # FRANCE
    "FR",
    # FRENCH GUIANA
    "GF",
    # FRENCH POLYNESIA
    "PF",
    # FRENCH SOUTHERN TERRITORIES
    "TF",
    # GABON
    "GA",
    # GAMBIA
    "GM",
    # GEORGIA
    "GE",
    # GERMANY
    "DE",
    # GHANA
    "GH",
    # GIBRALTAR
    "GI",
    # GREECE
    "GR",
    # GREENLAND
    "GL",
    # GRENADA
    "GD",
    # GUADELOUPE
    "GP",
    # GUAM
    "GU",
    # GUATEMALA
    "GT",
    # GUERNSEY
    "GG",
    # GUINEA
    "GN",
    # GUINEA-BISSAU
    "GW",
    # GUYANA
    "GY",
    # HAITI
    "HT",
    # HEARD ISLAND AND MCDONALD ISLANDS
    "HM",
    # HOLY SEE (VATICAN CITY STATE)
    "VA",
    # HONDURAS
    "HN",
    # HONG KONG
    "HK",
    # HUNGARY
    "HU",
    # ICELAND
    "IS",
    # INDIA
    "IN",
    # INDONESIA
    "ID",
    # IRAN, ISLAMIC REPUBLIC OF
    "IR",
    # IRAQ
    "IQ",
    # IRELAND
    "IE",
    # ISLE OF MAN
    "IM",
    # ISRAEL
    "IL",
    # ITALY
    "IT",
    # JAMAICA
    "JM",
    # JAPAN
    "JP",
    # JERSEY
    "JE",
    # JORDAN
    "JO",
    # KAZAKHSTAN
    "KZ",
    # KENYA
    "KE",
    # KIRIBATI
    "KI",
    # KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF
    "KP",
    # KOREA, REPUBLIC OF
    "KR",
    # KUWAIT
    "KW",
    # KYRGYZSTAN
    "KG",
    # LAO PEOPLE'S DEMOCRATIC REPUBLIC
    "LA",
    # LATVIA
    "LV",
    # LEBANON
    "LB",
    # LESOTHO
    "LS",
    # LIBERIA
    "LR",
    # LIBYAN ARAB JAMAHIRIYA
    "LY",
    # LIECHTENSTEIN
    "LI",
    # LITHUANIA
    "LT",
    # LUXEMBOURG
    "LU",
    # MACAO
    "MO",
    # MACEDONIA, THE FORMER YUGOSLAV REPUBLIC OF
    "MK",
    # MADAGASCAR
    "MG",
    # MALAWI
    "MW",
    # MALAYSIA
    "MY",
    # MALDIVES
    "MV",
    # MALI
    "ML",
    # MALTA
    "MT",
    # MARSHALL ISLANDS
    "MH",
    # MARTINIQUE
    "MQ",
    # MAURITANIA
    "MR",
    # MAURITIUS
    "MU",
    # MAYOTTE
    "YT",
    # MEXICO
    "MX",
    # MICRONESIA, FEDERATED STATES OF
    "FM",
    # MOLDOVA, REPUBLIC OF
    "MD",
    # MONACO
    "MC",
    # MONGOLIA
    "MN",
    # MONTENEGRO
    "ME",
    # MONTSERRAT
    "MS",
    # MOROCCO
    "MA",
    # MOZAMBIQUE
    "MZ",
    # MYANMAR
    "MM",
    # NAMIBIA
    "NA",
    # NAURU
    "NR",
    # NEPAL
    "NP",
    # NETHERLANDS
    "NL",
    # NEW CALEDONIA
    "NC",
    # NEW ZEALAND
    "NZ",
    # NICARAGUA
    "NI",
    # NIGER
    "NE",
    # NIGERIA
    "NG",
    # NIUE
    "NU",
    # NORFOLK ISLAND
    "NF",
    # NORTHERN MARIANA ISLANDS
    "MP",
    # NORWAY
    "NO",
    # OMAN
    "OM",
    # PAKISTAN
    "PK",
    # PALAU
    "PW",
    # PALESTINIAN TERRITORY, OCCUPIED
    "PS",
    # PANAMA
    "PA",
    # PAPUA NEW GUINEA
    "PG",
    # PARAGUAY
    "PY",
    # PERU
    "PE",
    # PHILIPPINES
    "PH",
    # PITCAIRN
    "PN",
    # POLAND
    "PL",
    # PORTUGAL
    "PT",
    # PUERTO RICO
    "PR",
    # QATAR
    "QA",
    # RÉUNION
    "RE",
    # ROMANIA
    "RO",
    # RUSSIAN FEDERATION
    "RU",
    # RWANDA
    "RW",
    # SAINT BARTHÉLEMY
    "BL",
    # SAINT HELENA, ASCENSION AND TRISTAN DA CUNHA
    "SH",
    # SAINT KITTS AND NEVIS
    "KN",
    # SAINT LUCIA
    "LC",
    # SAINT MARTIN (FRENCH PART)
    "MF",
    # SAINT PIERRE AND MIQUELON
    "PM",
    # SAINT VINCENT AND THE GRENADINES
    "VC",
    # SAMOA
    "WS",
    # SAN MARINO
    "SM",
    # SAO TOME AND PRINCIPE
    "ST",
    # SAUDI ARABIA
    "SA",
    # SENEGAL
    "SN",
    # SERBIA
    "RS",
    # SEYCHELLES
    "SC",
    # SIERRA LEONE
    "SL",
    # SINGAPORE
    "SG",
    # SINT MAARTEN (DUTCH PART)
    "SX",
    # SLOVAKIA
    "SK",
    # SLOVENIA
    "SI",
    # SOLOMON ISLANDS
    "SB",
    # SOMALIA
    "SO",
    # SOUTH AFRICA
    "ZA",
    # SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS
    "GS",
    # SOUTH SUDAN
    "SS",
    # SPAIN
    "ES",
    # SRI LANKA
    "LK",
    # SUDAN
    "SD",
    # SURINAME
    "SR",
    # SVALBARD AND JAN MAYEN
    "SJ",
    # SWAZILAND
    "SZ",
    # SWEDEN
    "SE",
    # SWITZERLAND
    "CH",
    # SYRIAN ARAB REPUBLIC
    "SY",
    # TAIWAN, PROVINCE OF CHINA
    "TW",
    # TAJIKISTAN
    "TJ",
    # TANZANIA, UNITED REPUBLIC OF
    "TZ",
    # THAILAND
    "TH",
    # TIMOR-LESTE
    "TL",
    # TOGO
    "TG",
    # TOKELAU
    "TK",
    # TONGA
    "TO",
    # TRINIDAD AND TOBAGO
    "TT",
    # TUNISIA
    "TN",
    # TURKEY
    "TR",
    # TURKMENISTAN
    "TM",
    # TURKS AND CAICOS ISLANDS
    "TC",
    # TUVALU
    "TV",
    # UGANDA
    "UG",
    # UKRAINE
    "UA",
    # UNITED ARAB EMIRATES
    "AE",
    # UNITED KINGDOM
    "GB",
    # UNITED STATES
    "US",
    # UNITED STATES MINOR OUTLYING ISLANDS
    "UM",
    # URUGUAY
    "UY",
    # UZBEKISTAN
    "UZ",
    # VANUATU
    "VU",
    # VENEZUELA, BOLIVARIAN REPUBLIC OF
    "VE",
    # VIET NAM
    "VN",
    # VIRGIN ISLANDS, BRITISH
    "VG",
    # VIRGIN ISLANDS, U.S.
    "VI",
    # WALLIS AND FUTUNA
    "WF",
    # WESTERN SAHARA
    "EH",
    # YEMEN
    "YE",
    # ZAMBIA
    "ZM",
    # ZIMBABWE
    "ZW",
}

MAX_COORDINATES = 999

transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
transformer_back = Transformer.from_crs("epsg:3857", "epsg:4326", always_xy=True)


def simplify_geometry(geom):
    """ Simplify geometry in epsg:3857"""
    distance = 100
    coordinates_count = len(geom.exterior.coords)
    while coordinates_count > MAX_COORDINATES:
        geom_3857 = transform(transformer.transform, geom)
        geom_3857_simplified = geom_3857.simplify(distance, preserve_topology=True)
        geom = transform(transformer_back.transform, geom_3857_simplified)
        coordinates_count = len(geom.exterior.coords)
        distance *= 1.5
    logger.info(f"{filename}: Reduced to {coordinates_count} coordinates using distance {distance} in EPSG:3857.")
    return geom


def add_source(source_path, root):
    """ Convert a source to an entry and add it to root"""

    with open(source_path) as f:
        source = json.load(f)

    properties = source["properties"]
    entry = ET.SubElement(root, "entry")

    source_name = ET.SubElement(entry, "name")
    source_name.text = properties["name"]

    source_id = ET.SubElement(entry, "id")
    source_id.text = properties["id"]

    source_type = ET.SubElement(entry, "type")
    source_type.text = properties["type"]

    source_url = ET.SubElement(entry, "url")
    source_url.text = CDATA(properties["url"])

    if properties.get("overlay"):
        entry.set("overlay", "true")

    if properties.get("best"):
        entry.set("eli-best", "true")

    if "available_projections" in properties:
        projections = ET.SubElement(entry, "projections")
        for projection in properties["available_projections"]:
            code = ET.SubElement(projections, "code")
            code.text = projection

    if "attribution" in properties:
        attribution = properties["attribution"]

        if attribution.get("text"):
            text = ET.SubElement(entry, "attribution-text")
            if attribution.get("required"):
                text.set("mandatory", "true")
            text.text = attribution["text"]

        if attribution.get("url"):
            url = ET.SubElement(entry, "attribution-url")
            url.text = CDATA(attribution["url"])

    if source.get("default", False):
        default = ET.SubElement(entry, "default")
        default.text = "true"

    if "start_date" in properties:
        date = ET.SubElement(entry, "date")
        if (
            "end_date" in properties
            and properties["start_date"] == properties["end_date"]
        ):
            date.text = properties["start_date"]
        elif (
            "end_date" in properties
            and properties["start_date"] != properties["end_date"]
        ):
            date.text = ";".join([properties["start_date"], properties["end_date"]])
        else:
            date.text = ";".join([properties["start_date"], "-"])

    if "icon" in properties:
        icon = ET.SubElement(entry, "icon")
        icon.text = CDATA(properties["icon"])

    if "country_code" in properties:
        if properties["country_code"] in country_code_list:
            country_code = ET.SubElement(entry, "country-code")
            country_code.text = properties["country_code"]

    if "license_url" in properties:
        permission_ref = ET.SubElement(entry, "permission-ref")
        permission_ref.text = CDATA(properties["license_url"])

    if "description" in properties:
        description = ET.SubElement(entry, "description")
        description.text = properties["description"]
        description.set("lang", "unknown")

    if "min_zoom" in properties:
        min_zoom = ET.SubElement(entry, "min-zoom")
        min_zoom.text = str(properties["min_zoom"])

    if "max_zoom" in properties:
        max_zoom = ET.SubElement(entry, "max-zoom")
        max_zoom.text = str(properties["max_zoom"])

    geometry = source.get("geometry")
    if geometry:

        def coord_str(coord):
            return "{0:.6f}".format(coord)

        geom = shape(geometry)
        bounds = ET.SubElement(entry, "bounds")

        minx, miny, maxx, maxy = geom.bounds
        bounds.set("min-lon", coord_str(minx))
        bounds.set("min-lat", coord_str(miny))
        bounds.set("max-lon", coord_str(maxx))
        bounds.set("max-lat", coord_str(maxy))

        # Currently ELI encodes Multipolygons as interior rings
        geoms = [Polygon(geom.exterior)]
        for ring in geom.interiors:
            geoms.append(Polygon(ring))

        for g in geoms:
            # Simplify geometries with more coordinates than max limit specified in maps.xsd
            coordinates_count = len(g.exterior.coords)
            if len(g.exterior.coords) > MAX_COORDINATES:
                logger.warning(
                    f"{filename}: Polygon with too many coordinates: {coordinates_count} > {MAX_COORDINATES}."
                )
                g = simplify_geometry(g)

            shape_element = ET.SubElement(bounds, "shape")
            # All interior rings (=holes) of polygons are ignored
            for c in g.exterior.coords:
                point_element = ET.SubElement(shape_element, "point")
                point_element.set("lon", coord_str(c[0]))
                point_element.set("lat", coord_str(c[1]))


root = ET.Element("imagery")
root.set("xmlns", "http://josm.openstreetmap.de/maps-1.0")

# Find all sources and convert them to xml
for filename in glob.glob(
    os.path.join(sources_directory, "**", "*.geojson"), recursive=True
):
    add_source(filename, root)

# Write pretty output
xml = ET.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True)
with open("imagery.xml", "wb") as f:
    f.write(xml)
