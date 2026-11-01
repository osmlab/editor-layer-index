# JOSM imagery schema

`maps.xsd` is a whitespace-normalised offline snapshot of JOSM's imagery schema:

- Published schema: https://josm.openstreetmap.de/maps-1.0
- Source: https://github.com/JOSM/josm/blob/1aefcb0cc6615b1c2ea3c85d002a71a89ef02f78/resources/data/maps.xsd
- Retrieved: 2026-11-01

The schema belongs to the JOSM project. JOSM and its integral parts are licensed
under GPL-2.0-or-later (https://github.com/JOSM/josm/blob/1aefcb0cc6615b1c2ea3c85d002a71a89ef02f78/LICENSE).
See `COPYING` for the GPL version 2 text. This licence applies to the schema;
it does not change the ELI imagery catalogue's licence.
Builds and tests validate against this snapshot without network access. PR CI
and the weekly audit additionally fetch and validate against the published
schema with `eli validate-josm`. To update the snapshot, copy the upstream file,
update this reference, and run the full build and tests.
