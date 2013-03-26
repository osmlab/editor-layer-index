var width = 300,
    height = 300;

var projection = d3.geo.miller()
    .translate([150, 150])
    .scale(50);

var path = d3.geo.path()
    .projection(projection);

var graticule = d3.geo.graticule();

var svg = d3.select("#map").append("svg")
    .attr("width", width)
    .attr("height", height);

svg.append("path")
    .datum(graticule.outline)
    .attr("class", "background")
    .attr("d", path);

svg.append("path")
    .datum(graticule.outline)
    .attr("class", "foreground")
    .attr("d", path);

d3.json("lib/world-110m.json", function(error, world) {
  svg.insert("path", ".graticule")
      .datum(topojson.object(world, world.objects.land))
      .attr("class", "land");

  svg.insert("path", ".graticule")
      .datum(topojson.mesh(world, world.objects.countries, function(a, b) { return a.id !== b.id; }))
      .attr("class", "boundary");
  d3.json("imagery.geojson", function(error, imagery) {
      var imagery_paths = svg.selectAll("path.imagery")
          .data(imagery.features)
          .enter()
          .append('path')
          .attr("class", "imagery");
      function update() {
          if (d3.event && d3.event.translate) {
            projection
                .translate(d3.event.translate)
                .scale(d3.event.scale);
          }
          svg.selectAll("path.graticule").attr("d", path);
          svg.selectAll("path.boundary").attr("d", path);
          svg.selectAll("path.foreground").attr("d", path);
          svg.selectAll("path.background").attr("d", path);
          svg.selectAll("path.land").attr("d", path);
          svg.selectAll("path.imagery").attr("d", path);
      }
      var zoom = d3.behavior.zoom()
        .on('zoom', update);

      svg.call(zoom);
      update();

      var divs = d3.select('#wrap')
        .selectAll('div')
        .data(imagery.features)
        .enter()
        .append('div');

      var info = d3.select('#info');

      var imagery_links = divs.append('a')
        .text(function(d) {
            return d.properties.name;
        })
        .attr('href', '#')
        .on('mouseover', function(d, i) {
            d3.event.preventDefault();
            var centroid = d3.geo.centroid(d);

            projection.scale(1).translate([0, 0]);

            var b = path.bounds(d),
                s = .55 / Math.max((b[1][0] - b[0][0]) / width,
                    (b[1][1] - b[0][1]) / height),
                t = [(width - s * (b[1][0] + b[0][0])) / 2,
                    (height - s * (b[1][1] + b[0][1])) / 2];

            projection.scale(s)
                  .translate(t);
            zoom.translate(projection.translate())
                  .scale(projection.scale())

            imagery_links.classed('active', function(d2, i2) {
                    return i2 == i;
                });
            imagery_paths.classed('active', function(d2, i2) {
                    return i2 == i;
                });

            update();
            info.datum(d);
        });

      imagery_links.append('span')
        .classed('type', true)
        .text(function(d) {
            return d.properties.type;
        });

      var meta = divs.append('div')
        .classed('meta', true);

      meta.append('span')
        .text(function(d) {
            return 'url: ' + d.properties.url;
        });
  });
});
