# India SEZ Atlas

Interactive map of all **277 operational Special Economic Zones** in India, from the Department of Commerce list "Operational SEZs in India" (up to 31.03.2026). SEZs are grouped into 8 sector groups (colour + shape), with a built-in completeness check, search, state filter and a full table.

**Live site (GitHub Pages):** `https://<your-username>.github.io/<repo-name>/`

## Run locally
The page fetches files from `data/`, so open it through a web server, not `file://`:

    python3 -m http.server 8000     # then open http://localhost:8000

## Deploy on GitHub Pages
Settings -> Pages -> Deploy from a branch -> `main` / root. No build step. (`.nojekyll` is included.)

## Contents
- `index.html` - the whole app (d3 v7.8.5 loaded from cdnjs, fonts from Google Fonts)
- `data/` - basemap layers (`states`, `districts`, `taluks`, `roads`, `rivers`, `lakes`, `urban`) and `places.json` (place-name labels)
- `sez_india_277.csv` - the 277 records with coordinates and sector group
- `scripts/` - Python used to prepare the data (not needed to run the site)

## Notes and limits
- SEZ pins are locality-level approximations, not surveyed boundaries. Place labels can sit a few km from the exact spot.
- OpenStreetMap was not used; the basemap is bundled open data.

## Sources and licences
- SEZ list: Department of Commerce, Government of India (sezindia.gov.in)
- Boundaries: Census of India 2011 via datameet and udit-001/india-maps-data (simplified)
- Roads, rivers, lakes, urban areas: Natural Earth (public domain)
- Place names: GeoNames (CC BY 4.0); India Post office names (Government Open Data License - India)
- d3 (ISC), Inter and Space Grotesk (SIL OFL)

Add your own licence for the code (e.g. MIT) before publishing.
