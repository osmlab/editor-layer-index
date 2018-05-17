/* eslint-disable no-console */
const colors = require('colors/safe');
const fs = require('fs');
const glob = require('glob');
const precision = require('geojson-precision');
const rewind = require('geojson-rewind');
const Validator = require('jsonschema').Validator;
const shell = require('shelljs');
const prettyStringify = require('json-stringify-pretty-compact');
const YAML = require('js-yaml');

const geojsonSchema = require('./schema/geojson.json');
const featureSchema = require('./schema/feature.json');
const resourceSchema = require('./schema/resource.json');

var v = new Validator();
v.addSchema(geojsonSchema, 'http://json.schemastore.org/geojson.json');

buildAll();


function buildAll() {
    console.log('building data');
    console.time(colors.green('data built'));

    // Start clean
    shell.rm('-f', ['dist/*.json', 'dist/*.js', 'i18n/en.yaml']);

    var tstrings = {};   // translation strings
    var features = generateFeatures();
    var resources = generateResources(tstrings, features);

    // Save individual data files
    fs.writeFileSync('dist/features.json', prettyStringify({ features: features }) );
    fs.writeFileSync('dist/features.min.json', JSON.stringify({ features: features }) );
    fs.writeFileSync('dist/resources.json', prettyStringify({ resources: resources }) );
    fs.writeFileSync('dist/resources.min.json', JSON.stringify({ resources: resources }) );
    fs.writeFileSync('i18n/en.yaml', YAML.safeDump({ en: { imagery: tstrings }}, { lineWidth: -1, sortKeys: true }) );

    console.timeEnd(colors.green('data built'));
}


function generateFeatures() {
    var features = {};
    var files = {};

    glob.sync(__dirname + '/features/**/*.geojson').forEach(function(file) {
        var contents = fs.readFileSync(file, 'utf8');
        var feature = precision(rewind(JSON.parse(contents), true), 5);
        var fc = feature.features;

        // A FeatureCollection with a single feature inside (geojson.io likes to make these).
        if (feature.type === 'FeatureCollection' && Array.isArray(fc) && fc.length === 1) {
            if (feature.id && !fc[0].id) {
                fc[0].id = feature.id;
            }
            feature = fc[0];
        }

        validateFile(file, feature, featureSchema);
        prettifyFile(file, feature, contents);

        var id = feature.id;
        if (files[id]) {
            console.error(colors.red('Error - Duplicate feature id: ') + colors.yellow(id));
            console.error('  ' + colors.yellow(files[id]));
            console.error('  ' + colors.yellow(file));
            process.exit(1);
        }
        features[id] = feature;
        files[id] = file;
    });

    return features;
}


function generateResources(tstrings, features) {
    var resources = {};
    var files = {};

    glob.sync(__dirname + '/resources/**/*.json').forEach(function(file) {
        var contents = fs.readFileSync(file, 'utf8');
        var resource = JSON.parse(contents);
        validateFile(file, resource, resourceSchema);
        prettifyFile(file, resource, contents);

        var resourceId = resource.id;
        if (files[resourceId]) {
            console.error(colors.red('Error - Duplicate resource id: ') + colors.yellow(resourceId));
            console.error('  ' + colors.yellow(files[resourceId]));
            console.error('  ' + colors.yellow(file));
            process.exit(1);
        }

        var url = resource.url;
        if (/\{z\}/.test(url)) {
            console.error(colors.red('Error - {z} found instead of {zoom} in tile url: '));
            console.error('  ' + colors.yellow(url));
            console.error('  ' + colors.yellow(file));
            process.exit(1);
        }

        var featureId = resource.featureId;
        if (featureId && !features[featureId]) {
            console.error(colors.red('Error - Unknown feature id: ') + colors.yellow(featureId));
            console.error('  ' + colors.yellow(file));
            process.exit(1);
        }

        if (!featureId && !/\/resources\/world/.test(file)) {
            if (resource.type !== 'scanex') {  // TODO make these normal TMS sources
                console.error(colors.red('Error - feature id is required for non-worldwide resource:'));
                console.error('  ' + colors.yellow(file));
                process.exit(1);
            }
        }

        resources[resourceId] = resource;
        files[resourceId] = file;

        // collect translation strings for this resource
        if (resource.i18n) {
            var t = {};
            if (resource.name) {
                t.name = resource.name;
            }
            if (resource.description) {
                t.description = resource.description;
            }
            if (resource.attribution && resource.attribution.text) {
                t.attribution = { text: resource.attribution.text };
            }

            tstrings[resourceId] = t;
        }
    });

    return resources;
}


function validateFile(file, resource, schema) {
    var validationErrors = v.validate(resource, schema).errors;
    if (validationErrors.length) {
        console.error(colors.red('Error - Schema validation:'));
        console.error('  ' + colors.yellow(file + ': '));
        validationErrors.forEach(function(error) {
            if (error.property) {
                console.error('  ' + colors.yellow(error.property + ' ' + error.message));
            } else {
                console.error('  ' + colors.yellow(error));
            }
        });
        process.exit(1);
    }
}


function prettifyFile(file, object, contents) {
    var pretty = prettyStringify(object);
    if (pretty !== contents) {
        fs.writeFileSync(file, pretty);
    }
}

