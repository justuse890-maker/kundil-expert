# Third-party notices

## Swiss Ephemeris

This project uses the Swiss Ephemeris (via `pyswisseph`) and ships its data files
(`sepl_18.se1`, `semo_18.se1`, `seas_18.se1`) in `backend/ephe/`.
Swiss Ephemeris is Copyright Astrodienst AG, Zurich, and is licensed under the
GNU Affero General Public License (AGPL-3.0) for open-source use.
See https://www.astro.com/swisseph/ .

## GeoNames

The offline place search (`backend/data/cities.tsv`) is derived from the GeoNames
`cities15000` extract and `admin1CodesASCII` (https://www.geonames.org/), which are
licensed under the Creative Commons Attribution 4.0 licence
(https://creativecommons.org/licenses/by/4.0/). Changes: columns reduced to name, ASCII
name, region, country, latitude, longitude, population and timezone; sorted by population.
Regenerate with `backend/scripts/build_cities.py`.
