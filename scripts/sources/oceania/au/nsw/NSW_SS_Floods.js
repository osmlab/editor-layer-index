#!/usr/bin/env node

// scripted used to help generate NSW SS Floods layers

const fs = require('fs');

const services = [
    'Floods_2021',
    'Floods_Historical',
    'Floods_Mar_2022',
    'Floods_Nov_2021',
    'Floods_Nov_2022'
];

const template = {
    "type": "Feature",
    "properties": {
        "attribution": {
            "url": "https://www.spatial.nsw.gov.au/",
            "text": "© State of New South Wales (Spatial Services, a business unit of the Department of Customer Service NSW). For current information go to spatial.nsw.gov.au.",
            "required": true
        },
        "license_url": "https://wiki.openstreetmap.org/wiki/File:SpatialServices_NSW_OSM_Waiver_completed.pdf",
        "privacy_policy_url": "https://www.spatial.nsw.gov.au/privacy",
        "name": "",
        "url": null,
        "available_projections": [
            "EPSG:3857"
        ],
        "max_zoom": 21,
        "min_zoom": 1,
        "start_date": null,
        "end_date": null,
        "country_code": "AU",
        "type": "wms",
        "id": "",
        "icon": "https://portal.spatial.nsw.gov.au/portal//sharing/rest/content/items/10ee1f6276e746efa7f3e364ed51d67f/resources/NSWGov_Logo_RGB_Primary_FullColour_sml3-01.png",
        "category": "historicphoto"
    }
};

(async() => {
    for (const service of services) {
        const serviceName = service.replaceAll('_', ' ');
        const response = await fetch(`https://portal.spatial.nsw.gov.au/server/rest/services/${service}/MapServer?f=pjson`);
        const data = await response.json();
        for (const layer of data.layers) {
            const id = layer.id;
            const name = layer.name?.replace(/\.jp2$/, '').replaceAll('_', ' ');
            const layerId = layer.name?.replace(/\.jp2$/, '').replaceAll(' ', '_');

            // 03122022 -> 2022-12-03
            // 2021_11_15 -> 2021-11-15
            // 2021_11_13cm -> 2021-11
            const date = layer.name?.match(/(?<dd>\d\d)(?<mm>\d\d)(?<yyyy>\d\d\d\d)_/)?.groups ??
                layer.name?.match(/(?<yyyy>\d\d\d\d)_(?<mm>\d\d)_(?<dd>\d\d)_/)?.groups ??
                layer.name?.match(/(?<yyyy>\d\d\d\d)_(?<mm>\d\d)_/)?.groups;

            const result = { ...template };

            result.properties.url = `https://portal.spatial.nsw.gov.au/server/rest/services/${service}/MapServer/export?f=image&format=png&transparent=true&imageSR={wkid}&bboxSR={wkid}&bbox={bbox}&size={width},{height}&layers=show:${id}`;

            let formattedDate;
            if (date && date.yyyy && date.mm && date.dd) {
                formattedDate = `${date.yyyy}-${date.mm}-${date.dd}`;
            }else if (date && date.yyyy && date.mm) {
                formattedDate = `${date.yyyy}-${date.mm}`;
            }else if (date && date.yyyy) {
                formattedDate = `${date.yyyy}`;
            }
            if (formattedDate) {
                result.properties.start_date = formattedDate;
                result.properties.end_date = formattedDate;
            } else {
                delete result.properties.start_date;
                delete result.properties.end_date;
            }

            result.properties.name = `DCS NSW ${serviceName} ${name}`;
            result.properties.id = `DCS_NSW_${service}_${layerId}`;

            if (formattedDate) {
                console.log(`${service} ${layer.id}: ${layer.name} (${formattedDate})`);
            } else {
                console.log(`${service} ${layer.id}: ${layer.name}`);
            }
            fs.writeFileSync(`output/NSW_SS_${service}_${layerId}.geojson`, JSON.stringify(result, null, 4));
        }
    }
})();
